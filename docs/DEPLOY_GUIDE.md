# NARA-AI 유니버설 배포 가이드

하나의 코드가 로컬 / Vercel / AWS Lambda / Docker 어디서든 동작합니다.

## 아키텍처

```
api/app.py (통합 FastAPI 앱)
    │
    ├── 로컬: python -m uvicorn api.app:app
    ├── Vercel: api/index.py → from api.app import app
    ├── AWS Lambda: api/lambda_handler.py → Mangum(app)
    └── Docker: uvicorn api.app:app --host 0.0.0.0
```

환경 자동 감지: `VERCEL=1` → Vercel, `AWS_LAMBDA_*` → Lambda, `/.dockerenv` → Docker

## 1. 로컬 실행

### Windows
```
setup.bat                                    # 초기 설정
python scripts\data\index_demo_data.py       # 데이터 인덱싱
run.bat                                      # 서버 시작
```

### Linux / macOS
```bash
bash scripts/linux/setup.sh
python3 scripts/data/index_demo_data.py
bash run.sh
```

### 직접 실행
```bash
PYTHONPATH=. python -m uvicorn api.app:app --host 127.0.0.1 --port 8080 --reload
```

접속: http://localhost:8080

## 2. Vercel 배포

```bash
# GitHub push 시 자동 배포 (권장)
git push origin main

# 또는 수동 배포
vercel deploy --prod
```

접속: https://nara-ai-project.vercel.app

## 3. Docker 배포

### 빌드 및 실행
```bash
docker build -f infra/docker/Dockerfile.cpu -t nara-ai .
docker run -p 8080:8080 nara-ai
```

### Docker Compose (전체 스택)
```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

접속: http://localhost:8080

## 4. AWS Lambda 배포

### 방법 A: SAM CLI (권장)
```bash
pip install aws-sam-cli
cd aws
sam build --template template.yaml
sam deploy --guided --stack-name nara-ai --region ap-northeast-2
```

### 방법 B: Docker Lambda
```bash
docker build -f aws/Dockerfile -t nara-ai-lambda .
# ECR에 push 후 Lambda 함수 생성
```

### 방법 C: ZIP 패키지
```bash
pip install mangum fastapi pydantic httpx -t package/
cp -r api/ config/ src/ package/
cd package && zip -r ../nara-ai-lambda.zip .
# Lambda 함수에 업로드, 핸들러: api.lambda_handler.handler
```

## 5. AWS ECS/Fargate

```bash
# Docker 이미지 빌드
docker build -f infra/docker/Dockerfile.cpu -t nara-ai .

# ECR에 push
aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin {ACCOUNT}.dkr.ecr.ap-northeast-2.amazonaws.com
docker tag nara-ai {ACCOUNT}.dkr.ecr.ap-northeast-2.amazonaws.com/nara-ai:latest
docker push {ACCOUNT}.dkr.ecr.ap-northeast-2.amazonaws.com/nara-ai:latest

# ECS 서비스 생성 (AWS 콘솔 또는 CLI)
```

## API 엔드포인트

모든 환경에서 동일한 API:

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | / | 웹 UI |
| GET | /health | 헬스체크 (환경 감지 포함) |
| GET | /status | 시스템 현황 |
| POST | /search | 기록물 검색 |
| POST | /pii/detect | PII 탐지 + 마스킹 |
| POST | /ocr/correct | OCR 후처리 교정 |
| GET | /docs | Swagger API 문서 |

## 환경별 검색 모드

| 환경 | 검색 방식 |
|------|----------|
| 로컬 (CPU 인덱스 있음) | TF-IDF + BM25 (1~2ms) |
| 로컬 (GPU) | Milvus 벡터 검색 |
| Vercel / AWS Lambda | Supabase REST API |
| Docker | CPU 인덱스 또는 Milvus |
