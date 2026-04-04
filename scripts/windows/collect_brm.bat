@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONPATH=%~dp0..\..

echo BRM 수집 시작: %date% %time%
python -m src.brm.collector --source api
echo BRM 수집 완료: %date% %time%
