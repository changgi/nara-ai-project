"""
NARA-AI 엔드투엔드 모듈 통합 테스트

서비스 없이 실행 가능한 모듈 간 연동 테스트.
실제 파이프라인 흐름을 시뮬레이션한다.
"""

import json
import pytest
from pathlib import Path


class TestPipelineDataFlow:
    """파이프라인 데이터 흐름 테스트"""

    def test_document_through_pipeline_stages(self):
        """문서가 파이프라인 단계를 통과하며 데이터가 누적되어야 한다"""
        from src.pipeline.pipeline_executor import (
            RecordDocument, RecordType, SecurityLevel, AuditEntry, PipelineStage,
        )

        doc = RecordDocument(
            title="테스트 문서",
            content="행정안전부에서 작성한 정부혁신 추진계획",
            record_type=RecordType.ELECTRONIC,
            security_level=SecurityLevel.PUBLIC,
            agency="행정안전부",
        )

        # 1단계: 수집 후 감사추적 추가
        doc.audit_trail.append(AuditEntry(
            user_id="test", agent_name="ingest", stage="ingest", action="collect",
            input_hash=doc.input_hash, output_summary="수집 완료",
        ))
        assert len(doc.audit_trail) == 1

        # 5단계: 분류 결과 추가
        doc.brm_code = "A01"
        doc.keywords = ["정부혁신", "행정안전부"]
        doc.audit_trail.append(AuditEntry(
            user_id="test", agent_name="classifier", stage="classify",
            action="classify", confidence=0.95,
        ))
        assert doc.brm_code == "A01"
        assert len(doc.audit_trail) == 2

        # 7단계: 비밀해제 (공개 문서이므로 패스)
        assert doc.security_level == SecurityLevel.PUBLIC

        # 감사추적이 누적되어야 한다
        assert all(e.agent_name for e in doc.audit_trail)


class TestPIIToMasking:
    """PII 탐지 → 마스킹 → 검증 전체 흐름"""

    def test_full_pii_flow(self):
        from src.agents.redaction.agent import RedactionAgent
        from src.agents.quality.agent import QualityAgent

        agent = RedactionAgent()

        # PII가 포함된 문서
        content = "신청인 홍길동(850101-1234567)의 연락처는 010-1111-2222입니다."
        detections = agent.detect_pii(content)
        masked = agent.mask_content(content, detections)

        # PII가 탐지되어야 한다
        assert len(detections) >= 2
        assert any(d.pii_type == "resident_id" for d in detections)

        # 마스킹된 텍스트에 원본 PII가 없어야 한다
        assert "1234567" not in masked

        # 품질 검증: 마스킹된 문서는 PII 검증 통과해야 한다
        import asyncio
        qa = QualityAgent()
        doc_data = {
            "content": masked,
            "ocr_text": "",
            "brm_code": "A01",
            "classification_confidence": 0.9,
            "title": "테스트",
            "agency": "테스트기관",
            "keywords": ["테스트"],
            "summary": "테스트 문서",
            "security_level": "restricted",
            "pii_detections": [{"type": d.pii_type} for d in detections],
            "audit_trail": [{"timestamp": "2024-01-01", "agent_name": "test"}],
        }
        result = asyncio.run(qa.verify(doc_data))
        # PII가 마스킹되었으므로 PII 체크는 통과해야 한다
        pii_check = [c for c in result.checks if c["check"] == "pii"]
        assert pii_check[0]["passed"]


class TestOCRToCorrection:
    """OCR 결과 → 후처리 교정 흐름"""

    def test_ocr_correction_flow(self):
        from src.ocr.postprocess.corrector import OCRPostProcessor

        processor = OCRPostProcessor()

        # OCR이 잘못 인식한 텍스트
        ocr_output = "국가기록완에서 발행한 보존기갼 관련 지침"
        result = processor.correct(ocr_output)

        assert "국가기록원" in result.corrected
        assert "보존기간" in result.corrected
        assert result.confidence > 0.9

    def test_hanja_document_flow(self):
        from src.ocr.postprocess.corrector import OCRPostProcessor

        processor = OCRPostProcessor()

        ocr_output = "本 文書는 國家의 重要 記錄이다."
        result = processor.correct(ocr_output)

        # 한자에 한글 병기가 추가되어야 한다
        assert "國家(국가)" in result.corrected
        assert "記錄(기록)" in result.corrected

    def test_structurize_document(self):
        from src.ocr.postprocess.corrector import OCRPostProcessor

        processor = OCRPostProcessor()
        text = """정부혁신 추진계획

1. 디지털 정부혁신
정부 서비스의 디지털 전환을 추진한다.

2. 국민참여 확대
국민이 정책 결정에 참여할 수 있는 채널을 확대한다."""

        doc = processor.structurize(text)
        assert doc.title == "정부혁신 추진계획"
        assert len(doc.sections) >= 2


class TestBenchmarkReportFormat:
    """벤치마크 보고서 형식 검증"""

    def test_report_json_format(self):
        from src.pipeline.eval.benchmark import run_benchmark

        report = run_benchmark(
            test_data_dir="data/test",
            output_path="_workspace/test_benchmark.json",
        )

        report_dict = report.to_dict()

        assert "timestamp" in report_dict
        assert "all_passed" in report_dict
        assert "results" in report_dict
        assert isinstance(report_dict["results"], list)

        # JSON 직렬화 가능해야 한다
        json_str = json.dumps(report_dict, ensure_ascii=False)
        assert len(json_str) > 0

        # 파일이 생성되어야 한다
        assert Path("_workspace/test_benchmark.json").exists()


class TestRiCCMStandard:
    """RiC-CM 표준 모델 테스트"""

    def test_entity_to_spanner_node(self):
        from src.standards.ric_cm.entities import RiCEntity, EntityType

        entity = RiCEntity(
            id="person-001",
            entity_type=EntityType.PERSON,
            name="Kim Gu",
            name_kr="김구",
            description="대한민국 임시정부 주석",
            date_range=("1876-08-29", "1949-06-26"),
        )

        node = entity.to_spanner_node()
        assert node["id"] == "person-001"
        assert node["type"] == "Person"
        assert node["name_kr"] == "김구"
        assert node["date_start"] == "1876-08-29"

    def test_relation_to_spanner_edge(self):
        from src.standards.ric_cm.entities import RiCRelation, RelationType

        relation = RiCRelation(
            source_id="person-001",
            target_id="org-001",
            relation_type=RelationType.CREATED_BY,
            certainty=0.95,
        )

        edge = relation.to_spanner_edge()
        assert edge["source_id"] == "person-001"
        assert edge["type"] == "createdBy"
        assert edge["certainty"] == 0.95
