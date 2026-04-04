"""
NARA-AI 11단계 처리 파이프라인 실행기

기록물을 수집부터 보안 스캐닝까지 11단계로 처리한다.
각 단계는 독립적으로 실행 가능하며, LangGraph 오케스트레이터가 조율한다.
HITL(Human-in-the-Loop) 게이트로 비밀해제/보존기간/분류 변경 시 인간 개입을 보장한다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("nara-ai.pipeline")

# 한국 표준시 (KST = UTC+9)
KST = timezone(timedelta(hours=9))


class PipelineStage(str, Enum):
    """11단계 파이프라인 단계 정의"""
    INGEST = "ingest"
    LAYOUT = "layout"
    OCR = "ocr"
    OCR_POST = "ocr_post"
    CLASSIFY = "classify"
    METADATA = "metadata"
    REDACTION = "redaction"
    EMBEDDING = "embedding"
    GRAPH = "graph"
    QUALITY = "quality"
    SECURITY = "security"

    @property
    def order(self) -> int:
        return list(PipelineStage).index(self)


class SecurityLevel(str, Enum):
    """기록물 보안 등급 (공공기록물법 기반)"""
    PUBLIC = "public"           # 공개
    RESTRICTED = "restricted"   # 부분공개
    SECRET = "secret"           # 비공개
    TOP_SECRET = "top_secret"   # 비밀


class RecordType(str, Enum):
    """기록물 유형"""
    ELECTRONIC = "electronic"       # 전자기록물
    PAPER = "paper"                # 종이기록물
    PHOTO = "photo"                # 사진
    MICROFILM = "microfilm"        # 마이크로필름
    AUDIO_VIDEO = "audio_video"    # 시청각기록물
    ARCHITECTURAL = "architectural" # 건축도면
    MAP = "map"                    # 지도


@dataclass
class AuditEntry:
    """감사추적 엔트리 (AI 기본법 투명성 요구사항)"""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(KST).isoformat())
    user_id: str = ""
    agent_name: str = ""
    stage: str = ""
    action: str = ""
    input_hash: str = ""
    output_summary: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    hitl_required: bool = False
    hitl_decision: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class RecordDocument:
    """기록물 문서 데이터 모델"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    record_type: RecordType = RecordType.ELECTRONIC
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    record_group: str = ""              # RG 번호
    agency: str = ""                    # 생산기관
    date_created: Optional[str] = None  # 생산일 (ISO 8601)
    date_received: Optional[str] = None # 접수일
    retention_period: int = 0           # 보존기간 (년)
    brm_code: str = ""                 # BRM 업무기능 코드
    keywords: list[str] = field(default_factory=list)
    summary: str = ""
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    embedding_vector: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    pii_detected: list[dict[str, str]] = field(default_factory=list)
    audit_trail: list[AuditEntry] = field(default_factory=list)

    @property
    def input_hash(self) -> str:
        """입력 데이터의 SHA-256 해시 (감사추적용)"""
        content = f"{self.title}:{self.content}:{self.ocr_text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


@dataclass
class PipelineResult:
    """파이프라인 단계 실행 결과"""
    stage: PipelineStage
    success: bool
    document: RecordDocument
    audit_entry: AuditEntry
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_stage: Optional[PipelineStage] = None
    hitl_pending: bool = False


class HITLGate:
    """HITL(Human-in-the-Loop) 게이트

    공공기록물법 및 AI 기본법에 따라 다음 결정에는 인간 개입이 필수:
    - 비밀해제 심사 (제34조)
    - 보존기간 변경 (제38조)
    - 분류 이의 (제33조)
    """

    REQUIRED_ACTIONS = {
        "redaction_decision": "비밀해제 여부 결정 (공공기록물법 제34조)",
        "retention_override": "보존기간 변경 (공공기록물법 제38조)",
        "classification_dispute": "분류 이의 처리 (공공기록물법 제33조)",
        "disposal_approval": "기록물 폐기 승인 (2인 이상, 제38조)",
    }

    def __init__(self, action: str):
        if action not in self.REQUIRED_ACTIONS:
            raise ValueError(f"알 수 없는 HITL 액션: {action}")
        self.action = action
        self.description = self.REQUIRED_ACTIONS[action]
        self.pending_decisions: list[dict[str, Any]] = []

    def request_decision(
        self,
        document: RecordDocument,
        ai_recommendation: str,
        confidence: float,
        reasoning: str,
    ) -> dict[str, Any]:
        """인간 결정을 요청한다. 큐에 추가하고 대기."""
        decision_request = {
            "request_id": str(uuid.uuid4()),
            "action": self.action,
            "description": self.description,
            "document_id": document.id,
            "document_title": document.title,
            "ai_recommendation": ai_recommendation,
            "confidence": confidence,
            "reasoning": reasoning,
            "requested_at": datetime.now(KST).isoformat(),
            "status": "pending",
            "human_decision": None,
            "human_comment": None,
        }
        self.pending_decisions.append(decision_request)
        logger.info(
            f"HITL 결정 요청: {self.action} - 문서 '{document.title}' "
            f"(AI 추천: {ai_recommendation}, 신뢰도: {confidence:.2f})"
        )
        return decision_request


