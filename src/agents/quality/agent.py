"""
품질 검증 에이전트

11단계 파이프라인의 각 단계 출력을 검증한다.
분류 신뢰도, OCR 품질, 메타데이터 완전성, 보안 준수를 점검한다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("nara-ai.agents.quality")


@dataclass
class QualityCheckResult:
    """품질 검증 결과"""
    passed: bool
    score: float                    # 0.0 ~ 1.0
    checks: list[dict[str, Any]]    # 개별 검증 항목
    critical_issues: list[str]      # 즉시 수정 필요
    warnings: list[str]             # 권고사항
    hitl_pending: bool = False
    reasoning: str = ""
    confidence: float = 0.0


# 품질 기준
QUALITY_THRESHOLDS = {
    "classification_confidence": 0.85,
    "ocr_confidence": 0.70,
    "metadata_completeness": 0.80,
    "pii_check_required": True,
    "audit_trail_required": True,
}


class QualityAgent:
    """품질 검증 AI 에이전트"""

    def __init__(self, thresholds: dict[str, Any] | None = None):
        self.thresholds = thresholds or QUALITY_THRESHOLDS

    async def verify(self, document: dict[str, Any]) -> QualityCheckResult:
        """문서의 품질을 종합 검증한다."""
        checks: list[dict[str, Any]] = []
        critical: list[str] = []
        warnings: list[str] = []
        score = 1.0

        # 1. 분류 품질
        cls_result = self._check_classification(document)
        checks.append(cls_result)
        if not cls_result["passed"]:
            score -= 0.2
            if cls_result.get("severity") == "critical":
                critical.append(cls_result["message"])
            else:
                warnings.append(cls_result["message"])

        # 2. OCR 품질
        ocr_result = self._check_ocr(document)
        checks.append(ocr_result)
        if not ocr_result["passed"]:
            score -= 0.2
            warnings.append(ocr_result["message"])

        # 3. 메타데이터 완전성
        meta_result = self._check_metadata(document)
        checks.append(meta_result)
        if not meta_result["passed"]:
            score -= 0.15
            warnings.append(meta_result["message"])

        # 4. PII 검증
        pii_result = self._check_pii(document)
        checks.append(pii_result)
        if not pii_result["passed"]:
            score -= 0.25
            critical.append(pii_result["message"])

        # 5. 감사추적 검증
        audit_result = self._check_audit_trail(document)
        checks.append(audit_result)
        if not audit_result["passed"]:
            score -= 0.1
            critical.append(audit_result["message"])

        # 6. 보안 등급 적합성
        security_result = self._check_security_level(document)
        checks.append(security_result)
        if not security_result["passed"]:
            score -= 0.2
            critical.append(security_result["message"])

        score = max(0.0, score)
        passed = score >= 0.7 and len(critical) == 0

        return QualityCheckResult(
            passed=passed,
            score=score,
            checks=checks,
            critical_issues=critical,
            warnings=warnings,
            hitl_pending=not passed,
            reasoning=f"품질 점수 {score:.2f}, 심각 이슈 {len(critical)}건, 경고 {len(warnings)}건",
            confidence=score,
        )

    def _check_classification(self, doc: dict[str, Any]) -> dict[str, Any]:
        """분류 결과 검증"""
        brm_code = doc.get("brm_code", "")
        confidence = doc.get("classification_confidence", 0.0)
        threshold = self.thresholds["classification_confidence"]

        if not brm_code:
            return {"check": "classification", "passed": False, "severity": "critical",
                    "message": "BRM 분류 코드 없음"}
        if confidence < threshold:
            return {"check": "classification", "passed": False, "severity": "warning",
                    "message": f"분류 신뢰도 낮음: {confidence:.2f} (기준: {threshold})"}
        return {"check": "classification", "passed": True, "message": f"분류 OK ({brm_code}, {confidence:.2f})"}

    def _check_ocr(self, doc: dict[str, Any]) -> dict[str, Any]:
        """OCR 결과 검증"""
        ocr_text = doc.get("ocr_text", "")
        confidence = doc.get("ocr_confidence", 0.0)
        threshold = self.thresholds["ocr_confidence"]

        if doc.get("record_type") in ("paper", "photo", "microfilm") and not ocr_text:
            return {"check": "ocr", "passed": False, "severity": "warning",
                    "message": "비전자기록물에 OCR 결과 없음"}
        if ocr_text and confidence < threshold:
            return {"check": "ocr", "passed": False, "severity": "warning",
                    "message": f"OCR 신뢰도 낮음: {confidence:.2f}"}
        return {"check": "ocr", "passed": True, "message": "OCR OK"}

    def _check_metadata(self, doc: dict[str, Any]) -> dict[str, Any]:
        """메타데이터 완전성 검증"""
        required = ["title", "agency", "keywords", "summary"]
        present = sum(1 for f in required if doc.get(f))
        completeness = present / len(required) if required else 0
        threshold = self.thresholds["metadata_completeness"]

        if completeness < threshold:
            missing = [f for f in required if not doc.get(f)]
            return {"check": "metadata", "passed": False, "severity": "warning",
                    "message": f"메타데이터 불완전 ({completeness:.0%}): 누락={missing}"}
        return {"check": "metadata", "passed": True, "message": f"메타데이터 OK ({completeness:.0%})"}

    def _check_pii(self, doc: dict[str, Any]) -> dict[str, Any]:
        """PII 처리 검증"""
        pii_detections = doc.get("pii_detections", [])
        content = doc.get("content", "") + doc.get("ocr_text", "")

        # 미처리 PII 패턴 체크
        raw_patterns = [
            (r'\d{6}-[1-4]\d{6}', "주민등록번호"),
        ]
        unmasked = []
        for pattern, name in raw_patterns:
            if re.search(pattern, content):
                unmasked.append(name)

        if unmasked:
            return {"check": "pii", "passed": False, "severity": "critical",
                    "message": f"미마스킹 PII 발견: {', '.join(unmasked)}"}
        return {"check": "pii", "passed": True, "message": "PII 검증 OK"}

    def _check_audit_trail(self, doc: dict[str, Any]) -> dict[str, Any]:
        """감사추적 검증 (AI 기본법 투명성)"""
        audit = doc.get("audit_trail", [])
        if not audit:
            return {"check": "audit", "passed": False, "severity": "critical",
                    "message": "감사추적 없음 (AI 기본법 위반)"}

        # 필수 필드 확인
        for entry in audit:
            if not entry.get("timestamp") or not entry.get("agent_name"):
                return {"check": "audit", "passed": False, "severity": "critical",
                        "message": "감사추적 필수 필드 누락 (timestamp/agent_name)"}

        return {"check": "audit", "passed": True, "message": f"감사추적 OK ({len(audit)}건)"}

    def _check_security_level(self, doc: dict[str, Any]) -> dict[str, Any]:
        """보안 등급 적합성 검증"""
        level = doc.get("security_level", "")
        has_pii = len(doc.get("pii_detections", [])) > 0

        if level == "public" and has_pii:
            return {"check": "security", "passed": False, "severity": "critical",
                    "message": "PII 포함 문서가 '공개' 등급으로 설정됨"}
        if not level:
            return {"check": "security", "passed": False, "severity": "warning",
                    "message": "보안 등급 미설정"}
        return {"check": "security", "passed": True, "message": f"보안 등급 OK ({level})"}
