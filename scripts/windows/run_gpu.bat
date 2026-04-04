@echo off
chcp 65001 >nul 2>&1
title NARA-AI v1.0 - GPU 모드

echo.
echo ========================================
echo   NARA-AI v1.0 - GPU 모드
echo   하드웨어 자동 감지 + 최적 설정
echo ========================================
echo.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONPATH=%~dp0..\..

cd /d "%~dp0..\.."

echo [1/3] 하드웨어 감지 중...
echo ----------------------------------------
python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); from config.hardware_profiles import detect_system, print_system_report; p = detect_system(); print_system_report(p)"
echo.

echo [2/3] vLLM 서빙 계획...
echo ----------------------------------------
python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); from config.hardware_profiles import detect_system; from src.pipeline.serve.vllm_config import get_serving_configs_adaptive, print_serving_plan; print_serving_plan(get_serving_configs_adaptive(detect_system()))"
echo.

echo [3/3] 서버 시작...
echo ----------------------------------------
echo.
echo   웹 UI:    http://localhost:8080
echo   API 문서: http://localhost:8080/docs
echo   헬스체크: http://localhost:8080/health
echo.
echo   종료: Ctrl+C
echo ========================================

python -m uvicorn api.server:app --host 127.0.0.1 --port 8080 --reload

echo.
echo   서버 종료: %date% %time%
pause
