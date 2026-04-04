"""검색/RAG 및 오케스트레이터 단위 테스트"""

import pytest
from src.search.rag.pipeline import QueryAnalyzer, RAGPipeline
from src.search.milvus.client import NaraMilvusClient, MilvusConfig
from src.pipeline.eval.benchmark import compute_f1, compute_rouge1, compute_cer, TARGETS


class TestQueryAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return QueryAnalyzer()

    @pytest.mark.asyncio
    async def test_search_intent(self, analyzer):
        result = await analyzer.analyze("한국전쟁 기록물 찾기")
        assert result["intent"] == "search"

    @pytest.mark.asyncio
    async def test_compare_intent(self, analyzer):
        result = await analyzer.analyze("남북한 외교 정책 비교")
        assert result["intent"] == "compare"

    @pytest.mark.asyncio
    async def test_summarize_intent(self, analyzer):
        result = await analyzer.analyze("이 문서를 요약해주세요")
        assert result["intent"] == "summarize"

    @pytest.mark.asyncio
    async def test_explore_intent(self, analyzer):
        result = await analyzer.analyze("김구와 관련된 인물 네트워크")
        assert result["intent"] == "explore"


class TestMilvusConfig:
    def test_default_config(self):
        config = MilvusConfig()
        assert config.host == "localhost"
        assert config.port == 19530
        assert config.collection == "nara_records"
        assert config.dim == 1024


class TestBenchmarkMetrics:
    def test_f1_perfect(self):
        preds = ["A", "B", "C"]
        refs = ["A", "B", "C"]
        assert compute_f1(preds, refs) == 1.0

    def test_f1_zero(self):
        preds = ["A", "A", "A"]
        refs = ["B", "B", "B"]
        assert compute_f1(preds, refs) == 0.0

    def test_f1_partial(self):
        preds = ["A", "B", "C"]
        refs = ["A", "B", "X"]
        f1 = compute_f1(preds, refs)
        assert 0.0 < f1 < 1.0

    def test_rouge1_perfect(self):
        preds = ["나는 학생입니다"]
        refs = ["나는 학생입니다"]
        assert compute_rouge1(preds, refs) == 1.0

    def test_rouge1_zero(self):
        preds = ["완전히 다른 문장"]
        refs = ["아무런 관련 없는 내용"]
        r1 = compute_rouge1(preds, refs)
        assert r1 < 1.0

    def test_cer_perfect(self):
        preds = ["안녕하세요"]
        refs = ["안녕하세요"]
        assert compute_cer(preds, refs) == 0.0

    def test_cer_imperfect(self):
        preds = ["안녕하세오"]  # 1글자 오류
        refs = ["안녕하세요"]
        cer = compute_cer(preds, refs)
        assert 0.0 < cer < 1.0

    def test_targets_defined(self):
        """성능 목표가 8개 정의되어야 한다"""
        assert len(TARGETS) == 8
        assert TARGETS["classification_f1"] == 0.92
        assert TARGETS["ocr_cer_printed"] == 0.03
        assert TARGETS["search_recall_at_10"] == 0.90


class TestOrchestratorGraph:
    def test_graph_builds(self):
        """오케스트레이터 그래프가 빌드 가능해야 한다"""
        pytest.importorskip("langgraph", reason="langgraph 미설치")
        from src.agents.orchestrator.graph import build_orchestrator_graph
        graph = build_orchestrator_graph()
        assert graph is not None

    def test_state_type_defined(self):
        """RecordProcessingState가 올바르게 정의되어야 한다"""
        pytest.importorskip("langgraph", reason="langgraph 미설치")
        from src.agents.orchestrator.graph import RecordProcessingState
        annotations = RecordProcessingState.__annotations__
        assert "document_id" in annotations
        assert "brm_code" in annotations
        assert "hitl_pending" in annotations
        assert "audit_trail" in annotations
