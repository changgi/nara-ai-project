---
name: rag-search
description: "기록물 시맨틱 검색 및 RAG 시스템 구축 스킬. Milvus 2.6 벡터DB, BGE-M3-Korean 임베딩(1024차원, Dense+Sparse+Multi-vector), RaBitQ 1비트 양자화, Lindera 한국어 토크나이저, 하이브리드 검색(시맨틱+키워드+그래프), 리랭킹, Cloud Spanner RiC-CM 지식그래프 연동을 수행한다. '검색', 'RAG', '벡터DB', 'Milvus', '임베딩', '시맨틱 검색', '하이브리드 검색', '지식그래프', '리랭킹' 관련 작업 시 반드시 이 스킬을 사용할 것."
---

# RAG 검색 시스템 구축

국가기록물에 대한 지능형 시맨틱 검색과 RAG(Retrieval-Augmented Generation) 시스템을 구축한다. 국민이 자연어로 질의하면 관련 기록물을 정확하게 찾아 답변을 생성한다.

## 3-계층 하이브리드 검색

```
사용자 자연어 질의
    ↓
[1] 쿼리 분석 & 확장
    ├── 의도 분석 (검색/비교/요약/탐색)
    ├── 시소러스 확장 (동의어, 이형표기, 한자)
    └── 시간/기관/주제 필터 추출
    ↓
[2] 3-계층 병렬 검색
    ├── Dense 검색: BGE-M3-Korean 1024차원 벡터 유사도
    ├── Sparse 검색: BM25 + Lindera 한국어 토크나이저
    └── Graph 검색: Cloud Spanner RiC-CM 관계 탐색
    ↓
[3] 결과 융합 & 리랭킹
    ├── Reciprocal Rank Fusion (RRF)
    ├── Cross-encoder 리랭킹
    └── 접근 권한 필터링 (공개/제한/비밀/극비)
    ↓
[4] RAG 답변 생성
    ├── 출처 인용 (기록물 참조번호)
    ├── 신뢰도 점수
    └── 관련 기록물 추천
```

## Milvus 2.6 벡터DB 설정

```python
# src/search/milvus/schema.py
from pymilvus import CollectionSchema, FieldSchema, DataType

NARA_RECORDS_SCHEMA = CollectionSchema(
    fields=[
        FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema("dense_vector", DataType.FLOAT_VECTOR, dim=1024),  # BGE-M3 dense
        FieldSchema("sparse_vector", DataType.SPARSE_FLOAT_VECTOR),     # BGE-M3 sparse
        FieldSchema("record_group", DataType.VARCHAR, max_length=32),   # RG 번호
        FieldSchema("classification", DataType.VARCHAR, max_length=16), # 공개구분
        FieldSchema("date_created", DataType.INT64),                    # 생산일
        FieldSchema("agency", DataType.VARCHAR, max_length=128),        # 생산기관
        FieldSchema("title", DataType.VARCHAR, max_length=512),         # 제목
        FieldSchema("content_preview", DataType.VARCHAR, max_length=2048),  # 내용 미리보기
        FieldSchema("metadata_json", DataType.JSON),                    # 확장 메타데이터
    ],
    description="국가기록물 벡터 컬렉션 (RaBitQ 1-bit 양자화)"
)

# 인덱스 설정
INDEX_PARAMS = {
    "dense_vector": {
        "index_type": "IVF_RABITQ",  # RaBitQ 1-bit 양자화 (4x 처리량)
        "metric_type": "COSINE",
        "params": {"nlist": 1024}
    },
    "sparse_vector": {
        "index_type": "SPARSE_INVERTED_INDEX",
        "metric_type": "BM25"
    },
    "metadata_json": {
        "index_type": "JSON_PATH_INDEX",  # 100x 빠른 필터링
        "json_paths": ["$.brm_code", "$.retention_period", "$.security_level"]
    }
}
```

## BGE-M3-Korean 임베딩

```python
# src/search/embedding/embedder.py
class KoreanRecordEmbedder:
    """BGE-M3-Korean 기반 3-벡터 임베딩"""

    def __init__(self):
        self.model = "upskyy/bge-m3-korean"  # 568M, 1024차원
        self.max_length = 8192  # 긴 문서 지원

    def embed(self, text: str) -> dict:
        """Dense + Sparse + Multi-vector 동시 생성"""
        return {
            "dense": [...],    # 1024차원 float32
            "sparse": {...},   # BM25 호환 sparse
            "multi_vector": [...]  # ColBERT 스타일
        }
```

## RiC-CM 지식그래프 연동

Cloud Spanner Property Graph에 구현된 RiC-CM 1.0 (19개 엔티티, 142개 관계 유형)과 연동하여 그래프 기반 검색을 수행한다.

```
# 그래프 검색 예시: "김구 관련 기록물을 생산한 기관은?"
GRAPH QUERY:
  MATCH (p:Person {name: "김구"})
        -[:CREATED_BY|RELATED_TO*1..3]-
        (r:RecordGroup)
        -[:PRODUCED_BY]-
        (a:Agency)
  RETURN a.name, r.title, r.date_range
```

## 성능 목표

| 메트릭 | 목표 | 벤치마크 |
|--------|------|---------|
| Recall@10 | ≥ 0.90 | 기록물 검색 테스트셋 |
| P99 레이턴시 | ≤ 2초 | 1,000만 벡터 기준 |
| QPS | ≥ 471 | 99% recall @ 50M 벡터 |
| 임베딩 처리량 | ≥ 1,000 문서/분 | 배치 임베딩 |

## 접근 권한 필터링

기록물의 보안 등급에 따라 검색 결과를 필터링한다. JWT claims의 role과 Milvus의 metadata_json.security_level을 교차 검증한다.

```python
SECURITY_LEVELS = {
    "public": 1,        # 공개
    "restricted": 2,    # 부분공개
    "secret": 3,        # 비공개
    "top_secret": 4     # 비밀
}
```
