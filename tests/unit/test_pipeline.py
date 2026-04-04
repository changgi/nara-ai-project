"""
NARA-AI 파이프라인 단위 테스트

11단계 처리 파이프라인의 핵심 기능을 검증한다.
"""

import pytest
from src.pipeline.pipeline_executor import (
    PipelineStage,
    SecurityLevel,
    RecordType,
    RecordDocument,
    AuditEntry,
    HITLGate,
    PipelineExecutor,
)


class TestPipelineStage:
    """파이프라인 단계 테스트"""

    def test_stage_order(self):
        """11단계가 올바른 순서로 정의되어야 한다"""
        stages = list(PipelineStage)
        assert len(stages) == 11
        assert stages[0] == PipelineStage.INGEST
        assert stages[-1] == PipelineStage.SECURITY

    def test_stage_values(self):
        """모든 단계가 고유한 문자열 값을 가져야 한다"""
        values = [s.value for s in PipelineStage]
        assert len(values) == len(set(values))


class TestRecordDocument:
    """기록물 문서 모델 테스트"""

    def test_default_creation(self):
        """기본 생성 시 필수 필드가 초기화되어야 한다"""
        doc = RecordDocument()
        assert doc.id  # UUID 자동 생성
        assert doc.record_type == RecordType.ELECTRONIC
        assert doc.security_level == SecurityLevel.PUBLIC
        assert doc.audit_trail == []

    def test_input_hash(self):
        """동일한 내용은 동일한 해시를 생성해야 한다"""
        doc1 = RecordDocument(title="테스트", content="내용")
        doc2 = RecordDocument(title="테스트", content="내용")
        assert doc1.input_hash == doc2.input_hash

    def test_different_hash(self):
        """다른 내용은 다른 해시를 생성해야 한다"""
        doc1 = RecordDocument(title="문서1", content="내용1")
        doc2 = RecordDocument(title="문서2", content="내용2")
        assert doc1.input_hash != doc2.input_hash


class TestHITLGate:
    """HITL 게이트 테스트"""

    def test_valid_actions(self):
        """유효한 액션으로 HITL 게이트를 생성할 수 있어야 한다"""
        gate = HITLGate("redaction_decision")
        assert gate.action == "redaction_decision"
        assert "제34조" in gate.description

    def test_invalid_action(self):
        """유효하지 않은 액션은 ValueError를 발생시켜야 한다"""
        with pytest.raises(ValueError, match="알 수 없는 HITL 액션"):
            HITLGate("invalid_action")

    def test_request_decision(self):
        """결정 요청이 올바른 구조로 생성되어야 한다"""
        gate = HITLGate("redaction_decision")
        doc = RecordDocument(title="비공개 기록물", content="내용")

        request = gate.request_decision(
            document=doc,
            ai_recommendation="공개",
            confidence=0.85,
            reasoning="30년 경과, PII 없음",
        )

        assert request["action"] == "redaction_decision"
        assert request["ai_recommendation"] == "공개"
        assert request["confidence"] == 0.85
        assert request["status"] == "pending"
        assert request["human_decision"] is None

    def test_pending_decisions_accumulated(self):
        """요청된 결정이 대기열에 누적되어야 한다"""
        gate = HITLGate("disposal_approval")
        doc1 = RecordDocument(title="문서1")
        doc2 = RecordDocument(title="문서2")

        gate.request_decision(doc1, "폐기", 0.9, "보존기간 경과")
        gate.request_decision(doc2, "보존", 0.7, "역사적 가치")

        assert len(gate.pending_decisions) == 2


class TestAuditEntry:
    """감사추적 엔트리 테스트"""

    def test_auto_fields(self):
        """자동 생성 필드가 올바르게 설정되어야 한다"""
        entry = AuditEntry(
            user_id="archivist-001",
            agent_name="nara-ai-classify",
            stage="classify",
            action="process_classify",
        )
        assert entry.decision_id  # UUID 자동
        assert entry.timestamp    # 타임스탬프 자동
        assert entry.user_id == "archivist-001"


class TestPipelineExecutor:
    """파이프라인 실행기 테스트"""

    def test_initialization(self, tmp_path):
        """실행기가 올바르게 초기화되어야 한다"""
        executor = PipelineExecutor(
            workspace_dir=tmp_path / "workspace",
            checkpoint_dir=tmp_path / "checkpoints",
        )
        assert (tmp_path / "workspace").exists()
        assert (tmp_path / "checkpoints").exists()

    def test_pipeline_status(self, tmp_path):
        """파이프라인 상태가 올바르게 반환되어야 한다"""
        executor = PipelineExecutor(workspace_dir=tmp_path / "ws")
        status = executor.get_pipeline_status()

        assert status["total_stages"] == 11
        assert "ingest" in status["stages"]
        assert "security" in status["stages"]

    def test_audit_trail_save(self, tmp_path):
        """감사추적이 파일로 저장되어야 한다"""
        executor = PipelineExecutor(workspace_dir=tmp_path / "ws")
        doc = RecordDocument(title="감사 테스트")
        doc.audit_trail.append(AuditEntry(
            user_id="test",
            agent_name="test-agent",
            stage="test",
            action="test_action",
        ))

        filepath = executor.save_audit_trail(doc)
        assert filepath.exists()
        assert filepath.suffix == ".json"


class TestSecurityLevel:
    """보안 등급 테스트"""

    def test_all_levels(self):
        """4개 보안 등급이 정의되어야 한다"""
        levels = list(SecurityLevel)
        assert len(levels) == 4
        assert SecurityLevel.PUBLIC in levels
        assert SecurityLevel.TOP_SECRET in levels
