@echo off
chcp 65001 >nul 2>&1
title NARA-AI - 테스트 실행

echo.
echo ========================================
echo   NARA-AI v1.0 - 전체 테스트
echo ========================================
echo.

set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0..\..
set PYTHONUTF8=1

echo [1/2] 단위 테스트...
echo ----------------------------------------
python -m pytest tests\unit\ -v --tb=short
echo.

echo [2/2] 통합 테스트 (경계면 검증)...
echo ----------------------------------------
python -m pytest tests\integration\ -v --tb=short -k "not health and not connection"
echo.

echo ========================================
echo   테스트 완료!
echo ========================================
pause
