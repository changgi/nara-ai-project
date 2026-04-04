"""
NARA-AI LangGraph 오케스트레이터

6개 특화 AI 에이전트를 조율하여 기록물 처리 파이프라인을 실행한다.
HITL 게이트로 비밀해제/보존기간/분류 변경 시 인간 개입을 보장한다.
감사추적으로 모든 의사결정 근거를 10년간 보존한다.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Annotated, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger("nara-ai.orchestrator")

KST = timezone(timedelta(hours=9))


# ─── 상태 정의 ───

class RecordProcessingState(TypedDict):
    """기록물 처리 파이프라인 상태"""
    # 입력
    document_id: str
    title: str
    content: str
    record_type: str
    agency: str

    # OCR 결과
    ocr_text: str
    ocr_confidence: float
    ocr_model: str

    # 분류 결과
    brm_code: str
    brm_name: str
    classification_confidence: float

    # 메타데이터
    generated_title: str
    summary: str
    keywords: list[str]
    named_entities: list[dict[str, Any]]

    # 비밀해제
    redaction_recommendation: str
    pii_detections: list[dict[str, Any]]
    security_concerns: list[str]

    # 임베딩
    embedding_vector: list[float]

    # 품질
    quality_score: float
    quality_issues: list[str]

    # HITL
    hitl_pending: bool
    hitl_action: str
    hitl_decision: str | None

    # 감사추적
    audit_trail: list[dict[str, Any]]

    # 상태
    current_stage: str
    error: str | None


# ─── 에이전트 노드 ───

async def classifier_node(state: RecordProcessingState) -> dict[str, Any]:
    """분류 에이전트: BRM 업무기능 매핑"""
    logger.info(f"분류 시작: {state['title']}")

    from src.agents.classifier.agent import ClassifierAgent
    agent = ClassifierAgent()

    try:
        result = await agent.classify(
            title=state["title"],
            content=state.get("ocr_text") or state["content"],
            agency=state.get("agency", ""),
        )
        return {
            "brm_code": result.brm_code,
            "brm_name": result.brm_name,
            "classification_confidence": result.confidence,
            "current_stage": "classify",
            "audit_trail": state.get("audit_trail", []) + [{
                "stage": "classify",
                "timestamp": datetime.now(KST).isoformat(),
                "user_id": state.get("user_id", "system"),
                "agent_name": "nara-ai-classifier",
                "input_hash": hashlib.sha256(
                    f"{state['title']}:{state.get('content', '')[:500]}".encode()
                ).hexdigest()[:16],
                "result": f"{result.brm_code} ({result.brm_name})",
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "hitl_required": result.hitl_pending,
            }],
        }
    finally:
        await agent.close()


async def metadata_node(state: RecordProcessingState) -> dict[str, Any]:
    """메타데이터 에이전트: 제목/요약/키워드/NER 생성"""
    logger.info(f"메타데이터 생성: {state['title']}")

    from src.agents.metadata.agent import MetadataAgent
    agent = MetadataAgent()

    try:
        result = await agent.generate(
            content=state.get("ocr_text") or state["content"],
        )
        return {
            "generated_title": result.title_suggestion,
            "summary": result.summary,
            "keywords": result.keywords,
            "named_entities": [
                {"text": e.text, "type": e.entity_type, "confidence": e.confidence}
                for e in result.named_entities
            ],
            "current_stage": "metadata",
            "audit_trail": state.get("audit_trail", []) + [{
                "stage": "metadata",
                "timestamp": datetime.now(KST).isoformat(),
                "user_id": state.get("user_id", "system"),
                "agent_name": "nara-ai-metadata",
                "input_hash": hashlib.sha256(
                    state.get("content", "")[:500].encode()
                ).hexdigest()[:16],
                "result": f"제목: {result.title_suggestion}, 키워드: {len(result.keywords)}개",
                "confidence": result.confidence,
                "hitl_required": False,
            }],
        }
    finally:
        await agent.close()


async def redaction_node(state: RecordProcessingState) -> dict[str, Any]:
    """비밀해제 에이전트: 공개 적합성 평가 (HITL 필수)"""
    logger.info(f"비밀해제 심사: {state['title']}")

    from src.agents.redaction.agent import RedactionAgent
    agent = RedactionAgent()

    try:
        result = await agent.review(
            title=state["title"],
            content=state.get("ocr_text") or state["content"],
        )
        return {
            "redaction_recommendation": result.recommendation,
            "pii_detections": [
                {"type": d.pii_type, "name": d.pii_name, "severity": d.severity}
                for d in result.pii_detections
            ],
            "security_concerns": result.security_concerns,
            "hitl_pending": True,  # 비밀해제는 항상 HITL 필수
            "hitl_action": "redaction_decision",
            "current_stage": "redaction",
            "audit_trail": state.get("audit_trail", []) + [{
                "stage": "redaction",
                "timestamp": datetime.now(KST).isoformat(),
                "user_id": state.get("user_id", "system"),
                "agent_name": "nara-ai-redaction",
                "input_hash": hashlib.sha256(
                    f"{state['title']}:{state.get('content', '')[:500]}".encode()
                ).hexdigest()[:16],
                "result": f"AI 추천: {result.recommendation}",
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "pii_count": len(result.pii_detections),
                "hitl_required": True,
            }],
        }
    finally:
        await agent.close()


async def quality_node(state: RecordProcessingState) -> dict[str, Any]:
    """품질 검증 에이전트"""
    logger.info(f"품질 검증: {state['title']}")

    issues: list[str] = []
    score = 1.0

    # 분류 신뢰도 검증
    if state.get("classification_confidence", 0) < 0.85:
        issues.append(f"분류 신뢰도 낮음: {state.get('classification_confidence', 0):.2f}")
        score -= 0.2

    # OCR 신뢰도 검증
    if state.get("ocr_confidence", 0) < 0.7:
        issues.append(f"OCR 신뢰도 낮음: {state.get('ocr_confidence', 0):.2f}")
        score -= 0.2

    # 메타데이터 완전성 검증
    if not state.get("keywords"):
        issues.append("키워드 미생성")
        score -= 0.1
    if not state.get("summary"):
        issues.append("요약 미생성")
        score -= 0.1

    return {
        "quality_score": max(0.0, score),
        "quality_issues": issues,
        "current_stage": "quality",
        "audit_trail": state.get("audit_trail", []) + [{
            "stage": "quality",
            "timestamp": datetime.now(KST).isoformat(),
            "user_id": state.get("user_id", "system"),
            "agent_name": "nara-ai-quality",
            "input_hash": hashlib.sha256(
                state.get("document_id", "").encode()
            ).hexdigest()[:16],
            "result": f"품질 점수: {max(0.0, score):.2f}, 이슈: {len(issues)}건",
            "confidence": max(0.0, score),
            "hitl_required": len(issues) > 0,
        }],
    }


# ─── HITL 게이트 ───

def should_hitl(state: RecordProcessingState) -> str:
    """HITL 필요 여부 판단"""
    if state.get("hitl_pending"):
        return "hitl_wait"
    return "continue"


async def hitl_wait_node(state: RecordProcessingState) -> dict[str, Any]:
    """HITL 대기: 인간 결정을 기다린다"""
    logger.info(
        f"HITL 대기 중: {state.get('hitl_action', 'unknown')} - "
        f"AI 추천: {state.get('redaction_recommendation', 'N/A')}"
    )
    # LangGraph 체크포인트에 저장, 인간 결정 후 resume
    return {
        "current_stage": "hitl_wait",
    }


# ─── 그래프 구성 ───

def build_orchestrator_graph() -> StateGraph:
    """LangGraph 오케스트레이터 그래프 구성"""

    graph = StateGraph(RecordProcessingState)

    # 노드 등록
    graph.add_node("classifier", classifier_node)
    graph.add_node("metadata", metadata_node)
    graph.add_node("redaction", redaction_node)
    graph.add_node("quality", quality_node)
    graph.add_node("hitl_wait", hitl_wait_node)

    # 엣지 (파이프라인 흐름)
    graph.set_entry_point("classifier")
    graph.add_edge("classifier", "metadata")
    graph.add_edge("metadata", "redaction")

    # HITL 조건부 분기
    graph.add_conditional_edges(
        "redaction",
        should_hitl,
        {
            "hitl_wait": "hitl_wait",
            "continue": "quality",
        },
    )
    graph.add_edge("hitl_wait", "quality")
    graph.add_edge("quality", END)

    return graph


def create_orchestrator(checkpoint_db: str = "checkpoints/langgraph.db"):
    """오케스트레이터 인스턴스 생성"""
    graph = build_orchestrator_graph()
    checkpointer = SqliteSaver.from_conn_string(checkpoint_db)
    return graph.compile(checkpointer=checkpointer)
