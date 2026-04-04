"""
YOLO-DocLayout 문서 레이아웃 분석기

문서 이미지에서 텍스트, 표, 그림, 서명 등 영역을 자동 분리한다.
영역별로 최적의 OCR 모델을 라우팅하는 데 사용된다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("nara-ai.ocr.layout")


@dataclass
class BoundingBox:
    """영역 좌표"""
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class LayoutRegion:
    """레이아웃 분석 결과 영역"""
    region_type: str     # text, title, table, figure, signature, header, footer, margin_note
    bbox: BoundingBox
    confidence: float
    page_number: int = 1
    reading_order: int = 0  # 읽기 순서

    @property
    def recommended_ocr_model(self) -> str:
        """영역 유형에 따른 추천 OCR 모델"""
        model_map = {
            "text": "paddleocr",       # 본문 → PaddleOCR (고속)
            "title": "qwen3-vl",       # 제목 → Qwen3-VL (정확)
            "table": "paddleocr",      # 표 → PaddleOCR (구조화)
            "figure": "qwen3-vl",      # 그림 내 텍스트 → Qwen3-VL (비전)
            "signature": "trocr",      # 서명 → TrOCR (필사체)
            "header": "paddleocr",
            "footer": "paddleocr",
            "margin_note": "trocr",    # 난외 주기 → TrOCR (필사체 가능성)
        }
        return model_map.get(self.region_type, "qwen3-vl")


@dataclass
class LayoutResult:
    """전체 레이아웃 분석 결과"""
    image_path: str
    page_number: int = 1
    regions: list[LayoutRegion] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0
    processing_time_ms: float = 0.0
    document_type_guess: str = ""  # 문서 유형 추정

    @property
    def text_regions(self) -> list[LayoutRegion]:
        return [r for r in self.regions if r.region_type in ("text", "title", "header", "footer")]

    @property
    def table_regions(self) -> list[LayoutRegion]:
        return [r for r in self.regions if r.region_type == "table"]

    @property
    def has_handwriting(self) -> bool:
        return any(r.region_type in ("signature", "margin_note") for r in self.regions)


# 레이아웃 카테고리 정의
LAYOUT_CATEGORIES = [
    "text",         # 본문 텍스트
    "title",        # 제목
    "table",        # 표
    "figure",       # 그림/사진
    "signature",    # 서명/도장
    "header",       # 머리글
    "footer",       # 바닥글
    "margin_note",  # 난외 주기
]


class DocumentLayoutDetector:
    """YOLO-DocLayout 기반 문서 레이아웃 분석기"""

    def __init__(
        self,
        model_path: str = "models/yolo-doclayout-v1",
        confidence_threshold: float = 0.5,
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self._model = None

    def _load_model(self) -> None:
        """YOLO 모델 로드 (lazy)"""
        if self._model is None:
            try:
                from ultralytics import YOLO
                self._model = YOLO(self.model_path)
                logger.info(f"YOLO-DocLayout 모델 로드 완료: {self.model_path}")
            except Exception as e:
                logger.error(f"모델 로드 실패: {e}")
                self._model = None

    def detect(self, image_path: str, page_number: int = 1) -> LayoutResult:
        """이미지에서 레이아웃 영역을 검출한다."""
        import time
        start = time.monotonic()

        self._load_model()

        result = LayoutResult(
            image_path=image_path,
            page_number=page_number,
        )

        if self._model is None:
            logger.warning("모델 미로드, 전체 이미지를 단일 텍스트 영역으로 처리")
            result.regions = [LayoutRegion(
                region_type="text",
                bbox=BoundingBox(0, 0, 1000, 1000),
                confidence=0.5,
                page_number=page_number,
            )]
            return result

        try:
            # YOLO 추론
            predictions = self._model.predict(
                image_path,
                conf=self.confidence_threshold,
                verbose=False,
            )

            if predictions and len(predictions) > 0:
                pred = predictions[0]
                result.image_width = pred.orig_shape[1]
                result.image_height = pred.orig_shape[0]

                for i, box in enumerate(pred.boxes):
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]

                    region_type = LAYOUT_CATEGORIES[cls_id] if cls_id < len(LAYOUT_CATEGORIES) else "text"

                    result.regions.append(LayoutRegion(
                        region_type=region_type,
                        bbox=BoundingBox(x1, y1, x2, y2),
                        confidence=conf,
                        page_number=page_number,
                        reading_order=i,
                    ))

            # 읽기 순서 정렬 (위→아래, 왼→오른)
            result.regions.sort(key=lambda r: (r.bbox.y1, r.bbox.x1))
            for i, region in enumerate(result.regions):
                region.reading_order = i

            # 문서 유형 추정
            result.document_type_guess = self._guess_document_type(result)

        except Exception as e:
            logger.error(f"레이아웃 분석 실패: {e}")

        result.processing_time_ms = (time.monotonic() - start) * 1000
        logger.info(
            f"레이아웃 분석 완료: {len(result.regions)}개 영역 "
            f"({result.processing_time_ms:.0f}ms)"
        )
        return result

    def _guess_document_type(self, result: LayoutResult) -> str:
        """영역 구성으로 문서 유형 추정"""
        types = [r.region_type for r in result.regions]

        if types.count("table") > 2:
            return "forms_tables"
        if "signature" in types and "margin_note" in types:
            return "handwritten"
        if result.has_handwriting:
            return "handwritten"
        return "printed_korean"

    def detect_batch(
        self,
        image_paths: list[str],
        start_page: int = 1,
    ) -> list[LayoutResult]:
        """배치 레이아웃 분석"""
        results = []
        for i, path in enumerate(image_paths):
            result = self.detect(path, page_number=start_page + i)
            results.append(result)
        return results
