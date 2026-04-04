#!/bin/bash
# BRM 주기 수집 (Linux cron용)
# crontab -e → 0 3 * * * /path/to/collect_brm.sh
export LANG=ko_KR.UTF-8
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
cd "$(dirname "$0")/../.."
export PYTHONPATH="$(pwd)"
echo "BRM 수집 시작: $(date)"
python3 -m src.brm.collector --source api
echo "BRM 수집 완료: $(date)"
