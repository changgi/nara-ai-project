"""
NARA-AI CPU 전용 임베딩/검색 모듈

GPU 없는 환경(노트북, RTX 3060 등)에서도 동작하는 경량 검색 시스템.
TF-IDF + BM25 기반으로 CPU만으로 시맨틱 검색을 수행한다.

사용법:
    # CPU 모드 자동 감지
    embedder = CPUEmbedder()
    vectors = embedder.embed(["기록물 검색 테스트"])
    results = embedder.search("한국전쟁 기록물", top_k=10)
"""

from __future__ import annotations

import json
import logging
import math
import os
import pickle
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("nara-ai.search.cpu")


@dataclass
class CPUSearchResult:
    """CPU 검색 결과"""
    id: str
    title: str
    content_preview: str
    score: float
    method: str  # "tfidf" | "bm25" | "hybrid"


class KoreanTokenizer:
    """한국어 간이 토크나이저 (형태소 분석기 없이 동작)

    공백 + 조사 제거 + 불용어 필터링으로 기본 토큰화.
    GPU/외부 라이브러리 불필요.
    """

    # 한국어 불용어 (기록물 도메인)
    STOPWORDS = {
        "이", "가", "은", "는", "을", "를", "에", "의", "로", "와", "과",
        "도", "만", "까지", "부터", "에서", "으로", "하다", "되다", "있다",
        "없다", "것", "수", "등", "및", "또는", "그", "이런", "저런",
        "한", "할", "함", "하는", "된", "하여", "위해", "대한", "관한",
    }

    # 조사 패턴
    JOSA_PATTERN = re.compile(r'(이|가|은|는|을|를|에|의|로|와|과|도|만|까지|부터|에서)$')

    def tokenize(self, text: str) -> list[str]:
        """텍스트를 토큰으로 분리"""
        # 특수문자 제거, 공백 분리
        text = re.sub(r'[^\w\s가-힣a-zA-Z0-9]', ' ', text)
        tokens = text.split()

        result = []
        for token in tokens:
            # 1글자 토큰 제거
            if len(token) <= 1:
                continue
            # 조사 제거
            clean = self.JOSA_PATTERN.sub('', token)
            if len(clean) <= 1:
                continue
            # 불용어 제거
            if clean in self.STOPWORDS:
                continue
            result.append(clean.lower())

        return result


class TFIDFVectorizer:
    """TF-IDF 벡터라이저 (sklearn 없이 순수 Python 구현)

    CPU만으로 동작하며, 외부 의존성 없음.
    """

    def __init__(self):
        self.tokenizer = KoreanTokenizer()
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.doc_count = 0

    def fit(self, documents: list[str]) -> None:
        """문서 집합에서 IDF 학습"""
        self.doc_count = len(documents)
        df: dict[str, int] = defaultdict(int)

        for doc in documents:
            tokens = set(self.tokenizer.tokenize(doc))
            for token in tokens:
                df[token] += 1

        # IDF 계산
        for token, count in df.items():
            self.idf[token] = math.log((self.doc_count + 1) / (count + 1)) + 1

        # 어휘 사전 구축
        self.vocab = {token: idx for idx, token in enumerate(sorted(self.idf.keys()))}

    def transform(self, text: str) -> dict[int, float]:
        """텍스트를 TF-IDF sparse 벡터로 변환"""
        tokens = self.tokenizer.tokenize(text)
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1

        vector: dict[int, float] = {}
        for token, count in tf.items():
            if token in self.vocab:
                tf_val = count / total
                idf_val = self.idf.get(token, 1.0)
                vector[self.vocab[token]] = tf_val * idf_val

        return vector

    def similarity(self, vec1: dict[int, float], vec2: dict[int, float]) -> float:
        """코사인 유사도"""
        common_keys = set(vec1.keys()) & set(vec2.keys())
        if not common_keys:
            return 0.0

        dot = sum(vec1[k] * vec2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)


