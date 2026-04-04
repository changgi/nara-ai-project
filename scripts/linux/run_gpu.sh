#!/bin/bash
# NARA-AI GPU 모드 실행 (Linux)
set -euo pipefail
export LANG=ko_KR.UTF-8
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

echo ""
echo "========================================"
echo "  NARA-AI v1.0 - GPU 모드"
echo "========================================"
echo ""

# GPU 감지
python3 -c "
from config.hardware_profiles import detect_system, print_system_report
profile = detect_system()
print_system_report(profile)
" 2>/dev/null || echo "  [경고] 하드웨어 감지 실패"

echo ""
echo "서버 시작: http://localhost:8080"
echo "종료: Ctrl+C"
echo "========================================"
echo ""

python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8080 --reload
