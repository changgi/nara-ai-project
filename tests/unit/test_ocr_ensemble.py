"""OCR 앙상블 단위 테스트"""

import pytest
from src.ocr.pipeline.ocr_ensemble import (
    OCREnsemble, DocumentCategory, OCRResult,
)
from src.ocr.pipeline.layout_detector import (
    DocumentLayoutDetector, LayoutRegion, BoundingBox, LAYOUT_CATEGORIES,
)
from src.ocr.postprocess.corrector import (
    OCRPostProcessor, DOMAIN_CORRECTIONS, HANJA_MAPPING,
)


class TestOCREnsemble:
    def test_model_routing_all_categories(self):
        """모든 문서 유형에 모델 라우팅이 정의되어야 한다"""
        assert len(OCREnsemble.MODEL_ROUTING) == 7
        for cat in DocumentCategory:
            assert cat in OCREnsemble.MODEL_ROUTING
            weights = OCREnsemble.MODEL_ROUTING[cat]
            assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_cer_targets_all_categories(self):
        """모든 문서 유형에 CER 목표가 정의되어야 한다"""
        for cat in DocumentCategory:
            assert cat in OCREnsemble.CER_TARGETS
            assert 0.0 < OCREnsemble.CER_TARGETS[cat] <= 0.15

    def test_document_categories(self):
        """7종 문서 유형이 정의되어야 한다"""
        assert len(DocumentCategory) == 7
        assert DocumentCategory.PRINTED_KOREAN.value == "printed_korean"
        assert DocumentCategory.HANJA_MIXED.value == "hanja_mixed"


class TestLayoutDetector:
    def test_layout_categories(self):
        """8종 레이아웃 카테고리가 정의되어야 한다"""
        assert len(LAYOUT_CATEGORIES) == 8
        assert "text" in LAYOUT_CATEGORIES
        assert "table" in LAYOUT_CATEGORIES
        assert "signature" in LAYOUT_CATEGORIES

    def test_bounding_box(self):
        """BoundingBox 속성 계산이 올바라야 한다"""
        bbox = BoundingBox(10, 20, 110, 120)
        assert bbox.width == 100
        assert bbox.height == 100
        assert bbox.area == 10000

    def test_region_ocr_model_recommendation(self):
        """영역 유형별 OCR 모델 추천이 올바라야 한다"""
        text_region = LayoutRegion("text", BoundingBox(0, 0, 100, 100), 0.9)
        assert text_region.recommended_ocr_model == "paddleocr"

        sig_region = LayoutRegion("signature", BoundingBox(0, 0, 100, 100), 0.9)
        assert sig_region.recommended_ocr_model == "trocr"

        title_region = LayoutRegion("title", BoundingBox(0, 0, 100, 100), 0.9)
        assert title_region.recommended_ocr_model == "qwen3-vl"


class TestOCRPostProcessor:
    @pytest.fixture
    def processor(self):
        return OCRPostProcessor()

    def test_domain_correction(self, processor):
        """도메인 사전 교정이 동작해야 한다"""
        result = processor.correct("행정안전뷰에서 발행한 문서")
        assert "행정안전부" in result.corrected
        assert len(result.corrections) > 0

    def test_hanja_annotation(self, processor):
        """한자 병기가 추가되어야 한다"""
        result = processor.correct("國家 기록관리")
        assert "國家(국가)" in result.corrected

    def test_clean_text_no_correction(self, processor):
        """교정이 필요 없는 텍스트는 원본 유지"""
        text = "정상적인 한국어 텍스트입니다."
        result = processor.correct(text)
        assert result.corrected == text
        assert len(result.corrections) == 0

    def test_date_extraction(self, processor):
        """날짜 추출이 동작해야 한다"""
        dates = processor.extract_dates("2024년 3월 15일에 작성된 문서")
        assert len(dates) >= 1

    def test_agency_extraction(self, processor):
        """기관명 추출이 동작해야 한다"""
        agencies = processor.extract_agencies("행정안전부와 국가기록원이 공동 작성")
        assert "행정안전부" in agencies
        assert "국가기록원" in agencies

    def test_domain_dict_not_empty(self):
        """도메인 사전이 비어있지 않아야 한다"""
        assert len(DOMAIN_CORRECTIONS) > 0
        assert len(HANJA_MAPPING) > 0