class BM25:
    """BM25 검색 (CPU 전용, 순수 Python)

    Okapi BM25 구현. 한국어 기록물 검색에 최적화.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.tokenizer = KoreanTokenizer()
        self.doc_tokens: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_length: float = 0.0
        self.df: dict[str, int] = defaultdict(int)
        self.n_docs: int = 0

    def fit(self, documents: list[str]) -> None:
        """문서 컬렉션 인덱싱"""
        self.n_docs = len(documents)
        self.doc_tokens = []
        self.doc_lengths = []
        self.df = defaultdict(int)

        for doc in documents:
            tokens = self.tokenizer.tokenize(doc)
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))

            for token in set(tokens):
                self.df[token] += 1

        self.avg_doc_length = sum(self.doc_lengths) / self.n_docs if self.n_docs > 0 else 1

    def score(self, query: str, doc_idx: int) -> float:
        """BM25 스코어 계산"""
        query_tokens = self.tokenizer.tokenize(query)
        doc_tokens = self.doc_tokens[doc_idx]
        doc_len = self.doc_lengths[doc_idx]
        tf = Counter(doc_tokens)

        score = 0.0
        for token in query_tokens:
            if token not in tf:
                continue

            # IDF
            n = self.df.get(token, 0)
            idf = math.log((self.n_docs - n + 0.5) / (n + 0.5) + 1)

            # TF with length normalization
            freq = tf[token]
            tf_norm = (freq * (self.k1 + 1)) / (
                freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
            )

            score += idf * tf_norm

        return score

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """BM25 검색"""
        scores = [(i, self.score(query, i)) for i in range(self.n_docs)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class CPUEmbedder:
    """CPU 전용 임베딩/검색 통합 모듈

    GPU 없이도 기록물 검색이 가능하도록 TF-IDF + BM25 하이브리드 검색을 제공.
    """

    def __init__(self, db_path: str = "data/db/cpu_vectors.pkl"):
        self.db_path = Path(db_path)
        self.tfidf = TFIDFVectorizer()
        self.bm25 = BM25()
        self.documents: list[dict[str, str]] = []
        self.tfidf_vectors: list[dict[int, float]] = []
        self._loaded = False

    def index_documents(self, documents: list[dict[str, str]]) -> int:
        """문서 컬렉션 인덱싱 (CPU)

        Args:
            documents: [{"id": "...", "title": "...", "content": "..."}]
        Returns:
            인덱싱된 문서 수
        """
        self.documents = documents
        texts = [f"{d.get('title', '')} {d.get('content', '')}" for d in documents]

        logger.info(f"CPU 인덱싱 시작: {len(texts)}건")

        # TF-IDF 학습
        self.tfidf.fit(texts)
        self.tfidf_vectors = [self.tfidf.transform(t) for t in texts]

        # BM25 학습
        self.bm25.fit(texts)

        # 저장
        self._save()
        self._loaded = True

        logger.info(f"CPU 인덱싱 완료: {len(texts)}건, 어휘: {len(self.tfidf.vocab)}개")
        return len(texts)

    def search(self, query: str, top_k: int = 10) -> list[CPUSearchResult]:
        """하이브리드 검색 (TF-IDF + BM25)"""
        if not self._loaded:
            self._load()

        if not self.documents:
            return []

        # TF-IDF 검색
        query_vec = self.tfidf.transform(query)
        tfidf_scores = [
            (i, self.tfidf.similarity(query_vec, doc_vec))
            for i, doc_vec in enumerate(self.tfidf_vectors)
        ]

        # BM25 검색
        bm25_results = self.bm25.search(query, top_k * 2)

        # RRF 융합
        rrf_scores: dict[int, float] = {}
        k = 60

        tfidf_sorted = sorted(tfidf_scores, key=lambda x: x[1], reverse=True)
        for rank, (idx, _) in enumerate(tfidf_sorted[:top_k * 2]):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank + 1)

        for rank, (idx, _) in enumerate(bm25_results):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank + 1)

        # 상위 K개
        sorted_indices = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        results = []
        for idx in sorted_indices:
            doc = self.documents[idx]
            results.append(CPUSearchResult(
                id=doc.get("id", str(idx)),
                title=doc.get("title", ""),
                content_preview=doc.get("content", "")[:200],
                score=rrf_scores[idx],
                method="hybrid",
            ))

        return results

    def _save(self) -> None:
        """인덱스 저장"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "documents": self.documents,
            "tfidf_vocab": self.tfidf.vocab,
            "tfidf_idf": self.tfidf.idf,
            "tfidf_vectors": self.tfidf_vectors,
            "bm25_doc_tokens": self.bm25.doc_tokens,
            "bm25_doc_lengths": self.bm25.doc_lengths,
            "bm25_df": dict(self.bm25.df),
            "bm25_avg_doc_length": self.bm25.avg_doc_length,
            "bm25_n_docs": self.bm25.n_docs,
        }
        with open(self.db_path, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"CPU 인덱스 저장: {self.db_path}")

    def _load(self) -> None:
        """인덱스 로드"""
        if not self.db_path.exists():
            logger.warning(f"인덱스 파일 없음: {self.db_path}")
            return

        with open(self.db_path, "rb") as f:
            data = pickle.load(f)

        self.documents = data["documents"]
        self.tfidf.vocab = data["tfidf_vocab"]
        self.tfidf.idf = data["tfidf_idf"]
        self.tfidf_vectors = data["tfidf_vectors"]
        self.bm25.doc_tokens = data["bm25_doc_tokens"]
        self.bm25.doc_lengths = data["bm25_doc_lengths"]
        self.bm25.df = defaultdict(int, data["bm25_df"])
        self.bm25.avg_doc_length = data["bm25_avg_doc_length"]
        self.bm25.n_docs = data["bm25_n_docs"]
        self._loaded = True

        logger.info(f"CPU 인덱스 로드: {len(self.documents)}건")
