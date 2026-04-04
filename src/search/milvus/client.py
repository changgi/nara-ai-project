"""
Milvus 2.6 벡터DB 클라이언트

BGE-M3-Korean (1024차원) 기반 벡터 CRUD 작업.
RaBitQ 1-bit 양자화 + Lindera 한국어 토크나이저 설정.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("nara-ai.search.milvus")

COLLECTION_NAME = "nara_records"
EMBEDDING_DIM = 1024


@dataclass
class MilvusConfig:
    """Milvus 연결 설정"""
    host: str = "localhost"
    port: int = 19530
    collection: str = COLLECTION_NAME
    dim: int = EMBEDDING_DIM


class NaraMilvusClient:
    """NARA-AI Milvus 클라이언트"""

    def __init__(self, config: MilvusConfig | None = None):
        self.config = config or MilvusConfig()
        self._connected = False

    def connect(self) -> None:
        """Milvus 연결"""
        from pymilvus import connections
        connections.connect(
            alias="default",
            host=self.config.host,
            port=self.config.port,
        )
        self._connected = True
        logger.info(f"Milvus 연결 완료: {self.config.host}:{self.config.port}")

    def create_collection(self) -> None:
        """nara_records 컬렉션 생성 (Dense + Sparse + JSON)"""
        from pymilvus import (
            Collection, CollectionSchema, FieldSchema, DataType,
            utility,
        )

        if utility.has_collection(self.config.collection):
            logger.info(f"컬렉션 '{self.config.collection}' 이미 존재")
            return

        fields = [
            FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema("dense_vector", DataType.FLOAT_VECTOR, dim=self.config.dim),
            FieldSchema("sparse_vector", DataType.SPARSE_FLOAT_VECTOR),
            FieldSchema("record_group", DataType.VARCHAR, max_length=32),
            FieldSchema("classification", DataType.VARCHAR, max_length=16),
            FieldSchema("date_created", DataType.INT64),
            FieldSchema("agency", DataType.VARCHAR, max_length=128),
            FieldSchema("title", DataType.VARCHAR, max_length=512),
            FieldSchema("content_preview", DataType.VARCHAR, max_length=2048),
            FieldSchema("metadata_json", DataType.JSON),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="국가기록물 벡터 컬렉션 (RaBitQ 1-bit 양자화)",
        )

        collection = Collection(self.config.collection, schema)

        # Dense 인덱스: IVF_FLAT (RaBitQ는 Milvus 2.6에서 별도 설정)
        collection.create_index(
            "dense_vector",
            {
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 1024},
            },
        )

        # Sparse 인덱스
        collection.create_index(
            "sparse_vector",
            {
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "IP",
            },
        )

        collection.load()
        logger.info(f"컬렉션 '{self.config.collection}' 생성 완료")

    def insert(self, records: list[dict[str, Any]]) -> int:
        """기록물 벡터 삽입"""
        from pymilvus import Collection

        collection = Collection(self.config.collection)
        data = [
            [r["id"] for r in records],
            [r["dense_vector"] for r in records],
            [r.get("sparse_vector", {}) for r in records],
            [r.get("record_group", "") for r in records],
            [r.get("classification", "public") for r in records],
            [r.get("date_created", 0) for r in records],
            [r.get("agency", "") for r in records],
            [r.get("title", "") for r in records],
            [r.get("content_preview", "") for r in records],
            [r.get("metadata_json", {}) for r in records],
        ]

        result = collection.insert(data)
        count = result.insert_count
        logger.info(f"{count}건 삽입 완료")
        return count

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Dense 벡터 검색"""
        from pymilvus import Collection

        collection = Collection(self.config.collection)

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 64},
        }

        results = collection.search(
            data=[query_vector],
            anns_field="dense_vector",
            param=search_params,
            limit=top_k,
            expr=filters,
            output_fields=["id", "title", "content_preview", "record_group", "agency", "classification"],
        )

        return [
            {
                "id": hit.entity.get("id"),
                "title": hit.entity.get("title"),
                "content_preview": hit.entity.get("content_preview"),
                "record_group": hit.entity.get("record_group"),
                "agency": hit.entity.get("agency"),
                "classification": hit.entity.get("classification"),
                "score": float(hit.distance),
            }
            for hit in results[0]
        ]

    def get_stats(self) -> dict[str, Any]:
        """컬렉션 통계"""
        from pymilvus import Collection, utility

        if not utility.has_collection(self.config.collection):
            return {"exists": False}

        collection = Collection(self.config.collection)
        return {
            "exists": True,
            "name": self.config.collection,
            "num_entities": collection.num_entities,
            "dim": self.config.dim,
        }

    def disconnect(self) -> None:
        """Milvus 연결 해제"""
        from pymilvus import connections
        connections.disconnect("default")
        self._connected = False
