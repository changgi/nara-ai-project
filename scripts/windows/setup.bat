@echo off
chcp 65001 >nul 2>&1
title NARA-AI - 초기 설정

echo.
echo ========================================
echo   NARA-AI 초기 설정
echo   국가기록원 AI 지능형 기록물 관리 시스템
echo ========================================
echo.
echo   시작: %date% %time%
echo.

REM Step 1: Python
echo ----------------------------------------
echo [1/6] Python 확인 중...
echo ----------------------------------------
python --version 2>nul
if errorlevel 1 (
    echo.
    echo   [실패] Python이 설치되어 있지 않습니다.
    echo.
    echo   Python 3.11 이상을 설치하세요:
    echo     https://www.python.org/downloads/
    echo.
    echo   중요: 설치 시 "Add Python to PATH" 반드시 체크!
    echo.
    pause
    exit /b 1
)
echo   [완료] Python 확인
echo.

REM Step 2: .env
echo ----------------------------------------
echo [2/6] 환경 변수 설정 (.env)
echo ----------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo   .env.example 복사 완료
    ) else if exist ".env.production" (
        copy ".env.production" ".env" >nul
        echo   .env.production 복사 완료
    ) else (
        echo   [경고] .env 템플릿 없음. 수동 생성 필요.
    )
    echo   .env 파일의 비밀키를 변경하세요!
) else (
    echo   .env 파일 존재
)
echo   [완료]
echo.

REM Step 3: Directories
echo ----------------------------------------
echo [3/6] 디렉토리 생성 중...
echo ----------------------------------------
if not exist "data\raw\electronic" mkdir "data\raw\electronic"
if not exist "data\raw\non-electronic" mkdir "data\raw\non-electronic"
if not exist "data\raw\ocr-gt" mkdir "data\raw\ocr-gt"
if not exist "data\processed\sft" mkdir "data\processed\sft"
if not exist "data\processed\dpo" mkdir "data\processed\dpo"
if not exist "data\test" mkdir "data\test"
if not exist "data\embeddings" mkdir "data\embeddings"
if not exist "checkpoints" mkdir "checkpoints"
if not exist "logs" mkdir "logs"
if not exist "_workspace\audit" mkdir "_workspace\audit"
echo   모든 디렉토리 생성 완료
echo   [완료]
echo.

REM Step 4: pip upgrade
echo ----------------------------------------
echo [4/6] pip 업그레이드 중...
echo ----------------------------------------
python -m pip install --upgrade pip --disable-pip-version-check -q
echo   [완료]
echo.

REM Step 5: Install packages
echo ----------------------------------------
echo [5/6] Python 패키지 설치 중...
echo       (처음 실행 시 2~5분 소요)
echo ----------------------------------------
echo.
python -m pip install -r requirements-ml.txt --disable-pip-version-check -q 2>nul
if errorlevel 1 (
    echo   [경고] 일부 ML 패키지 설치 실패 (GPU 없는 환경에서 정상)
    echo   CPU 전용 패키지를 설치합니다...
    python -m pip install -r scripts\windows\requirements-cpu.txt --disable-pip-version-check -q 2>nul
)
echo   [완료]
echo.

REM Step 6: Node.js
echo ----------------------------------------
echo [6/6] Node.js 확인 중...
echo ----------------------------------------
node --version 2>nul
if errorlevel 1 (
    echo   [경고] Node.js 미설치. MCP 서버 사용 시 필요합니다.
    echo   설치: https://nodejs.org/
) else (
    echo   Node.js 확인 완료
    if exist "package.json" (
        call npm install --silent 2>nul
        echo   npm 패키지 설치 완료
    )
)
echo   [완료]
echo.

echo ========================================
echo.
echo   초기 설정 완료!
echo.
echo   완료 시각: %date% %time%
echo.
echo   다음 단계:
echo     1. .env 파일에서 비밀키 변경
echo     2. 학습 데이터를 data\raw\ 에 배치
echo     3. run.bat 실행 (서버 시작)
echo     4. run_cpu.bat 실행 (CPU 전용 모드)
echo.
echo ========================================
echo.
pause
