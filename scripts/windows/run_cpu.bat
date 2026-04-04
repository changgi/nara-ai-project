@echo off
chcp 65001 >nul 2>&1
title NARA-AI v1.0 - CPU 전용 모드 (RTX 3060 / 노트북)

echo.
echo ========================================
echo   NARA-AI v1.0 - CPU 전용 모드
echo   RTX 3060 / 노트북 환경용
echo ========================================
echo.
echo   GPU 추론 대신 CPU 기반으로 실행합니다:
echo   - 임베딩: TF-IDF (CPU) 또는 소형 모델
echo   - 검색: BM25 (CPU) + TF-IDF
echo   - OCR: 후처리만 (모델 추론 없음)
echo   - PII 탐지: 정규식 기반 (CPU)
echo.
echo   시작: %date% %time%
echo.

REM 환경 변수 설정
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%~dp0..\..
set PYTHONUTF8=1
set NARA_MODE=cpu
set CUDA_VISIBLE_DEVICES=
set TOKENIZERS_PARALLELISM=false

REM Python 확인
python --version 2>nul
if errorlevel 1 (
    echo   [실패] Python 미설치. setup.bat을 먼저 실행하세요.
    pause
    exit /b 1
)

echo ----------------------------------------
echo [1/5] CPU 전용 패키지 확인 중...
echo ----------------------------------------
python -c "import fastapi; import uvicorn; import httpx; print('  핵심 패키지 OK')" 2>nul
if errorlevel 1 (
    echo   패키지 설치 중...
    python -m pip install -r scripts\windows\requirements-cpu.txt -q --disable-pip-version-check
)
echo   [완료]
echo.

echo ----------------------------------------
echo [2/5] 디렉토리 확인 중...
echo ----------------------------------------
if not exist "data\test" mkdir "data\test"
if not exist "logs" mkdir "logs"
if not exist "_workspace\audit" mkdir "_workspace\audit"
echo   [완료]
echo.

echo ----------------------------------------
echo [3/5] 테스트 실행 중...
echo ----------------------------------------
python -m pytest tests\unit\test_pipeline.py tests\unit\test_redaction.py tests\unit\test_ocr_ensemble.py -q --tb=no 2>nul
if errorlevel 1 (
    echo   [경고] 일부 테스트 실패
) else (
    echo   [완료] 기본 테스트 통과
)
echo.

echo ----------------------------------------
echo [4/5] 데모 실행 중...
echo ----------------------------------------
echo.
echo --- PII 탐지 데모 ---
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from src.agents.redaction.agent import RedactionAgent
agent = RedactionAgent()
texts = [
    '홍길동(850101-1234567) 연락처 010-1234-5678',
    '이메일 test@example.com 여권 M12345678',
]
for t in texts:
    d = agent.detect_pii(t)
    m = agent.mask_content(t, d)
    print(f'  원본: {t}')
    print(f'  마스킹: {m}')
    print(f'  탐지: {len(d)}건')
    print()
"
echo.
echo --- OCR 후처리 데모 ---
python -c "
import sys; sys.stdout.reconfigure(encoding='utf-8')
from src.ocr.postprocess.corrector import OCRPostProcessor
p = OCRPostProcessor()
texts = ['행정안전뷰 공공기록뭄 지침', '國家記錄院 行政安全部']
for t in texts:
    r = p.correct(t)
    print(f'  원본: {t}')
    print(f'  교정: {r.corrected}')
    print()
"
echo.

echo ----------------------------------------
echo [5/5] CPU 임베딩 서버 시작 중...
echo ----------------------------------------
echo.
echo   접속 주소:
echo     임베딩 서버:  http://localhost:8002/health
echo     API 문서:     http://localhost:8002/docs
echo.
echo   추가 명령어:
echo     python src\main.py --mode status
echo     python src\main.py --mode benchmark
echo     python src\main.py --mode pii-demo
echo     python src\main.py --mode ocr-demo
echo.
echo   종료: Ctrl+C
echo.
echo ========================================

python -m uvicorn src.search.embedding.server:app --host 127.0.0.1 --port 8002 --reload

echo.
echo   서버 종료: %date% %time%
pause
