@echo off
chcp 65001 >nul 2>&1
title NARA-AI v1.0 - 서버 실행

echo.
echo ========================================
echo   NARA-AI v1.0
echo   AI 기반 국가기록물 지능형 검색/분류/활용
echo   행정안전부 / 국가기록원
echo ========================================
echo.
echo   시작: %date% %time%
echo.

REM Python 확인
python --version 2>nul
if errorlevel 1 (
    echo   [실패] Python 미설치. setup.bat을 먼저 실행하세요.
    pause
    exit /b 1
)

REM 환경 변수
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0..\..
set PYTHONUTF8=1

REM GPU 확인
echo ----------------------------------------
echo [1/4] GPU 확인 중...
echo ----------------------------------------
python -c "import torch; print(f'  PyTorch: {torch.__version__}'); print(f'  CUDA: {torch.cuda.is_available()}'); print(f'  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"없음\"}')" 2>nul
if errorlevel 1 (
    echo   [정보] PyTorch 미설치 또는 CUDA 미감지
    echo   CPU 모드로 실행합니다. run_cpu.bat 사용을 권장합니다.
)
echo.

REM 디렉토리 확인
echo ----------------------------------------
echo [2/4] 디렉토리 확인 중...
echo ----------------------------------------
if not exist "data" mkdir "data"
if not exist "logs" mkdir "logs"
if not exist "_workspace\audit" mkdir "_workspace\audit"
echo   [완료]
echo.

REM 벤치마크 실행
echo ----------------------------------------
echo [3/4] 벤치마크 실행 중...
echo ----------------------------------------
python -m pytest tests\unit\ -q --tb=no 2>nul
if errorlevel 1 (
    echo   [경고] 일부 테스트 실패. 서버는 계속 시작합니다.
) else (
    echo   [완료] 테스트 통과
)
echo.

REM 서버 시작
echo ----------------------------------------
echo [4/4] 서버 시작 중...
echo ----------------------------------------
echo.
echo   접속 주소:
echo     임베딩 서버:  http://localhost:8002
echo     시스템 현황:  python src\main.py --mode status
echo     PII 데모:     python src\main.py --mode pii-demo
echo     OCR 데모:     python src\main.py --mode ocr-demo
echo     벤치마크:     python src\main.py --mode benchmark
echo.
echo   종료: Ctrl+C
echo.
echo ========================================

python -m uvicorn src.search.embedding.server:app --host 127.0.0.1 --port 8002 --reload

echo.
echo ========================================
echo   서버 종료: %date% %time%
echo ========================================
pause
