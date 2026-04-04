"""
NARA-AI DPO 학습 파이프라인

기록물 관리 전문가의 피드백(chosen/rejected 쌍)으로
SFT 모델을 정렬(alignment)한다.

Direct Preference Optimization (DPO):
- SFT 완료 모델을 base로 사용
- 5,000건 전문가 피드백으로 정렬
- beta=0.1 (KL divergence 가중치)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import yaml
from torch.utils.data import Dataset

logger = logging.getLogger("nara-ai.train.dpo")


@dataclass
class DPOConfig:
    """DPO 학습 설정"""
    base_model: str = "checkpoints/nara-sft-v1"
    output_dir: str = "checkpoints/nara-dpo-v1"
    epochs: int = 1
    batch_size: int = 2
    gradient_accumulation: int = 16
    learning_rate: float = 5e-5
    beta: float = 0.1
    max_seq_length: int = 4096
    lora_rank: int = 32
    lora_alpha: int = 64
    use_dora: bool = True
    deepspeed_config: str | None = None
    wandb_project: str = "nara-ai-dpo"

    @classmethod
    def from_yaml(cls, path: str) -> "DPOConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            base_model=data.get("model", {}).get("base_model", cls.base_model),
            output_dir=data.get("output", {}).get("output_dir", cls.output_dir),
            epochs=data.get("training", {}).get("epochs", cls.epochs),
            batch_size=data.get("training", {}).get("per_device_batch_size", cls.batch_size),
            gradient_accumulation=data.get("training", {}).get("gradient_accumulation_steps", cls.gradient_accumulation),
            learning_rate=data.get("training", {}).get("learning_rate", cls.learning_rate),
            beta=data.get("training", {}).get("beta", cls.beta),
            lora_rank=data.get("model", {}).get("lora", {}).get("rank", cls.lora_rank),
            deepspeed_config=data.get("deepspeed", {}).get("config_path"),
        )


class PreferenceDataset(Dataset):
    """DPO 선호도 데이터셋

    각 행: {"prompt": "...", "chosen": "...", "rejected": "..."}
    chosen: 전문가가 선호한 응답
    rejected: 전문가가 비선호한 응답
    """

    def __init__(self, data_path: str, tokenizer: Any, max_length: int = 4096):
        self.data: list[dict[str, str]] = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    if "prompt" in item and "chosen" in item and "rejected" in item:
                        self.data.append(item)

        logger.info(f"DPO 데이터셋 로드: {len(self.data)}건")

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.data[idx]
        return {
            "prompt": item["prompt"],
            "chosen": item["chosen"],
            "rejected": item["rejected"],
        }


def train_dpo(config: DPOConfig, data_path: str) -> None:
    """DPO 학습 실행"""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, TaskType
    from trl import DPOTrainer, DPOConfig as TRLDPOConfig

    os.environ["WANDB_PROJECT"] = config.wandb_project

    # 4-bit 양자화
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    logger.info(f"DPO 기반 모델 로드: {config.base_model}")
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(config.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # LoRA/DoRA
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        use_dora=config.use_dora,
    )

    # 데이터셋
    dataset = PreferenceDataset(data_path, tokenizer, config.max_seq_length)

    # DPO 학습 설정
    training_args = TRLDPOConfig(
        output_dir=config.output_dir,
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation,
        learning_rate=config.learning_rate,
        beta=config.beta,
        bf16=True,
        logging_steps=10,
        save_steps=500,
        save_total_limit=2,
        report_to="wandb",
        deepspeed=config.deepspeed_config,
        gradient_checkpointing=True,
        remove_unused_columns=False,
    )

    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        peft_config=peft_config,
    )

    logger.info("DPO 학습 시작")
    trainer.train()
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    logger.info(f"DPO 모델 저장: {config.output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NARA-AI DPO Trainer")
    parser.add_argument("--config", default="config/training/dpo_config.yaml")
    parser.add_argument("--data_path", default="data/processed/dpo/expert-feedback-5k.jsonl")
    parser.add_argument("--deepspeed", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    config = DPOConfig.from_yaml(args.config)
    if args.deepspeed:
        config.deepspeed_config = args.deepspeed
    train_dpo(config, args.data_path)


if __name__ == "__main__":
    main()
