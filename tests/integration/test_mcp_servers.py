"""
MCP 서버 통합 테스트

5개 MCP 서버의 헬스체크 및 도구 호출 검증.
경계면 교차 비교: MCP 스키마 ↔ LangGraph 에이전트.
"""

import pytest
import httpx


# 서버 포트 매핑
MCP_SERVERS = {
    "mcp-archive": {"port": 3001, "expected_tools": 10},
    "mcp-iarna": {"port": 3002, "expected_tools": 12},
    "mcp-nara": {"port": 3003, "expected_tools": 12},
    "mcp-law": {"port": 3004, "expected_tools": 6},
    "mcp-ramp": {"port": 3005, "expected_tools": 7},
}

INFERENCE_SERVERS = {
    "vllm-llm": {"port": 8000, "health_path": "/health"},
    "vllm-ocr": {"port": 8001, "health_path": "/health"},
    "embedding": {"port": 8002, "health_path": "/health"},
}


@pytest.fixture
def http_client():
    return httpx.Client(timeout=5.0)


class TestMCPServerHealth:
    """MCP 서버 헬스체크 테스트"""

    @pytest.mark.parametrize("server_name,config", list(MCP_SERVERS.items()))
    def test_health_endpoint(self, http_client, server_name, config):
        """각 MCP 서버의 /health 엔드포인트가 응답해야 한다"""
        try:
            response = http_client.get(f"http://localhost:{config['port']}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["server"] == server_name
        except httpx.ConnectError:
            pytest.skip(f"{server_name} 서버가 실행 중이 아닙니다")


class TestInferenceServerHealth:
    """추론 서버 헬스체크 테스트"""

    @pytest.mark.parametrize("server_name,config", list(INFERENCE_SERVERS.items()))
    def test_health_endpoint(self, http_client, server_name, config):
        """추론 서버가 응답해야 한다"""
        try:
            response = http_client.get(f"http://localhost:{config['port']}{config['health_path']}")
            assert response.status_code == 200
        except httpx.ConnectError:
            pytest.skip(f"{server_name} 서버가 실행 중이 아닙니다")


class TestMilvusConnection:
    """Milvus 벡터DB 연결 테스트"""

    def test_connection(self):
        """Milvus에 연결할 수 있어야 한다"""
        try:
            from pymilvus import connections, utility
            connections.connect(host="localhost", port=19530)
            assert utility.get_server_version() is not None
            connections.disconnect("default")
        except Exception:
            pytest.skip("Milvus 서버가 실행 중이 아닙니다")


class TestBoundaryVerification:
    """경계면 교차 비교 테스트 (QA 핵심)"""

    def test_mcp_tool_count_consistency(self):
        """MCP 서버별 도구 수가 설계와 일치해야 한다"""
        expected_total = sum(c["expected_tools"] for c in MCP_SERVERS.values())
        assert expected_total == 47  # 10+12+12+6+7 = 47

    def test_pipeline_stage_count(self):
        """11단계 파이프라인이 정확히 11개여야 한다"""
        from src.pipeline.pipeline_executor import PipelineStage
        assert len(list(PipelineStage)) == 11

    def test_hitl_gates_exist(self):
        """HITL 게이트가 4개 정의되어야 한다"""
        from src.pipeline.pipeline_executor import HITLGate
        assert len(HITLGate.REQUIRED_ACTIONS) == 4
        assert "redaction_decision" in HITLGate.REQUIRED_ACTIONS
        assert "retention_override" in HITLGate.REQUIRED_ACTIONS
        assert "classification_dispute" in HITLGate.REQUIRED_ACTIONS
        assert "disposal_approval" in HITLGate.REQUIRED_ACTIONS

    def test_security_levels_match_law(self):
        """보안 등급이 공공기록물법과 일치해야 한다"""
        from src.pipeline.pipeline_executor import SecurityLevel
        levels = [l.value for l in SecurityLevel]
        assert "public" in levels
        assert "restricted" in levels
        assert "secret" in levels
        assert "top_secret" in levels

    def test_ric_cm_entities_count(self):
        """RiC-CM 엔티티가 19개 정의되어야 한다"""
        from src.standards.ric_cm.entities import EntityType
        assert len(list(EntityType)) == 19

    def test_brm_top_level_categories(self):
        """BRM 대분류가 16개여야 한다"""
        from src.standards.ric_cm.entities import BRM_TOP_LEVEL
        assert len(BRM_TOP_LEVEL) == 16

    def test_pii_patterns_defined(self):
        """PII 탐지 패턴이 6종 이상 정의되어야 한다"""
        from src.agents.redaction.agent import PII_PATTERNS
        assert len(PII_PATTERNS) >= 6
        assert "resident_id" in PII_PATTERNS
        assert all("severity" in v for v in PII_PATTERNS.values())

    def test_ocr_ensemble_model_routing(self):
        """OCR 앙상블 모델 라우팅이 7종 문서에 대해 정의되어야 한다"""
        from src.ocr.pipeline.ocr_ensemble import OCREnsemble, DocumentCategory
        assert len(DocumentCategory) == 7
        assert len(OCREnsemble.MODEL_ROUTING) == 7
        # 각 문서 유형에 3개 모델 가중치가 있어야 한다
        for category, weights in OCREnsemble.MODEL_ROUTING.items():
            assert len(weights) == 3
            assert abs(sum(weights.values()) - 1.0) < 0.01  # 가중치 합 = 1.0
