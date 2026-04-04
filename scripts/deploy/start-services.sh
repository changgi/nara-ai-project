#!/bin/bash
# NARA-AI 전체 서비스 시작 스크립트
# 에어갭(물리적 망분리) 환경용

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  NARA-AI 서비스 시작                               ║"
echo "║  AI 기반 국가기록물 지능형 검색·분류·활용 체계         ║"
echo "╚══════════════════════════════════════════════════╝"

# GPU 프로파일 선택
GPU_PROFILE="${1:-8}"
echo "GPU 프로파일: ${GPU_PROFILE} GPU"

cd "$PROJECT_ROOT"

# 1단계: 기반 서비스 (Milvus, 모니터링)
echo "[1/4] 기반 서비스 시작 (Milvus, 모니터링)..."
docker compose -f infra/docker/docker-compose.yml up -d \
  etcd minio milvus prometheus grafana

echo "  Milvus 헬스체크 대기..."
until curl -sf http://localhost:9091/healthz > /dev/null 2>&1; do
  sleep 5
done
echo "  Milvus 준비 완료"

# 2단계: AI 추론 서버 (GPU)
echo "[2/4] AI 추론 서버 시작 (vLLM + 임베딩)..."
docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.gpu.yml up -d \
  vllm-llm vllm-ocr embedding

echo "  vLLM 헬스체크 대기 (모델 로딩 중, 1~3분 소요)..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  sleep 10
done
echo "  vLLM LLM 서버 준비 완료"

# 3단계: MCP 서버
echo "[3/4] MCP 서버 시작 (5개)..."
docker compose -f infra/docker/docker-compose.yml up -d \
  mcp-archive mcp-iarna mcp-nara mcp-law mcp-ramp

# 4단계: 헬스체크
echo "[4/4] 전체 서비스 헬스체크..."
SERVICES=(
  "Milvus:19530:9091/healthz"
  "vLLM-LLM:8000:8000/health"
  "vLLM-OCR:8001:8001/health"
  "Embedding:8002:8002/health"
  "MCP-Archive:3001:3001/health"
  "MCP-IARNA:3002:3002/health"
  "Prometheus:9090:9090/-/healthy"
  "Grafana:3000:3000/api/health"
)

ALL_OK=true
for svc in "${SERVICES[@]}"; do
  IFS=':' read -r name port path <<< "$svc"
  if curl -sf "http://localhost:${path}" > /dev/null 2>&1; then
    echo "  ✓ ${name} (포트 ${port})"
  else
    echo "  ✗ ${name} (포트 ${port}) - 실패"
    ALL_OK=false
  fi
done

echo ""
if [ "$ALL_OK" = true ]; then
  echo "╔══════════════════════════════════════════════════╗"
  echo "║  모든 서비스 정상 가동                              ║"
  echo "║                                                  ║"
  echo "║  Grafana:    http://localhost:3000                ║"
  echo "║  Prometheus: http://localhost:9090                ║"
  echo "║  Milvus:     localhost:19530                      ║"
  echo "║  vLLM LLM:   http://localhost:8000                ║"
  echo "║  vLLM OCR:   http://localhost:8001                ║"
  echo "║  Embedding:  http://localhost:8002                ║"
  echo "╚══════════════════════════════════════════════════╝"
else
  echo "⚠ 일부 서비스가 시작되지 않았습니다. 로그를 확인하세요."
  echo "  docker compose -f infra/docker/docker-compose.yml logs"
  exit 1
fi
