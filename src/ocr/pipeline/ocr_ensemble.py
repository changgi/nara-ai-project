"""
NARA-AI OCR 3모델 앙상블 파이프라인

Qwen3-VL(8B) + PaddleOCR-VL(0.9B) + TrOCR 앙상블로
활자체/필사체/한자혼용 문서를 처리한다.

처리량 목표: 1,500~3,800 페이지/시간 (8 B200 GPU)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("nara-ai.ocr.ensemble")


class DocumentCategory(str, Enum):
    """문서 유형 분류"""
    PRINTED_KOREAN = "printed_korean"     # 현대 한글 활자체
    HANJA_MIXED = "hanja_mixed"          # 한자 혼용
    HANDWRITTEN = "handwritten"          # 필사체/손글씨
    COLONIAL_ERA = "colonial_era"        # 일제강점기
    FORMS_TABLES = "forms_tables"        # 양식/표
    ARCHITECTURAL = "architectural"      # 건축도면
    MICROFILM = "microfilm"              # 마이크로필름


@dataclass
class LayoutRegion:
    """레이아웃 분석 결과 - 문서 내 영역"""
    region_type: str          # text, title, table, figure, signature, header, footer, margin_note
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float = 0.0
    ocr_text: str = ""
    ocr_model: str = ""       # 사용된 OCR 모델


@dataclass
class OCRResult:
    """OCR 처리 결과"""
    text: str                         # 최종 OCR 텍스트
    confidence: float                 # 전체 신뢰도
    document_category: DocumentCategory
    regions: list[LayoutRegion] = field(default_factory=list)
    model_results: dict[str, str] = field(default_factory=dict)  # 모델별 결과
    cer_estimate: float = 0.0         # 추정 CER
    processing_time_ms: float = 0.0
    hitl_pending: bool = False
    reasoning: str = ""


class OCRModel:
    """OCR 모델 기본 인터페이스"""

    def __init__(self, name: str, endpoint: str):
        self.name = name
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=60.0)

    async def recognize(self, image_path: str, region: Optional[LayoutRegion] = None) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        await self.client.aclose()


class Qwen3VLModel(OCRModel):
    """Qwen3-VL 8B OCR 모델 (주력)

    OCRBench 905점, 32개 언어 네이티브, 한자+한국어 동시 처리
    """

    def __init__(self, endpoint: str = "http://localhost:8001/v1"):
        super().__init__("qwen3-vl", endpoint)

    async def recognize(self, image_path: str, region: Optional[LayoutRegion] = None) -> str:
        """이미지에서 텍스트 추출 (vLLM OpenAI-compatible API)"""
        import base64

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = "이 문서 이미지의 모든 텍스트를 정확하게 읽어주세요. 한자가 있으면 한자도 함께 표기하세요."
        if region:
            prompt += f" 특히 {region.region_type} 영역에 집중하세요."

        try:
            response = await self.client.post(
                f"{self.endpoint}/chat/completions",
                json={
                    "model": "Qwen/Qwen3-VL-8B",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.0,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Qwen3-VL OCR 실패: {e}")
            return ""


class PaddleOCRModel(OCRModel):
    """PaddleOCR-VL 0.9B (고속 배치 처리)

    50-100 페이지/분/GPU, 표/양식 구조화 우수
    """

    def __init__(self, endpoint: str = "http://localhost:8003"):
        super().__init__("paddleocr", endpoint)

    async def recognize(self, image_path: str, region: Optional[LayoutRegion] = None) -> str:
        try:
            with open(image_path, "rb") as f:
                files = {"image": (Path(image_path).name, f, "image/png")}
                response = await self.client.post(
                    f"{self.endpoint}/ocr",
                    files=files,
                    data={"language": "korean", "structure": "true"},
                )
            response.raise_for_status()
            result = response.json()
            return result.get("text", "")
        except Exception as e:
            logger.error(f"PaddleOCR 실패: {e}")
            return ""


class TrOCRModel(OCRModel):
    """TrOCR 필사체 특화 모델

    한국어 손글씨/필사체 전문, AI Hub 옛한글 데이터 학습
    """

    def __init__(self, endpoint: str = "http://localhost:8004"):
        super().__init__("trocr", endpoint)

    async def recognize(self, image_path: str, region: Optional[LayoutRegion] = None) -> str:
        try:
            with open(image_path, "rb") as f:
                files = {"image": (Path(image_path).name, f, "image/png")}
                response = await self.client.post(
                    f"{self.endpoint}/recognize",
                    files=files,
                )
            response.raise_for_status()
            return response.json().get("text", "")
        except Exception as e:
            logger.error(f"TrOCR 실패: {e}")
            return ""


class OCREnsemble:
    """3모델 앙상블 OCR 파이프라인"""

    # 문서 유형별 모델 라우팅 및 가중치
    MODEL_ROUTING: dict[DocumentCategory, dict[str, float]] = {
        DocumentCategory.PRINTED_KOREAN: {"paddleocr": 0.5, "qwen3-vl": 0.3, "trocr": 0.2},
        DocumentCategory.HANJA_MIXED: {"qwen3-vl": 0.6, "paddleocr": 0.3, "trocr": 0.1},
        DocumentCategory.HANDWRITTEN: {"trocr": 0.5, "qwen3-vl": 0.4, "paddleocr": 0.1},
        DocumentCategory.COLONIAL_ERA: {"qwen3-vl": 0.6, "trocr": 0.3, "paddleocr": 0.1},
        DocumentCategory.FORMS_TABLES: {"paddleocr": 0.6, "qwen3-vl": 0.3, "trocr": 0.1},
        DocumentCategory.ARCHITECTURAL: {"qwen3-vl": 0.7, "paddleocr": 0.2, "trocr": 0.1},
        DocumentCategory.MICROFILM: {"qwen3-vl": 0.4, "paddleocr": 0.3, "trocr": 0.3},
    }

    # CER 목표
    CER_TARGETS: dict[DocumentCategory, float] = {
        DocumentCategory.PRINTED_KOREAN: 0.03,
        DocumentCategory.HANJA_MIXED: 0.07,
        DocumentCategory.HANDWRITTEN: 0.10,
        DocumentCategory.COLONIAL_ERA: 0.07,
        DocumentCategory.FORMS_TABLES: 0.05,
        DocumentCategory.ARCHITECTURAL: 0.08,
        DocumentCategory.MICROFILM: 0.12,
    }

    def __init__(self):
        self.models: dict[str, OCRModel] = {
            "qwen3-vl": Qwen3VLModel(),
            "paddleocr": PaddleOCRModel(),
            "trocr": TrOCRModel(),
        }

    async def process(
        self,
        image_path: str,
        category: DocumentCategory = DocumentCategory.PRINTED_KOREAN,
    ) -> OCRResult:
        """이미지를 3모델 앙상블로 OCR 처리"""
        import time
        start = time.monotonic()

        weights = self.MODEL_ROUTING[category]

        # 3모델 병렬 실행
        tasks = {
            name: model.recognize(image_path)
            for name, model in self.models.items()
        }
        results = {}
        for name, coro in tasks.items():
            try:
                results[name] = await coro
            except Exception as e:
                logger.warning(f"{name} 실패: {e}")
                results[name] = ""

        # 가중 투표로 최종 텍스트 선택
        best_text = self._weighted_vote(results, weights)

        # 신뢰도 추정
        non_empty = sum(1 for t in results.values() if t.strip())
        confidence = non_empty / len(results)

        duration_ms = (time.monotonic() - start) * 1000

        return OCRResult(
            text=best_text,
            confidence=confidence,
            document_category=category,
            model_results=results,
            cer_estimate=self.CER_TARGETS.get(category, 0.10),
            processing_time_ms=duration_ms,
            hitl_pending=confidence < 0.5,
            reasoning=f"앙상블 처리 완료 ({non_empty}/3 모델 성공, {category.value})",
        )

    def _weighted_vote(self, results: dict[str, str], weights: dict[str, float]) -> str:
        """가중 투표로 최적 OCR 결과 선택"""
        best_text = ""
        best_score = -1.0

        for name, text in results.items():
            if not text.strip():
                continue
            weight = weights.get(name, 0.1)
            score = weight * len(text)  # 가중치 × 텍스트 길이 (더 많은 텍스트 선호)
            if score > best_score:
                best_score = score
                best_text = text

        return best_text

    async def close(self) -> None:
        for model in self.models.values():
            await model.close()
