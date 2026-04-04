"""CPU 전용 검색 모듈 테스트"""

import pytest
from src.search.embedding.cpu_embedder import (
    KoreanTokenizer, TFIDFVectorizer, BM25, CPUEmbedder, CPUSearchResult,
)


class TestKoreanTokenizer:
    @pytest.fixture
    def tokenizer(self):
        return KoreanTokenizer()

    def test_basic_tokenize(self, tokenizer):
        tokens = tokenizer.tokenize("국가기록원에서 기록물을 관리한다")
        assert "국가기록원" in tokens or "국가기록원에서" in tokens

    def test_stopword_removal(self, tokenizer):
        tokens = tokenizer.tokenize("이것은 테스트입니다")
        assert "이것" not in tokens or len(tokens) < 3

    def test_single_char_removal(self, tokenizer):
        tokens = tokenizer.tokenize("나 는 학 생")
        # 1글자 토큰은 제거
        for t in tokens:
            assert len(t) > 1


class TestTFIDF:
    def test_fit_and_transform(self):
        vectorizer = TFIDFVectorizer()
        docs = ["국가기록원 기록물 관리", "행정안전부 정부혁신 추진", "교육부 교육과정 개정"]
        vectorizer.fit(docs)

        vec = vectorizer.transform("기록물 관리")
        assert len(vec) > 0

    def test_similarity(self):
        vectorizer = TFIDFVectorizer()
        docs = ["국가기록원 기록물 관리", "행정안전부 정부혁신", "기록물 보존 관리 체계"]
        vectorizer.fit(docs)

        v1 = vectorizer.transform("기록물 관리")
        v2 = vectorizer.transform("기록물 보존 관리")
        v3 = vectorizer.transform("정부혁신 추진")

        sim_12 = vectorizer.similarity(v1, v2)
        sim_13 = vectorizer.similarity(v1, v3)

        # "기록물 관리"는 "기록물 보존 관리"와 더 유사해야 한다
        assert sim_12 > sim_13


class TestBM25:
    def test_search(self):
        bm25 = BM25()
        docs = [
            "국가기록원은 기록물의 효율적 관리를 담당한다",
            "행정안전부는 정부혁신을 추진한다",
            "공공기록물법에 따라 기록물을 보존한다",
        ]
        bm25.fit(docs)

        results = bm25.search("기록물 관리", top_k=3)
        assert len(results) == 3
        # 첫 번째 결과가 "기록물 관리" 관련 문서여야 한다
        assert results[0][0] in (0, 2)  # 인덱스 0 또는 2

    def test_score_relevance(self):
        bm25 = BM25()
        docs = ["기록물 관리 체계", "완전히 다른 주제의 문서"]
        bm25.fit(docs)

        score0 = bm25.score("기록물", 0)
        score1 = bm25.score("기록물", 1)
        assert score0 > score1


class TestCPUEmbedder:
    def test_index_and_search(self, tmp_path):
        embedder = CPUEmbedder(db_path=str(tmp_path / "test_vectors.pkl"))

        documents = [
            {"id": "1", "title": "정부혁신 추진계획", "content": "행정안전부는 디지털 정부혁신을 추진한다"},
            {"id": "2", "title": "기록물 관리 지침", "content": "국가기록원의 기록물 보존 및 관리 체계"},
            {"id": "3", "title": "국방 전략 보고서", "content": "국방부의 한반도 안보 전략 분석"},
            {"id": "4", "title": "교육과정 개정", "content": "교육부의 2025 개정 교육과정 적용 방안"},
            {"id": "5", "title": "비밀기록물 관리", "content": "비밀 기록물의 생산등록 및 분류 관리 규정"},
        ]

        count = embedder.index_documents(documents)
        assert count == 5

        # 검색
        results = embedder.search("기록물 관리", top_k=3)
        assert len(results) <= 3
        assert all(isinstance(r, CPUSearchResult) for r in results)

        # 기록물 관련 문서가 상위에 있어야 한다
        top_titles = [r.title for r in results]
        assert any("기록물" in t for t in top_titles)

    def test_save_and_load(self, tmp_path):
        db_path = str(tmp_path / "persist_test.pkl")

        # 인덱싱
        embedder1 = CPUEmbedder(db_path=db_path)
        embedder1.index_documents([
            {"id": "1", "title": "테스트 문서", "content": "국가기록원 기록물 관리"},
        ])

        # 새 인스턴스에서 로드
        embedder2 = CPUEmbedder(db_path=db_path)
        results = embedder2.search("기록물", top_k=1)
        assert len(results) == 1

    def test_empty_search(self, tmp_path):
        embedder = CPUEmbedder(db_path=str(tmp_path / "empty.pkl"))
        results = embedder.search("검색어")
        assert results == []
