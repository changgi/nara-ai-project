#!/bin/bash
# NARA-AI SFT 학습 실행 스크립트
# EXAONE 3.5 8B → 기록물 분류/메타데이터/비밀해제 파인튜닝

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  NARA-AI SFT 학습 시작                            ║"
echo "║  모델: EXAONE 3.5 7.8B + QLoRA(r=64) + DoRA      ║"
echo "╚══════════════════════════════════════════════════╝"

# GPU 설정
GPU_COUNT="${1:-4}"
echo "GPU: ${GPU_COUNT}장"

export CUDA_VISIBLE_DEVICES=$(seq -s, 0 $((GPU_COUNT-1)))
export WANDB_PROJECT="nara-ai-sft"
export WANDB_MODE="${WANDB_MODE:-offline}"  # 에어갭: offline

cd "$PROJECT_ROOT"

# 데이터 확인
for f in data/processed/sft/classification-50k.jsonl data/processed/sft/metadata-gen-30k.jsonl data/processed/sft/redaction-20k.jsonl; do
  if [ ! -f "$f" ]; then
    echo "⚠ 학습 데이터 없음: $f"
    echo "  데이터를 먼저 준비하세요."
    exit 1
  fi
done

echo "[1/3] 분류 SFT 학습..."
torchrun --nproc_per_node=$GPU_COUNT \
  src/pipeline/train/sft_trainer.py \
  --config config/training/sft_config.yaml \
  --data_path data/processed/sft/classification-50k.jsonl \
  --output_dir checkpoints/nara-classifier-v1 \
  --deepspeed config/ds_zero3.json

echo "[2/3] 메타데이터 SFT 학습..."
torchrun --nproc_per_node=$GPU_COUNT \
  src/pipeline/train/sft_trainer.py \
  --config config/training/sft_config.yaml \
  --data_path data/processed/sft/metadata-gen-30k.jsonl \
  --output_dir checkpoints/nara-metadata-v1 \
  --deepspeed config/ds_zero3.json

echo "[3/3] 비밀해제 SFT 학습..."
torchrun --nproc_per_node=$GPU_COUNT \
  src/pipeline/train/sft_trainer.py \
  --config config/training/sft_config.yaml \
  --data_path data/processed/sft/redaction-20k.jsonl \
  --output_dir checkpoints/nara-redaction-v1 \
  --deepspeed config/ds_zero3.json

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  SFT 학습 완료                                    ║"
echo "║  체크포인트:                                       ║"
echo "║  - checkpoints/nara-classifier-v1                 ║"
echo "║  - checkpoints/nara-metadata-v1                   ║"
echo "║  - checkpoints/nara-redaction-v1                  ║"
echo "╚══════════════════════════════════════════════════╝"
