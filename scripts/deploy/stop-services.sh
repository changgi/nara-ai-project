#!/bin/bash
# NARA-AI 전체 서비스 중지 스크립트
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "NARA-AI 서비스 중지 중..."

docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.gpu.yml down

echo "모든 서비스가 중지되었습니다."
