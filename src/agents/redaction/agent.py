"""
비밀해제 심사 에이전트

공공기록물법 제34조에 따라 비공개 기록물의 공개 전환 여부를 심사 지원한다.
PII(개인식별정보) 탐지, 보안 등급 검토, 공개 적합성 평가를 수행한다.

중요: 이 에이전트의 결과는 AI 추천이며, 최종 결정은 반드시 인간이 수행한다. (HITL 필수)
성능 목표: Precision ≥ 0.95 (PII 탐지)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("nara-ai.agents.redaction")


# PII 패턴 (한국 개인정보보호법 기반)
PII_PATTERNS = {
    "resident_id": {
        "pattern": r"\d{6}-[1-4]\d{6}",
        "name": "주민등록번호",
        "severity": "critical",
    },
    "phone": {
        "pattern": r"01[0-9]-?\d{3,4}-?\d{4}",
        "name": "전화번호",
        "severity": "high",
    },
    "email": {
        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "name": "이메일",
        "severity": "medium",
    },
    "passport": {
        "pattern": r"[A-Z]{1,2}\d{7,8}",
        "name": "여권번호",
        "severity": "critical",
    },
    "driver_license": {
        "pattern": r"\d{2}-\d{6}-\d{2}",
        "name": "운전면허번호",
        "severity": "critical",
    },
    "account": {
        "pattern": r"\d{3,4}-\d{2,6}-\d{2,6}",
        "name": "계좌번호",
        "severity": "high",
    },
}


@dataclass
class PIIDetection:
    """PII 탐지 결과"""
    pii_type: str          # resident_id, phone, email, etc.
    pii_name: str          # 한국어 이름
    matched_text: str      # 매칭된 텍스트 (마스킹 처리)
    severity: str          # critical, high, medium, low
    start_offset: int = 0
    end_offset: int = 0
    masked_text: str = ""  # 가명처리된 텍스트


@dataclass
class RedactionResult:
    """비밀해제 심사 결과"""
    recommendation: str           # "공개", "부분공개", "비공개 유지"
    confidence: float
    reasoning: str
    pii_detections: list[PIIDetection]
    security_concerns: list[str]  # 보안 우려사항
    legal_basis: str              # 법적 근거 (공공기록물법 조항)
    hitl_pending: bool = True     # 항상 True (비밀해제는 HITL 필수)
    masked_content: str = ""      # PII 마스킹된 본문


class RedactionAgent:
    """비밀해제 심사 AI 에이전트

    주의: 이 에이전트의 모든 결과는 AI 추천이며,
    최종 비밀해제 결정은 반드시 인간(기록물관리 전문가)이 수행한다.
    """

    def __init__(
        self,
        vllm_endpoint: str = "http://localhost:8000/v1",
        model_name: str = "nara-classifier-v1",  # 단일 SFT 모델 공유 (QA-C01 수정)
    ):
        self.vllm_endpoint = vllm_endpoint
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=30.0)
        self._compiled_patterns = {
            name: re.compile(info["pattern"])
            for name, info in PII_PATTERNS.items()
        }

    def detect_pii(self, text: str) -> list[PIIDetection]:
        """PII 자동 탐지 (정규식 기반 1차 스캐닝)"""
        detections: list[PIIDetection] = []

        for pii_type, pattern in self._compiled_patterns.items():
            info = PII_PATTERNS[pii_type]
            for match in pattern.finditer(text):
                matched = match.group()
                # 가명처리: 앞 2자리만 노출, 나머지 마스킹
                masked = matched[:2] + "*" * (len(matched) - 2)

                detections.append(PIIDetection(
                    pii_type=pii_type,
                    pii_name=info["name"],
                    matched_text=masked,  # 원본 저장하지 않음 (보안)
                    severity=info["severity"],
                    start_offset=match.start(),
                    end_offset=match.end(),
                    masked_text=masked,
                ))

        logger.info(f"PII 탐지 완료: {len(detections)}건 발견")
        return detections

    def mask_content(self, text: str, detections: list[PIIDetection]) -> str:
        """PII가 마스킹된 본문 생성 (가명처리, 개인정보보호법 제28조의2)"""
        masked = text
        # 역순으로 치환 (offset 보존)
        for det in sorted(detections, key=lambda d: d.start_offset, reverse=True):
            original = text[det.start_offset:det.end_offset]
            masked = masked[:det.start_offset] + det.masked_text + masked[det.end_offset:]
        return masked

    async def review(
        self,
        title: str,
        content: str,
        current_level: str = "secret",
        years_since_creation: int = 0,
    ) -> RedactionResult:
        """비밀해제 심사를 수행한다. 결과는 AI 추천이며 HITL 필수."""
        # 1단계: PII 탐지
        pii_detections = self.detect_pii(content)
        masked_content = self.mask_content(content, pii_detections)

        # 2단계: AI 기반 공개 적합성 평가
        try:
            prompt = self._build_review_prompt(
                title, masked_content, current_level, years_since_creation, pii_detections
            )

            response = await self.client.post(
                f"{self.vllm_endpoint}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "당신은 국가기록원의 비밀해제 심사 전문가입니다. "
                                "공공기록물법 제33조~35조에 근거하여 비공개 기록물의 "
                                "공개 전환 여부를 검토하세요. "
                                "주의: 당신의 답변은 AI 추천이며, 최종 결정은 인간이 합니다. "
                                "JSON 형식으로 응답하세요."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            result = self._parse_response(response.json(), pii_detections, masked_content)
            return result

        except httpx.HTTPError as e:
            logger.error(f"비밀해제 심사 실패: {e}")
            return RedactionResult(
                recommendation="비공개 유지",
                confidence=0.0,
                reasoning=f"AI 심사 실패: {str(e)}. 수동 심사 필요.",
                pii_detections=pii_detections,
                security_concerns=["AI 심사 불가"],
                legal_basis="공공기록물법 제34조",
                hitl_pending=True,
                masked_content=masked_content,
            )

    def _build_review_prompt(
        self,
        title: str,
        masked_content: str,
        current_level: str,
        years: int,
        pii_detections: list[PIIDetection],
    ) -> str:
        """비밀해제 심사 프롬프트"""
        pii_summary = ", ".join(
            f"{d.pii_name}({d.severity})" for d in pii_detections
        ) if pii_detections else "없음"

        return f"""다음 비공개 기록물의 공개 전환 적합성을 검토하세요.

