---
name: model-training
description: "한국어 LLM 파인튜닝 및 학습 파이프라인 구축 스킬. EXAONE 3.5, Solar Pro 2, Qwen 2.5 등 한국어 LLM의 CPT/SFT/DPO 3단계 학습, DeepSpeed ZeRO-3/FSDP2 분산 학습 설정, QLoRA+DoRA 경량 학습, vLLM 추론 서빙, WandB 실험 추적을 수행한다. '모델 학습', '파인튜닝', 'fine-tuning', 'SFT', 'DPO', 'RLHF', 'DeepSpeed', 'FSDP', '학습 설정', '추론 서버', 'vLLM', '체크포인트' 관련 작업 시 반드시 이 스킬을 사용할 것."
---

# 모델 학습 파이프라인 구축

국가기록원 도메인에 특화된 한국어 LLM을 학습하고 배포하는 파이프라인을 구축한다.

## 3단계 학습 전략

### Stage 1: Continued Pre-Training (CPT)
- **목적**: 정부 문서/기록물 도메인 적응
- **데이터**: 50-100B 토큰 (정부 기록물 코퍼스)
- **프레임워크**: FSDP2 (TorchTitan) + Megatron-LM
- **GPU**: 16장 (텐서 병렬 4 x 파이프라인 병렬 4)
- **HanjaBridge**: 한자 문맥 해소 기법 적용 (+21% 성능)

### Stage 2: Supervised Fine-Tuning (SFT)
- **목적**: 과업별 명령어 튜닝
- **데이터셋**:
  - `classification-50k.jsonl`: 기록물 분류 (BRM 업무기능 매핑)
  - `metadata-gen-30k.jsonl`: 메타데이터 자동 생성
  - `redaction-20k.jsonl`: 비밀해제 심사 지원
  - `ocr-korean-archive-100k.jsonl`: OCR 이미지-텍스트 쌍
- **프레임워크**: QLoRA (4-bit) + DoRA (weight-decomposed)
- **GPU**: 4-8장

### Stage 3: Direct Preference Optimization (DPO)
- **목적**: 기록물 관리 전문가 피드백 정렬
- **데이터**: `expert-feedback-5k.jsonl` (chosen/rejected 쌍)
- **프레임워크**: DeepSpeed ZeRO-3
- **GPU**: 8장

## 모델 선택 가이드

| 모델 | 크기 | 강점 | 용도 |
|------|------|------|------|
| EXAONE 3.5 | 8B | 오픈소스, 한국어 네이티브 | 분류/메타데이터 기본 모델 |
| Solar Pro 2 | 31B | 프론티어 성능 | 복잡한 추론 작업 |
| Qwen 2.5 | 7B/72B | 한자/CJK 지원 우수 | 한자 혼용 문서 |
| Llama 3.1 | 8B/70B | 커뮤니티 생태계 | Korean CPT 후보 |

## 학습 설정 파일 구조

```python
# config/training/sft_config.yaml
model:
  base: "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
  quantization: "qlora-4bit"  # QLoRA 4-bit
  lora_rank: 64
  lora_alpha: 128
  target_modules: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

training:
  epochs: 3
  batch_size: 4
  gradient_accumulation: 8
  learning_rate: 2e-4
  warmup_ratio: 0.1
  max_seq_length: 4096
  bf16: true
  gradient_checkpointing: true

deepspeed:
  config: "config/ds_zero3.json"

wandb:
  project: "nara-ai-sft"
  tags: ["classification", "exaone-3.5"]
```

## vLLM 추론 서빙 설정

```python
# src/pipeline/serve/vllm_config.py
VLLM_CONFIG = {
    "llm": {
        "model": "checkpoints/nara-classifier-v1",
        "port": 8000,
        "tensor_parallel_size": 2,
        "max_model_len": 4096,
        "gpu_memory_utilization": 0.90,
        "dtype": "bfloat16",
    },
    "ocr": {
        "model": "Qwen/Qwen3-VL-8B",
        "port": 8001,
        "tensor_parallel_size": 1,
        "max_model_len": 8192,
    },
    "embedding": {
        "model": "upskyy/bge-m3-korean",
        "port": 8002,
        "dtype": "float16",
    }
}
```

## 성능 목표 및 평가 메트릭

| 과업 | 메트릭 | 목표 | 평가 데이터 |
|------|--------|------|-----------|
| 기록물 분류 | F1 Score | ≥ 0.92 | classification test set |
| 메타데이터 생성 | ROUGE-1 | ≥ 0.85 | metadata test set |
| 비밀해제 심사 | Precision | ≥ 0.95 | redaction test set |
| OCR (활자) | CER | ≤ 3% | printed doc test set |
| OCR (필사) | CER | ≤ 10% | handwritten test set |
| OCR (한자혼용) | CER | ≤ 7% | hanja-mixed test set |

## 학습 실행 스크립트

```bash
# scripts/train_sft.sh
#!/bin/bash
export CUDA_VISIBLE_DEVICES=0,1,2,3
export WANDB_PROJECT="nara-ai-sft"

torchrun --nproc_per_node=4 \
  src/pipeline/train/sft_trainer.py \
  --config config/training/sft_config.yaml \
  --data_path data/processed/sft/ \
  --output_dir checkpoints/nara-classifier-v1 \
  --deepspeed config/ds_zero3.json
```

## 체크포인트 관리

- 학습 중 매 500 step마다 체크포인트 저장
- 최선 3개 체크포인트만 유지 (eval loss 기준)
- 최종 모델은 ONNX + TorchScript 형식으로 내보내기
- MLflow Registry에 시맨틱 버전으로 등록 (v1.0.0-sft, v1.0.0-dpo)
