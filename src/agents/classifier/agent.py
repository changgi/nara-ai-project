"""
기록물 분류 에이전트

BRM(Business Reference Model) 업무기능 매핑을 수행한다.
EXAONE 3.5 8B 파인튜닝 모델을 사용하여 기록물을 16개 대분류,
하위 중분류/소분류로 자동 분류한다.

성능 목표: F1 Score ≥ 0.92
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger("nara-ai.agents.classifier")

# BRM 대분류 코드 매핑
BRM_CATEGORIES = {
    "A": "일반공공행정",
    "B": "공공질서및안전",
    "C": "통일외교",
    "D": "국방",
    "E": "교육",
    "F": "문화및관광",
    "G": "환경",
    "H": "사회복지",
    "I": "보건",
    "J": "농림해양수산",
    "K": "산업중소기업에너지",
    "L": "교통및물류",
    "M": "통신",
    "N": "국토및지역개발",
    "O": "과학기술",
    "P": "재정금융",
}


@dataclass
class ClassificationResult:
    """분류 결과"""
    brm_code: str           # BRM 업무기능 코드 (예: "A01-03")
    brm_name: str           # 업무기능 이름
    confidence: float       # 신뢰도 (0.0 ~ 1.0)
    reasoning: str          # 분류 근거 (AI 기본법 설명가능성)
    alternatives: list[dict[str, Any]]  # 대안 분류 (상위 3개)
    hitl_pending: bool = False  # HITL 필요 여부


class ClassifierAgent:
    """기록물 분류 AI 에이전트"""

    def __init__(
        self,
        vllm_endpoint: str = "http://localhost:8000/v1",
        model_name: str = "nara-classifier-v1",
        confidence_threshold: float = 0.85,
        hitl_threshold: float = 0.70,
    ):
        self.vllm_endpoint = vllm_endpoint
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.hitl_threshold = hitl_threshold
        self.client = httpx.AsyncClient(timeout=30.0)

    async def classify(
        self,
        title: str,
        content: str,
        agency: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> ClassificationResult:
        """기록물을 BRM 업무기능으로 분류한다.

        Args:
            title: 기록물 제목
            content: 기록물 본문 (OCR 텍스트 포함)
            agency: 생산기관명
            context: 추가 컨텍스트 (이전 분류 이력 등)

        Returns:
            ClassificationResult: 분류 결과
        """
        prompt = self._build_classification_prompt(title, content, agency, context)

        try:
            response = await self.client.post(
                f"{self.vllm_endpoint}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "당신은 대한민국 국가기록원의 기록물 분류 전문가입니다. "
                                "BRM(정부기능분류체계)에 따라 기록물을 분류하고, "
                                "분류 근거를 명확히 설명하세요. "
                                "반드시 JSON 형식으로 응답하세요."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            result = response.json()
            return self._parse_response(result)

        except httpx.HTTPError as e:
            logger.error(f"vLLM 호출 실패: {e}")
            return ClassificationResult(
                brm_code="",
                brm_name="분류 실패",
                confidence=0.0,
                reasoning=f"추론 서버 오류: {str(e)}",
                alternatives=[],
                hitl_pending=True,
            )

    def _build_classification_prompt(
        self,
        title: str,
        content: str,
        agency: str,
        context: Optional[dict[str, Any]],
    ) -> str:
        """분류 프롬프트 구성"""
        content_preview = content[:2000] if len(content) > 2000 else content

        prompt = f"""다음 기록물을 BRM 업무기능으로 분류하세요.

## 기록물 정보
- 제목: {title}
- 생산기관: {agency or "미상"}
- 본문 (일부):
{content_preview}

## 응답 형식 (JSON)
{{
    "brm_code": "대분류코드-중분류번호-소분류번호",
    "brm_name": "업무기능 이름",
    "confidence": 0.0~1.0,
    "reasoning": "분류 근거 설명",
    "alternatives": [
        {{"brm_code": "...", "brm_name": "...", "confidence": 0.0~1.0}}
    ]
}}"""

        if context:
            prompt += f"\n\n## 추가 컨텍스트\n{json.dumps(context, ensure_ascii=False)}"

        return prompt

    def _parse_response(self, api_response: dict[str, Any]) -> ClassificationResult:
        """API 응답을 ClassificationResult로 파싱"""
        try:
            content = api_response["choices"][0]["message"]["content"]
            data = json.loads(content)

            confidence = float(data.get("confidence", 0.0))
            hitl_needed = confidence < self.hitl_threshold

            return ClassificationResult(
                brm_code=data.get("brm_code", ""),
                brm_name=data.get("brm_name", ""),
                confidence=confidence,
                reasoning=data.get("reasoning", ""),
                alternatives=data.get("alternatives", []),
                hitl_pending=hitl_needed,
            )
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"응답 파싱 실패: {e}")
            return ClassificationResult(
                brm_code="",
                brm_name="파싱 실패",
                confidence=0.0,
                reasoning=f"응답 파싱 오류: {str(e)}",
                alternatives=[],
                hitl_pending=True,
            )

    async def close(self) -> None:
        """HTTP 클라이언트 정리"""
        await self.client.aclose()
