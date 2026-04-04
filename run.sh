#!/bin/bash
# NARA-AI 크로스 플랫폼 런처 (Linux/macOS 바로가기)
export LANG=ko_KR.UTF-8
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

cd "$(dirname "${BASH_SOURCE[0]}")"
export PYTHONPATH="$(pwd)"
python3 run.py "$@"
