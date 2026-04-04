"""
NARA-AI RAG (Retrieval-Augmented Generation) 파이프라인

3-계층 하이브리드 검색: Dense + Sparse + Graph
Milvus 2.6 + BGE-M3-Korean + Cloud Spanner RiC-CM 연동

성능 목표: Recall@10 ≥ 0.90, P99 레이턴시 ≤ 2초
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("nara-ai.search.rag")


@dataclass
class SearchResult:
    """검색 결과"""
    id: str
    title: str
    content_preview: str
    score: float
    source: str           # "dense", "sparse", "graph", "hybrid"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResponse:
    """RAG 응답"""
    answer: str
    sources: list[SearchResult]
    confidence: float
    query_analysis: dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


class QueryAnalyzer:
    """쿼리 분석기: 의도 분석, 시소러스 확장, 필터 추출"""

    INTENT_TYPES = ["search", "compare", "summarize", "explore", "legal"]

    async def analyze(self, query: str) -> dict[str, Any]:
        """자연어 쿼리를 분석한다."""
        return {
            "original_query": query,
            "intent": self._detect_intent(query),
            "expanded_terms": self._expand_terms(query),
            "filters": self._extract_filters(query),
            "language": "ko",
        }

    def _detect_intent(self, query: str) -> str:
        """의도 분류 (규칙 기반 + 키워드)"""
        if any(kw in query for kw in ["비교", "차이", "대비"]):
            return "compare"
        if any(kw in query for kw in ["요약", "정리", "핵심"]):
            return "summarize"
        if any(kw in query for kw in ["법률", "법적", "조항", "공공기록물법"]):
            return "legal"
        if any(kw in query for kw in ["관련", "연결", "관계", "네트워크"]):
            return "explore"
        return "search"

    def _expand_terms(self, query: str) -> list[str]:
        """시소러스 기반 쿼리 확장 (동의어, 이형표기, 한자)"""
        # IARNA 시소러스 연동
        expansions = [query]
        # 예: "경성" → ["경성", "京城", "서울", "Seoul"]
        return expansions

    def _extract_filters(self, query: str) -> dict[str, Any]:
        """날짜, 기관, 주제 등 필터 추출"""
        filters: dict[str, Any] = {}
        # 간단한 연도 추출
        import re
        years = re.findall(r'(\d{4})년', query)
        if years:
            filters["date_year"] = [int(y) for y in years]
        return filters


class MilvusSearcher:
    """Milvus 벡터 검색 (Dense + Sparse)"""

    def __init__(
        self,
        embedding_endpoint: str = "http://localhost:8002",
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        collection_name: str = "nara_records",
    ):
        self.embedding_endpoint = embedding_endpoint
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = collection_name
        self.client = httpx.AsyncClient(timeout=10.0)

    async def dense_search(self, query: str, top_k: int = 20) -> list[SearchResult]:
        """Dense 벡터 검색 (BGE-M3-Korean 1024차원)"""
        try:
            # 1. 쿼리 임베딩 생성
            emb_response = await self.client.post(
                f"{self.embedding_endpoint}/v1/embeddings",
                json={"texts": [query], "model": "bge-m3-korean", "return_sparse": False},
            )
            emb_response.raise_for_status()
            query_vector = emb_response.json()["embeddings"][0]

            # 2. Milvus 검색
            from pymilvus import connections, Collection
            connections.connect(host=self.milvus_host, port=self.milvus_port)
            collection = Collection(self.collection_name)

            results = collection.search(
                data=[query_vector],
                anns_field="dense_vector",
                param={"metric_type": "COSINE", "params": {"nprobe": 64}},
                limit=top_k,
                output_fields=["id", "title", "content_preview", "record_group", "agency"],
            )

            return [
                SearchResult(
                    id=hit.entity.get("id", ""),
                    title=hit.entity.get("title", ""),
                    content_preview=hit.entity.get("content_preview", ""),
                    score=float(hit.distance),
                    source="dense",
                    metadata={
                        "record_group": hit.entity.get("record_group", ""),
                        "agency": hit.entity.get("agency", ""),
                    },
                )
                for hit in results[0]
            ]
        except Exception as e:
            logger.error(f"Dense 검색 실패: {e}")
            return []

    async def sparse_search(self, query: str, top_k: int = 20) -> list[SearchResult]:
        """Sparse 검색 (BM25 + Lindera 한국어 토크나이저)"""
        try:
            from pymilvus import connections, Collection
            connections.connect(host=self.milvus_host, port=self.milvus_port)
            collection = Collection(self.collection_name)

            # BM25 기반 sparse 검색
            emb_response = await self.client.post(
                f"{self.embedding_endpoint}/v1/embeddings",
                json={"texts": [query], "model": "bge-m3-korean", "return_sparse": True},
            )
            emb_response.raise_for_status()
            sparse_vector = emb_response.json().get("sparse_embeddings", [{}])[0]

            # Milvus sparse 검색은 별도 인덱스
            results = collection.search(
                data=[sparse_vector],
                anns_field="sparse_vector",
                param={"metric_type": "IP"},  # Milvus sparse는 IP 메트릭 사용 (QA-M01 수정)
                limit=top_k,
                output_fields=["id", "title", "content_preview"],
            )

            return [
                SearchResult(
                    id=hit.entity.get("id", ""),
                    title=hit.entity.get("title", ""),
                    content_preview=hit.entity.get("content_preview", ""),
                    score=float(hit.distance),
                    source="sparse",
                )
                for hit in results[0]
            ]
        except Exception as e:
            logger.error(f"Sparse 검색 실패: {e}")
            return []

    async def close(self) -> None:
        await self.client.aclose()


class GraphSearcher:
    """Cloud Spanner RiC-CM 그래프 검색"""

    async def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """지식그래프 기반 관계 탐색 (MCP JSON-RPC 프로토콜)"""
        # IARNA MCP 서버 (포트 3002) - JSON-RPC 2.0 프로토콜 (QA-M02 수정)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://localhost:3002/jsonrpc",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": "vibe_query", "arguments": {"query": query, "maxResults": top_k}},
                        "id": 1,
                    },
                )
                response.raise_for_status()
                rpc_result = response.json()
                data = rpc_result.get("result", {})

                return [
                    SearchResult(
                        id=item.get("id", ""),
                        title=item.get("name", ""),
                        content_preview=item.get("description", ""),
                        score=float(item.get("relevance", 0.5)),
                        source="graph",
                        metadata=item.get("properties", {}),
                    )
                    for item in data.get("results", [])
                ]
        except Exception as e:
            logger.error(f"그래프 검색 실패: {e}")
            return []


class RAGPipeline:
    """3-계층 하이브리드 RAG 파이프라인"""

    def __init__(self):
        self.query_analyzer = QueryAnalyzer()
        self.milvus = MilvusSearcher()
        self.graph = GraphSearcher()
        self.llm_client = httpx.AsyncClient(timeout=30.0)

    async def search(self, query: str, top_k: int = 10) -> RAGResponse:
        """하이브리드 검색 + RAG 답변 생성"""
        start = time.monotonic()

        # 1. 쿼리 분석
        analysis = await self.query_analyzer.analyze(query)

        # 2. 3-계층 병렬 검색
        dense_task = self.milvus.dense_search(query, top_k * 2)
        sparse_task = self.milvus.sparse_search(query, top_k * 2)
        graph_task = self.graph.search(query, top_k)

        dense_results, sparse_results, graph_results = await asyncio.gather(
            dense_task, sparse_task, graph_task,
            return_exceptions=True,
        )

        # 예외 처리
        if isinstance(dense_results, Exception):
            dense_results = []
        if isinstance(sparse_results, Exception):
            sparse_results = []
        if isinstance(graph_results, Exception):
            graph_results = []

        # 3. RRF (Reciprocal Rank Fusion) 결과 융합
        fused = self._reciprocal_rank_fusion(
            dense_results, sparse_results, graph_results, top_k
        )

        # 4. RAG 답변 생성
        answer = await self._generate_answer(query, fused)

        duration = (time.monotonic() - start) * 1000

        return RAGResponse(
            answer=answer,
            sources=fused,
            confidence=fused[0].score if fused else 0.0,
            query_analysis=analysis,
            processing_time_ms=duration,
        )

    def _reciprocal_rank_fusion(
        self,
        dense: list[SearchResult],
        sparse: list[SearchResult],
        graph: list[SearchResult],
        top_k: int,
        k: int = 60,  # RRF 상수
    ) -> list[SearchResult]:
        """RRF로 3개 검색 결과 융합"""
        scores: dict[str, float] = {}
        results_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(dense):
            scores[result.id] = scores.get(result.id, 0) + 1.0 / (k + rank + 1)
            results_map[result.id] = result

        for rank, result in enumerate(sparse):
            scores[result.id] = scores.get(result.id, 0) + 1.0 / (k + rank + 1)
            if result.id not in results_map:
                results_map[result.id] = result

        for rank, result in enumerate(graph):
            scores[result.id] = scores.get(result.id, 0) + 1.5 / (k + rank + 1)  # 그래프 가중치 부스트
            if result.id not in results_map:
                results_map[result.id] = result

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]

        return [
            SearchResult(
                id=rid,
                title=results_map[rid].title,
                content_preview=results_map[rid].content_preview,
                score=scores[rid],
                source="hybrid",
                metadata=results_map[rid].metadata,
            )
            for rid in sorted_ids
            if rid in results_map
        ]

    async def _generate_answer(self, query: str, sources: list[SearchResult]) -> str:
        """검색 결과 기반 RAG 답변 생성"""
        if not sources:
            return "관련 기록물을 찾을 수 없습니다."

        context = "\n\n".join(
            f"[출처 {i+1}] {s.title}\n{s.content_preview}"
            for i, s in enumerate(sources[:5])
        )

        try:
            response = await self.llm_client.post(
                "http://localhost:8000/v1/chat/completions",
                json={
                    "model": "nara-classifier-v1",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "당신은 국가기록원 검색 도우미입니다. "
                                "제공된 기록물 출처를 바탕으로 정확하게 답변하세요. "
                                "반드시 출처 번호를 인용하세요."
                            ),
                        },
                        {"role": "user", "content": f"질문: {query}\n\n참고 기록물:\n{context}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"RAG 답변 생성 실패: {e}")
            return f"검색 결과 {len(sources)}건을 찾았으나 답변 생성에 실패했습니다."

    async def close(self) -> None:
        await self.milvus.close()
        await self.llm_client.aclose()
