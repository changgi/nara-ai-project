"""
메타데이터 자동 생성 에이전트

기록물의 제목, 요약, 키워드, NER(개체명 인식)을 자동 생성한다.
EXAONE 3.5 8B SFT 모델 + RAG를 활용하여 기존 메타데이터 패턴을 학습한다.

성능 목표: ROUGE-1 ≥ 0.85 (제목 98%, 유형 94%, 날짜 89%, 위치 95%)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("nara-ai.agents.metadata")


@dataclass
class NamedEntity:
    """개체명 인식 결과"""
    text: str              # 추출된 텍스트
    entity_type: str       # PERSON, ORGANIZATION, LOCATION, DATE, EVENT
    start_offset: int = 0  # 원문 내 시작 위치
    end_offset: int = 0    # 원문 내 끝 위치
    confidence: float = 0.0


@dataclass
class MetadataResult:
    """메타데이터 생성 결과"""
    title_suggestion: str           # 제목 제안
    summary: str                    # 요약 (200자 이내)
    keywords: list[str]             # 키워드 (5~10개)
    named_entities: list[NamedEntity]  # 개체명 목록
    date_extracted: Optional[str] = None  # 추출된 날짜 (ISO 8601)
    agency_extracted: str = ""      # 추출된 기관명
    confidence: float = 0.0
    reasoning: str = ""
    hitl_pending: bool = False


class MetadataAgent:
    """메타데이터 자동 생성 AI 에이전트"""

    def __init__(
        self,
        vllm_endpoint: str = "http://localhost:8000/v1",
        model_name: str = "nara-classifier-v1",  # 단일 SFT 모델 공유 (QA-C01 수정)
    ):
        self.vllm_endpoint = vllm_endpoint
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(
        self,
        content: str,
        existing_metadata: Optional[dict[str, Any]] = None,
    ) -> MetadataResult:
        """기록물 본문에서 메타데이터를 자동 생성한다."""
        prompt = self._build_prompt(content, existing_metadata)

        try:
            response = await self.client.post(
                f"{self.vllm_endpoint}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "당신은 국가기록원의 메타데이터 전문가입니다. "
                                "기록물에서 제목, 요약, 키워드, 개체명을 추출하세요. "
                                "ISAD(G) 기술 표준과 NAK 메타데이터 요소를 준수하세요. "
                                "JSON 형식으로 응답하세요."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return self._parse_response(response.json())

        except httpx.HTTPError as e:
            logger.error(f"메타데이터 생성 실패: {e}")
            return MetadataResult(
                title_suggestion="",
                summary="",
                keywords=[],
                named_entities=[],
                confidence=0.0,
                reasoning=f"서버 오류: {str(e)}",
                hitl_pending=True,
            )

    def _build_prompt(
        self,
        content: str,
        existing_metadata: Optional[dict[str, Any]],
    ) -> str:
        """메타데이터 생성 프롬프트"""
        content_preview = content[:3000]

        prompt = f"""다음 기록물에서 메타데이터를 추출하세요.

## 기록물 본문
{content_preview}

## 추출 항목
1. title_suggestion: 기록물 제목 (간결하고 정확하게)
2. summary: 200자 이내 요약
3. keywords: 핵심 키워드 5~10개
4. named_entities: 개체명 (인물, 기관, 장소, 날짜, 사건)
5. date_extracted: 문서 생산일 (ISO 8601)
6. agency_extracted: 생산 기관명

## 응답 형식 (JSON)
{{
    "title_suggestion": "...",
    "summary": "...",
    "keywords": ["...", "..."],
    "named_entities": [
        {{"text": "...", "entity_type": "PERSON|ORGANIZATION|LOCATION|DATE|EVENT", "confidence": 0.0~1.0}}
    ],
    "date_extracted": "YYYY-MM-DD",
    "agency_extracted": "...",
    "confidence": 0.0~1.0,
    "reasoning": "..."
}}"""

        if existing_metadata:
            prompt += f"\n\n## 기존 메타데이터 참조\n{json.dumps(existing_metadata, ensure_ascii=False)}"

        return prompt

    def _parse_response(self, api_response: dict[str, Any]) -> MetadataResult:
        """API 응답 파싱"""
        try:
            content = api_response["choices"][0]["message"]["content"]
            data = json.loads(content)

            entities = [
                NamedEntity(
                    text=e.get("text", ""),
                    entity_type=e.get("entity_type", ""),
                    confidence=float(e.get("confidence", 0.0)),
                )
                for e in data.get("named_entities", [])
            ]

            return MetadataResult(
                title_suggestion=data.get("title_suggestion", ""),
                summary=data.get("summary", ""),
                keywords=data.get("keywords", []),
                named_entities=entities,
                date_extracted=data.get("date_extracted"),
                agency_extracted=data.get("agency_extracted", ""),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
            )
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"메타데이터 파싱 실패: {e}")
            return MetadataResult(
                title_suggestion="",
                summary="",
                keywords=[],
                named_entities=[],
                confidence=0.0,
                reasoning=f"파싱 오류: {str(e)}",
                hitl_pending=True,
            )

    async def close(self) -> None:
        await self.client.aclose()