class PipelineExecutor:
    """11단계 처리 파이프라인 실행기"""

    def __init__(
        self,
        workspace_dir: str | Path = "_workspace",
        checkpoint_dir: str | Path = "checkpoints",
    ):
        self.workspace_dir = Path(workspace_dir)
        self.checkpoint_dir = Path(checkpoint_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # HITL 게이트 초기화
        self.hitl_gates = {
            action: HITLGate(action)
            for action in HITLGate.REQUIRED_ACTIONS
        }

        # 단계별 처리 함수 매핑
        self._stage_handlers: dict[PipelineStage, Any] = {}

    def register_handler(self, stage: PipelineStage, handler: Any) -> None:
        """단계별 처리 함수 등록"""
        self._stage_handlers[stage] = handler
        logger.info(f"파이프라인 단계 등록: {stage.value}")

    async def process_document(
        self,
        document: RecordDocument,
        start_stage: PipelineStage = PipelineStage.INGEST,
        end_stage: PipelineStage = PipelineStage.SECURITY,
        user_id: str = "system",
    ) -> list[PipelineResult]:
        """문서를 지정된 단계 범위에서 처리한다."""
        results: list[PipelineResult] = []
        current_doc = document

        for stage in PipelineStage:
            if stage.order < start_stage.order:
                continue
            if stage.order > end_stage.order:
                break

            logger.info(f"[{stage.order + 1}/11] {stage.value} 단계 시작: '{current_doc.title}'")
            start_time = time.monotonic()

            try:
                handler = self._stage_handlers.get(stage)
                if handler is None:
                    logger.warning(f"핸들러 미등록: {stage.value}, 건너뜀")
                    continue

                result = await handler(current_doc)
                duration_ms = (time.monotonic() - start_time) * 1000

                # 감사추적 엔트리 생성
                audit = AuditEntry(
                    user_id=user_id,
                    agent_name=f"nara-ai-{stage.value}",
                    stage=stage.value,
                    action=f"process_{stage.value}",
                    input_hash=current_doc.input_hash,
                    output_summary=f"{stage.value} 완료",
                    confidence=getattr(result, "confidence", 0.0),
                    reasoning=getattr(result, "reasoning", ""),
                    hitl_required=getattr(result, "hitl_pending", False),
                    duration_ms=duration_ms,
                )

                current_doc.audit_trail.append(audit)
                pipeline_result = PipelineResult(
                    stage=stage,
                    success=True,
                    document=current_doc,
                    audit_entry=audit,
                    hitl_pending=getattr(result, "hitl_pending", False),
                )
                results.append(pipeline_result)

                # HITL 게이트에서 대기 중이면 중단
                if pipeline_result.hitl_pending:
                    logger.info(f"HITL 대기: {stage.value} - 인간 결정 필요")
                    break

                logger.info(
                    f"[{stage.order + 1}/11] {stage.value} 완료 "
                    f"({duration_ms:.0f}ms)"
                )

            except Exception as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(f"파이프라인 에러: {stage.value} - {e}")

                audit = AuditEntry(
                    user_id=user_id,
                    agent_name=f"nara-ai-{stage.value}",
                    stage=stage.value,
                    action=f"error_{stage.value}",
                    input_hash=current_doc.input_hash,
                    output_summary=f"에러: {str(e)[:200]}",
                    duration_ms=duration_ms,
                )
                current_doc.audit_trail.append(audit)

                results.append(PipelineResult(
                    stage=stage,
                    success=False,
                    document=current_doc,
                    audit_entry=audit,
                    errors=[str(e)],
                ))
                # 에러 발생 시 다음 단계로 진행하지 않음
                break

        return results

    def save_audit_trail(self, document: RecordDocument) -> Path:
        """감사추적 로그를 파일로 저장 (10년 보존)"""
        audit_dir = self.workspace_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        filepath = audit_dir / f"{document.id}_audit.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                [asdict(entry) for entry in document.audit_trail],
                f, ensure_ascii=False, indent=2,
            )
        return filepath

    def get_pipeline_status(self) -> dict[str, Any]:
        """파이프라인 현황 반환"""
        return {
            "version": "1.0.0",
            "stages": [s.value for s in PipelineStage],
            "total_stages": len(PipelineStage),
            "registered_handlers": list(self._stage_handlers.keys()),
            "hitl_pending": sum(
                len(gate.pending_decisions)
                for gate in self.hitl_gates.values()
            ),
        }