## 기록물 정보
- 제목: {title}
- 현재 보안 등급: {current_level}
- 생산 후 경과 연수: {years}년
- PII 탐지 결과: {pii_summary}

## 본문 (PII 마스킹 처리됨)
{masked_content[:2000]}

## 검토 기준
1. 공공기록물법 제33조~35조 적용
2. 30년 경과 기록물은 원칙적 공개 (제35조)
3. PII 포함 시 부분공개 고려
4. 국가안보/외교 관련 내용은 비공개 유지

## 응답 형식 (JSON)
{{
    "recommendation": "공개|부분공개|비공개 유지",
    "confidence": 0.0~1.0,
    "reasoning": "검토 근거 상세 설명",
    "security_concerns": ["우려사항1", "..."],
    "legal_basis": "근거 법률 조항"
}}"""

    def _parse_response(
        self,
        api_response: dict[str, Any],
        pii_detections: list[PIIDetection],
        masked_content: str,
    ) -> RedactionResult:
        """API 응답 파싱"""
        try:
            content = api_response["choices"][0]["message"]["content"]
            data = json.loads(content)

            return RedactionResult(
                recommendation=data.get("recommendation", "비공개 유지"),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
                pii_detections=pii_detections,
                security_concerns=data.get("security_concerns", []),
                legal_basis=data.get("legal_basis", "공공기록물법 제34조"),
                hitl_pending=True,  # 비밀해제는 항상 HITL 필수
                masked_content=masked_content,
            )
        except (KeyError, json.JSONDecodeError) as e:
            return RedactionResult(
                recommendation="비공개 유지",
                confidence=0.0,
                reasoning=f"응답 파싱 오류: {str(e)}",
                pii_detections=pii_detections,
                security_concerns=["파싱 실패"],
                legal_basis="공공기록물법 제34조",
                hitl_pending=True,
                masked_content=masked_content,
            )

    async def close(self) -> None:
        await self.client.aclose()
