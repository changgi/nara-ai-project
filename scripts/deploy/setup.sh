#!/bin/bash
# NARA-AI 초기 환경 설정 스크립트
# 에어갭 환경에서 실행 전 사전 준비

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  NARA-AI 초기 환경 설정                            ║"
echo "╚══════════════════════════════════════════════════╝"

cd "$PROJECT_ROOT"

# 1. 디렉토리 구조 생성
echo "[1/6] 디렉토리 구조 생성..."
dirs=(
  "data/raw/electronic" "data/raw/non-electronic" "data/raw/ocr-gt"
  "data/processed/sft" "data/processed/dpo" "data/processed/tokens"
  "data/embeddings" "data/test"
  "checkpoints" "logs"
  "_workspace/audit"
)
for d in "${dirs[@]}"; do
  mkdir -p "$d"
done
echo "  완료"

# 2. Python 의존성 확인
echo "[2/6] Python 의존성 확인..."
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version 2>&1)
  echo "  Python: $PY_VER"
  pip install -r requirements-ml.txt 2>/dev/null || echo "  ⚠ 일부 의존성 설치 실패 (GPU 없는 환경에서 정상)"
else
  echo "  ⚠ Python3 미설치"
fi

# 3. Node.js 의존성 확인
echo "[3/6] Node.js 의존성 확인..."
if command -v node &>/dev/null; then
  NODE_VER=$(node --version)
  echo "  Node.js: $NODE_VER"
  npm ci 2>/dev/null || npm install 2>/dev/null || echo "  ⚠ npm 의존성 설치 실패"
else
  echo "  ⚠ Node.js 미설치"
fi

# 4. Docker 확인
echo "[4/6] Docker 확인..."
if command -v docker &>/dev/null; then
  DOCKER_VER=$(docker --version)
  echo "  $DOCKER_VER"
else
  echo "  ⚠ Docker 미설치"
fi

# 5. GPU 확인
echo "[5/6] GPU 확인..."
if command -v nvidia-smi &>/dev/null; then
  GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
  echo "  GPU: ${GPU_COUNT}x ${GPU_NAME}"
else
  echo "  ⚠ NVIDIA GPU 미감지 (nvidia-smi 없음)"
fi

# 6. 환경 변수 설정
echo "[6/6] 환경 변수 확인..."
if [ ! -f ".env" ]; then
  if [ -f ".env.production" ]; then
    cp .env.production .env
    echo "  .env.production → .env 복사 (⚠ 비밀키를 변경하세요)"
  elif [ -f ".env.example" ]; then
    cp .env.example .env
    echo "  .env.example → .env 복사"
  fi
else
  echo "  .env 존재"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  초기 설정 완료                                    ║"
echo "║                                                  ║"
echo "║  다음 단계:                                       ║"
echo "║  1. .env 파일의 비밀키 변경                        ║"
echo "║  2. 학습 데이터를 data/raw/에 배치                  ║"
echo "║  3. bash scripts/deploy/start-services.sh         ║"
echo "╚══════════════════════════════════════════════════╝"
