#!/bin/bash
# NARA-AI AWS Lambda 배포 스크립트
set -euo pipefail

echo "=== NARA-AI AWS Lambda 배포 ==="

# 방법 1: SAM CLI (권장)
if command -v sam &>/dev/null; then
    echo "[SAM] 빌드 및 배포..."
    cd "$(dirname "$0")"
    sam build --template template.yaml
    sam deploy --guided \
        --stack-name nara-ai \
        --capabilities CAPABILITY_IAM \
        --region ap-northeast-2
    echo "배포 완료!"
    exit 0
fi

# 방법 2: Docker Lambda
if command -v docker &>/dev/null; then
    echo "[Docker] Lambda 컨테이너 빌드..."
    cd "$(dirname "$0")/.."
    docker build -f aws/Dockerfile -t nara-ai-lambda .
    echo ""
    echo "ECR에 push하려면:"
    echo "  aws ecr get-login-password | docker login --username AWS --password-stdin {ACCOUNT}.dkr.ecr.ap-northeast-2.amazonaws.com"
    echo "  docker tag nara-ai-lambda {ACCOUNT}.dkr.ecr.ap-northeast-2.amazonaws.com/nara-ai:latest"
    echo "  docker push {ACCOUNT}.dkr.ecr.ap-northeast-2.amazonaws.com/nara-ai:latest"
    exit 0
fi

echo "[오류] sam 또는 docker가 필요합니다."
echo "  SAM: pip install aws-sam-cli"
echo "  Docker: https://docs.docker.com/get-docker/"
exit 1
