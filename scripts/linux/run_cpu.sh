#!/bin/bash
# NARA-AI CPU 전용 모드 실행 (Linux)
set -euo pipefail
export LANG=ko_KR.UTF-8
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export NARA_MODE=cpu
export CUDA_VISIBLE_DEVICES=""

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

echo ""
echo "========================================"
echo "  NARA-AI v1.0 - CPU 전용 모드"
echo "  GPU 비활성화, TF-IDF + BM25 검색"
echo "========================================"
echo ""

# CPU 정보
python3 -c "
from config.hardware_profiles import detect_cpu
cpu = detect_cpu()
print(f'  CPU: {cpu.name} ({cpu.cores}코어, {cpu.arch.value})')
print(f'  검색 모드: {cpu.search_mode}')
" 2>/dev/null || echo "  CPU 감지 실패"

echo ""
echo "서버 시작: http://localhost:8080"
echo "종료: Ctrl+C"
echo "========================================"
echo ""

python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8080 --reload
