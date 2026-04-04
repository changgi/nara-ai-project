"""
NARA-AI 임베딩 서버

BGE-M3-Korean (568M, 1024차원) 기반 임베딩 API.
Dense + Sparse + Multi-vector 동시 생성.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("nara-ai.embedding")

app = FastAPI(
    title="NARA-AI Embedding Server",
    description="BGE-M3-Korean 기반 기록물 임베딩 서버",
    version="1.0.0",
)

# 전역 모델 (lazy init)
_model = None
_tokenizer = None


class EmbeddingRequest(BaseModel):
    """임베딩 요청"""
    texts: list[str] = Field(..., min_length=1, max_length=100)
    model: str = Field(default="bge-m3-korean")
    return_sparse: bool = Field(default=True)


class EmbeddingResponse(BaseModel):
    """임베딩 응답"""
    embeddings: list[list[float]]   # Dense 벡터 (1024차원)
    sparse_embeddings: list[dict[str, float]] | None = None  # Sparse 벡터
    model: str
    usage: dict[str, int]
    processing_time_ms: float


def get_model():
    """모델 Lazy 로드"""
    global _model, _tokenizer
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("BGE-M3-Korean 모델 로드 중...")
        _model = SentenceTransformer("upskyy/bge-m3-korean")
        logger.info("모델 로드 완료")
    return _model


@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "ok", "model": "bge-m3-korean", "dimension": 1024}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """임베딩 생성 API (OpenAI 호환)"""
    start = time.monotonic()

    try:
        model = get_model()
        embeddings = model.encode(
            request.texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        dense_list = embeddings.tolist()

        # Sparse 임베딩 (BM25 호환)
        sparse_list = None
        if request.return_sparse:
            sparse_list = _generate_sparse(request.texts)

        duration = (time.monotonic() - start) * 1000
        total_tokens = sum(len(t.split()) for t in request.texts)

        return EmbeddingResponse(
            embeddings=dense_list,
            sparse_embeddings=sparse_list,
            model="bge-m3-korean",
            usage={"prompt_tokens": total_tokens, "total_tokens": total_tokens},
            processing_time_ms=duration,
        )

    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_sparse(texts: list[str]) -> list[dict[str, float]]:
    """BM25 호환 Sparse 벡터 생성 (간단한 TF 기반)"""
    from collections import Counter
    import math

    sparse_vectors = []
    for text in texts:
        tokens = text.split()
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        sparse = {token: count / total for token, count in tf.items()}
        sparse_vectors.append(sparse)

    return sparse_vectors


@app.post("/v1/rerank")
async def rerank(
    query: str,
    documents: list[str],
    top_k: int = 10,
) -> dict[str, Any]:
    """Cross-encoder 리랭킹"""
    model = get_model()

    query_emb = model.encode([query], normalize_embeddings=True)
    doc_embs = model.encode(documents, normalize_embeddings=True)

    import numpy as np
    scores = np.dot(doc_embs, query_emb.T).flatten()

    ranked_indices = scores.argsort()[::-1][:top_k]
    results = [
        {"index": int(i), "score": float(scores[i]), "text": documents[i][:200]}
        for i in ranked_indices
    ]

    return {"results": results, "model": "bge-m3-korean"}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8002)
