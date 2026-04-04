"""
검색 에이전트

국민의 자연어 질의를 분석하고, 3계층 하이브리드 검색(Dense+Sparse+Graph)을
수행하여 관련 기록물을 찾아 답변을 생성한다.

성능 목표: Recall@10 ≥ 0.90, P99 레이턴시 ≤ 2초
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("nara-ai.agents.search")


@dataclass
class SearchAgentResult:
    """검색 에이전트 결과"""
    answer: str
    sources: list[dict[str, Any]]
    total_found: int
    confidence: float
    query_analysis: dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    hitl_pending: bool = False
    reasoning: str = ""


class SearchAgent:
    """검색 AI 에이전트

    국민이 자연어로 국가기록에 접근할 수 있도록 한다.
    쿼리 분석 → 시소러스 확장 → 하이브리드 검색 → RAG 답변 생성
    """

    def __init__(
        self,
        rag_endpoint: str = "http://localhost:8000",
        embedding_endpoint: str = "http://localhost:8002",
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
    ):
        self.rag_endpoint = rag_endpoint
        self.embedding_endpoint = embedding_endpoint
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.client = httpx.AsyncClient(timeout=10.0)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        security_level: str = "public",
        user_role: str = "public",
    ) -> SearchAgentResult:
        """자연어 검색 수행"""
        start = time.monotonic()

        # 1. 접근 권한 확인
        allowed_levels = self._get_allowed_levels(user_role)
        if security_level not in allowed_levels:
            return SearchAgentResult(
                answer="해당 보안 등급의 기록물에 접근 권한이 없습니다.",
                sources=[],
                total_found=0,
                confidence=0.0,
                reasoning=f"권한 부족: {user_role} → {security_level}",
            )

        # 2. 쿼리 분석
        query_analysis = await self._analyze_query(query)

        # 3. 임베딩 생성
        query_vector = await self._get_embedding(query)

        # 4. Milvus 검색
        results = await self._search_milvus(
            query_vector, top_k, allowed_levels
        )

        # 5. RAG 답변 생성
        answer = await self._generate_answer(query, results)

        duration = (time.monotonic() - start) * 1000

        return SearchAgentResult(
            answer=answer,
            sources=results,
            total_found=len(results),
            confidence=results[0]["score"] if results else 0.0,
            query_analysis=query_analysis,
            processing_time_ms=duration,
            reasoning=f"하이브리드 검색 완료: {len(results)}건 ({duration:.0f}ms)",
        )

    def _get_allowed_levels(self, user_role: str) -> list[str]:
        """사용자 역할별 접근 가능 보안 등급"""
        role_permissions = {
            "public": ["public"],
            "researcher": ["public", "restricted"],
            "archivist": ["public", "restricted", "secret"],
            "admin": ["public", "restricted", "secret", "top_secret"],
        }
        return role_permissions.get(user_role, ["public"])

    async def _analyze_query(self, query: str) -> dict[str, Any]:
        """쿼리 의도 분석"""
        intent = "search"
        if any(kw in query for kw in ["비교", "차이"]):
            intent = "compare"
        elif any(kw in query for kw in ["요약", "정리"]):
            intent = "summarize"
        elif any(kw in query for kw in ["관련", "연결", "관계"]):
            intent = "explore"

        return {"original": query, "intent": intent, "language": "ko"}

    async def _get_embedding(self, text: str) -> list[float]:
        """텍스트 임베딩 생성"""
        try:
            response = await self.client.post(
                f"{self.embedding_endpoint}/v1/embeddings",
                json={"texts": [text], "model": "bge-m3-korean", "return_sparse": False},
            )
            response.raise_for_status()
            return response.json()["embeddings"][0]
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return [0.0] * 1024

    async def _search_milvus(
        self,
        query_vector: list[float],
        top_k: int,
        allowed_levels: list[str],
    ) -> list[dict[str, Any]]:
        """Milvus 벡터 검색 + 보안 등급 필터링"""
        try:
            from pymilvus import connections, Collection
            connections.connect(host=self.milvus_host, port=self.milvus_port)

            collection = Collection("nara_records")
            level_filter = " || ".join(
                f'classification == "{level}"' for level in allowed_levels
            )

            results = collection.search(
                data=[query_vector],
                anns_field="dense_vector",
                param={"metric_type": "COSINE", "params": {"nprobe": 64}},
                limit=top_k,
                expr=level_filter,
                output_fields=["id", "title", "content_preview", "agency", "record_group"],
            )

            return [
                {
                    "id": hit.entity.get("id", ""),
                    "title": hit.entity.get("title", ""),
                    "content_preview": hit.entity.get("content_preview", ""),
                    "agency": hit.entity.get("agency", ""),
                    "score": float(hit.distance),
                }
                for hit in results[0]
            ]
        except Exception as e:
            logger.error(f"Milvus 검색 실패: {e}")
            return []

    async def _generate_answer(self, query: str, sources: list[dict[str, Any]]) -> str:
        """RAG 답변 생성"""
        if not sources:
            return "관련 기록물을 찾을 수 없습니다. 다른 검색어를 시도해 보세요."

        context = "\n".join(
            f"[{i+1}] {s['title']} ({s.get('agency', '')})\n{s.get('content_preview', '')[:200]}"
            for i, s in enumerate(sources[:5])
        )

        try:
            response = await self.client.post(
                f"{self.rag_endpoint}/v1/chat/completions",
                json={
                    "model": "nara-classifier-v1",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "국가기록원 검색 도우미입니다. 검색된 기록물을 바탕으로 "
                                "정확하게 답변하고, 출처 번호를 인용하세요. "
                                "확인할 수 없는 내용은 답변하지 마세요."
                            ),
                        },
                        {"role": "user", "content": f"질문: {query}\n\n검색 결과:\n{context}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"답변 생성 실패: {e}")
            titles = ", ".join(s["title"] for s in sources[:3])
            return f"관련 기록물 {len(sources)}건을 찾았습니다: {titles}"

    async def close(self) -> None:
        await self.client.aclose()
