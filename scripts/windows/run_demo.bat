@echo off
chcp 65001 >nul 2>&1
title NARA-AI - 전체 데모

echo.
echo ========================================
echo   NARA-AI v1.0 - 전체 데모 실행
echo ========================================
echo.

set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0..\..
set PYTHONUTF8=1

python --version 2>nul
if errorlevel 1 (
    echo   [실패] Python 미설치
    pause
    exit /b 1
)

echo [1/4] 시스템 현황...
echo ----------------------------------------
python src\main.py --mode status
echo.

echo [2/4] PII 탐지 데모...
echo ----------------------------------------
python src\main.py --mode pii-demo
echo.

echo [3/4] OCR 후처리 데모...
echo ----------------------------------------
python src\main.py --mode ocr-demo
echo.

echo [4/4] 벤치마크...
echo ----------------------------------------
python src\main.py --mode benchmark
echo.

echo ========================================
echo   데모 완료!
echo ========================================
pause
