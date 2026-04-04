# NARA-AI ML 학습/추론 Docker 이미지
# CUDA 12.8 + PyTorch 2.6 + vLLM + 학습 프레임워크

FROM nvidia/cuda:12.8.0-devel-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    git curl wget \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app

# Python 의존성
COPY requirements-ml.txt ./
RUN pip3 install --no-cache-dir -r requirements-ml.txt

# 소스 코드
COPY src/ ./src/
COPY config/ ./config/

# 모델 체크포인트 마운트 포인트
VOLUME ["/models", "/data"]

EXPOSE 8000 8001 8002

# 기본: 임베딩 서버
CMD ["python3", "-m", "uvicorn", "src.search.embedding.server:app", "--host", "0.0.0.0", "--port", "8002"]
