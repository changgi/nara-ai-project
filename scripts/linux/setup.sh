#!/bin/bash
# NARA-AI 초기 설정 (Linux/macOS)
# UTF-8 한글 지원

set -euo pipefail
export LANG=ko_KR.UTF-8
export LC_ALL=ko_KR.UTF-8
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "========================================"
echo "  NARA-AI 초기 설정"
echo "  AI 기반 국가기록물 지능형 검색/분류/활용"
echo "========================================"
echo ""

# 1. Python 확인
echo "[1/5] Python 확인..."
if ! command -v python3 &>/dev/null; then
    echo "  [실패] Python3 미설치"
    echo "  Ubuntu: sudo apt install python3 python3-pip python3-venv"
    echo "  macOS:  brew install python3"
    exit 1
fi
PY_VER=$(python3 --version)
echo "  [완료] $PY_VER"

# 2. 환경 변수
echo "[2/5] 환경 변수 설정..."
if [ ! -f ".env" ]; then
    for tmpl in .env.production .env.example; do
        if [ -f "$tmpl" ]; then
            cp "$tmpl" .env
            echo "  $tmpl -> .env 복사됨 (비밀키 변경 필요)"
            break
        fi
    done
fi
echo "  [완료]"

# 3. 디렉토리 생성
echo "[3/5] 디렉토리 생성..."
dirs=(data/raw/electronic data/raw/non-electronic data/raw/ocr-gt
      data/processed/sft data/processed/dpo data/test data/embeddings data/db
      checkpoints logs _workspace/audit)
for d in "${dirs[@]}"; do
    mkdir -p "$d"
done
echo "  [완료]"

# 4. GPU 감지 및 의존성 설치
echo "[4/5] GPU 감지 및 패키지 설치..."

GPU_TYPE="cpu"
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
    echo "  NVIDIA GPU: ${GPU_COUNT}x ${GPU_NAME}"
    GPU_TYPE="nvidia"
elif command -v rocm-smi &>/dev/null; then
    echo "  AMD GPU (ROCm) 감지"
    GPU_TYPE="rocm"
else
    echo "  GPU 미감지 → CPU 모드"
fi

python3 -m pip install --upgrade pip -q --disable-pip-version-check

case "$GPU_TYPE" in
    nvidia)
        echo "  NVIDIA CUDA 패키지 설치 중..."
        python3 -m pip install -r requirements-ml.txt -q --disable-pip-version-check 2>/dev/null || \
        python3 -m pip install -r scripts/windows/requirements-cpu.txt -q --disable-pip-version-check
        ;;
    rocm)
        echo "  AMD ROCm 패키지 설치 중..."
        if [ -f "requirements-rocm.txt" ]; then
            python3 -m pip install -r requirements-rocm.txt -q --disable-pip-version-check
        else
            python3 -m pip install -r scripts/windows/requirements-cpu.txt -q --disable-pip-version-check
        fi
        ;;
    cpu)
        echo "  CPU 전용 패키지 설치 중..."
        python3 -m pip install -r scripts/windows/requirements-cpu.txt -q --disable-pip-version-check
        ;;
esac
echo "  [완료]"

# 5. Node.js (선택)
echo "[5/5] Node.js 확인..."
if command -v node &>/dev/null; then
    echo "  Node.js $(node --version)"
    [ -f "package.json" ] && npm install --silent 2>/dev/null || true
else
    echo "  [정보] Node.js 미설치. MCP 서버 사용 시 필요."
fi
echo "  [완료]"

echo ""
echo "========================================"
echo "  초기 설정 완료!"
echo ""
echo "  다음 단계:"
echo "    1. nano .env  (비밀키 변경)"
echo "    2. bash scripts/linux/run_gpu.sh  (GPU 모드)"
echo "    3. bash scripts/linux/run_cpu.sh  (CPU 모드)"
echo "========================================"
