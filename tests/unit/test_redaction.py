"""
비밀해제 에이전트 단위 테스트

PII 탐지 및 가명처리 기능을 검증한다.
공공기록물법 제34조 및 개인정보보호법 제28조의2 준수.
"""

import pytest
from src.agents.redaction.agent import RedactionAgent, PII_PATTERNS


class TestPIIDetection:
    """PII 탐지 테스트"""

    @pytest.fixture
    def agent(self):
        return RedactionAgent()

    def test_resident_id_detection(self, agent):
        """주민등록번호를 탐지해야 한다"""
        text = "신청인 주민등록번호는 850101-1234567 입니다."
        detections = agent.detect_pii(text)
        assert len(detections) >= 1
        assert any(d.pii_type == "resident_id" for d in detections)
        assert any(d.severity == "critical" for d in detections)

    def test_phone_detection(self, agent):
        """전화번호를 탐지해야 한다"""
        text = "연락처: 010-1234-5678"
        detections = agent.detect_pii(text)
        assert len(detections) >= 1
        assert any(d.pii_type == "phone" for d in detections)

    def test_email_detection(self, agent):
        """이메일을 탐지해야 한다"""
        text = "이메일: test@example.com"
        detections = agent.detect_pii(text)
        assert len(detections) >= 1
        assert any(d.pii_type == "email" for d in detections)

    def test_no_pii_clean_text(self, agent):
        """PII가 없는 텍스트에서는 탐지하지 않아야 한다"""
        text = "대한민국 국가기록원은 기록물 관리를 담당한다."
        detections = agent.detect_pii(text)
        assert len(detections) == 0

    def test_masking_preserves_length(self, agent):
        """마스킹 후 텍스트 길이가 유지되어야 한다 (가명처리)"""
        text = "주민번호 850101-1234567 확인"
        detections = agent.detect_pii(text)
        masked = agent.mask_content(text, detections)
        # 마스킹된 텍스트가 원본과 같은 길이여야 한다
        assert len(masked) == len(text)

    def test_masked_text_not_original(self, agent):
        """마스킹된 텍스트에 원본 PII가 포함되지 않아야 한다"""
        text = "연락처 010-9876-5432 입니다"
        detections = agent.detect_pii(text)
        masked = agent.mask_content(text, detections)
        assert "9876-5432" not in masked

    def test_multiple_pii(self, agent):
        """여러 PII가 동시에 탐지되어야 한다"""
        text = "주민번호 850101-1234567, 전화 010-1111-2222, 이메일 a@b.com"
        detections = agent.detect_pii(text)
        types = {d.pii_type for d in detections}
        assert "resident_id" in types
        assert "phone" in types
        assert "email" in types


class TestPIIPatterns:
    """PII 패턴 유효성 테스트"""

    def test_all_patterns_have_required_fields(self):
        """모든 PII 패턴에 필수 필드가 있어야 한다"""
        for name, info in PII_PATTERNS.items():
            assert "pattern" in info, f"{name}: pattern 누락"
            assert "name" in info, f"{name}: name 누락"
            assert "severity" in info, f"{name}: severity 누락"
            assert info["severity"] in ("critical", "high", "medium", "low")
