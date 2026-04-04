"""
NARA-AI SFT 학습 파이프라인

EXAONE 3.5 8B 모델을 기록물 분류/메타데이터/비밀해제 과업으로 파인튜닝한다.
QLoRA + DoRA로 4-8 GPU 환경에서 효율적으로 학습한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import torch
import yaml
from torch.utils.data import Dataset

logger = logging.getLogger("nara-ai.train.sft")


@dataclass
class SFTConfig:
    """SFT 학습 설정"""
    base_model: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
    output_dir: str = "checkpoints/nara-sft-v1"
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation: int = 8
    learning_rate: float = 2e-4
    max_seq_length: int = 4096
    lora_rank: int = 64
    lora_alpha: int = 128
    use_dora: bool = True
    bf16: bool = True
    gradient_checkpointing: bool = True
    deepspeed_config: Optional[str] = None
    wandb_project: str = "nara-ai-sft"

    @classmethod
    def from_yaml(cls, path: str) -> "SFTConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            base_model=data.get("model", {}).get("base_model", cls.base_model),
            output_dir=data.get("output", {}).get("output_dir", cls.output_dir),
            epochs=data.get("training", {}).get("epochs", cls.epochs),
            batch_size=data.get("training", {}).get("per_device_batch_size", cls.batch_size),
            gradient_accumulation=data.get("training", {}).get("gradient_accumulation_steps", cls.gradient_accumulation),
            learning_rate=data.get("training", {}).get("learning_rate", cls.learning_rate),
            max_seq_length=data.get("training", {}).get("max_seq_length", cls.max_seq_length),
            lora_rank=data.get("model", {}).get("lora", {}).get("rank", cls.lora_rank),
            lora_alpha=data.get("model", {}).get("lora", {}).get("alpha", cls.lora_alpha),
            use_dora=data.get("model", {}).get("lora", {}).get("use_dora", cls.use_dora),
            deepspeed_config=data.get("deepspeed", {}).get("config_path"),
            wandb_project=data.get("tracking", {}).get("wandb", {}).get("project", cls.wandb_project),
        )


class NaraInstructionDataset(Dataset):
    """NARA-AI 명령어 데이터셋 (JSONL 형식)

    각 행: {"instruction": "...", "input": "...", "output": "..."}
    """

    def __init__(self, data_path: str, tokenizer: Any, max_length: int = 4096):
        self.data: list[dict[str, str]] = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        path = Path(data_path)
        if path.is_file():
            self._load_file(path)
        elif path.is_dir():
            for f in sorted(path.glob("*.jsonl")):
                self._load_file(f)

        logger.info(f"데이터셋 로드 완료: {len(self.data)}건 ({data_path})")

    def _load_file(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.data.append(json.loads(line))

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.data[idx]
        instruction = item.get("instruction", "")
        input_text = item.get("input", "")
        output_text = item.get("output", "")

        if input_text:
            prompt = f"### 지시사항\n{instruction}\n\n### 입력\n{input_text}\n\n### 응답\n"
        else:
            prompt = f"### 지시사항\n{instruction}\n\n### 응답\n"

        full_text = prompt + output_text

        encoded = self.tokenizer(
            full_text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encoded["input_ids"].squeeze()
        attention_mask = encoded["attention_mask"].squeeze()

        # 프롬프트 부분은 loss 계산에서 제외
        prompt_encoded = self.tokenizer(prompt, truncation=True, max_length=self.max_length)
        prompt_length = len(prompt_encoded["input_ids"])

        labels = input_ids.clone()
        labels[:prompt_length] = -100  # 프롬프트 마스킹

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


def setup_model_and_tokenizer(config: SFTConfig) -> tuple[Any, Any]:
    """모델 및 토크나이저 초기화 (QLoRA + DoRA)"""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, TaskType

    # 4-bit 양자화 설정 (QLoRA)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    logger.info(f"모델 로드 중: {config.base_model}")
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # LoRA/DoRA 설정
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_dora=config.use_dora,
    )

    model = get_peft_model(model, lora_config)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(
        f"학습 파라미터: {trainable_params:,} / {total_params:,} "
        f"({100 * trainable_params / total_params:.2f}%)"
    )

    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    return model, tokenizer


def train(config: SFTConfig, data_paths: list[str]) -> None:
    """SFT 학습 실행"""
    from transformers import TrainingArguments, Trainer

    # WandB 설정
    os.environ["WANDB_PROJECT"] = config.wandb_project

    model, tokenizer = setup_model_and_tokenizer(config)

    # 데이터셋 로드
    train_dataset = NaraInstructionDataset(data_paths[0], tokenizer, config.max_seq_length)

    # 학습 인자
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation,
        learning_rate=config.learning_rate,
        weight_decay=0.01,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        bf16=config.bf16,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=500,
        save_steps=500,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="wandb",
        deepspeed=config.deepspeed_config,
        gradient_checkpointing=config.gradient_checkpointing,
        dataloader_num_workers=4,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        tokenizer=tokenizer,
    )

    logger.info("SFT 학습 시작")
    trainer.train()

    # 최종 모델 저장
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    logger.info(f"모델 저장 완료: {config.output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NARA-AI SFT Trainer")
    parser.add_argument("--config", type=str, default="config/training/sft_config.yaml")
    parser.add_argument("--data_path", type=str, default="data/processed/sft/")
    parser.add_argument("--output_dir", type=str, default=None)
    parser.add_argument("--deepspeed", type=str, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    config = SFTConfig.from_yaml(args.config)
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.deepspeed:
        config.deepspeed_config = args.deepspeed

    train(config, [args.data_path])


if __name__ == "__main__":
    main()
