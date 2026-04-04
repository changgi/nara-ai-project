"""
NARA-AI 메인 엔트리포인트

전체 시스템을 초기화하고 11단계 파이프라인을 실행한다.
CLI에서 직접 실행하거나, 모듈로 임포트하여 사용한다.

사용법:
  python -m src.main --mode serve      # 추론 서비스 시작
  python -m src.main --mode pipeline   # 파이프라인 실행
  python -m src.main --mode benchmark  # 벤치마크 실행
  python -m src.main --mode status     # 시스템 현황
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nara-ai")

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent


def print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════════╗
║   NARA-AI v1.0                                               ║
║   AI 기반 국가기록물 지능형 검색·분류·활용 체계                    ║
║   행정안전부 / 국가기록원                                        ║
║                                                              ║
║   "국민을 위한, 국민에 의한, 국민에게 혜택이 돌아가는"              ║
╚══════════════════════════════════════════════════════════════╝
    """)


async def run_status() -> None:
    """시스템 현황 출력"""
    from src.pipeline.pipeline_executor import PipelineExecutor
    from src.pipeline.serve.vllm_config import SERVICE_PORTS

    executor = PipelineExecutor()
    status = executor.get_pipeline_status()

    print(f"\n=== NARA-AI 시스템 현황 ({datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}) ===\n")
    print(f"파이프라인: {status['total_stages']}단계")
    print(f"등록 핸들러: {len(status['registered_handlers'])}개")
    print(f"HITL 대기: {status['hitl_pending']}건")

    print("\n서비스 포트:")
    for name, port in SERVICE_PORTS.items():
        print(f"  {name:20s} : {port}")

    # MCP 서버 도구 수
    print("\nMCP 서버 도구:")
    mcp_tools = {"archive": 10, "iarna": 12, "nara": 12, "law": 6, "ramp": 7}
    for name, count in mcp_tools.items():
        print(f"  mcp-{name:10s} : {count}개")
    print(f"  {'합계':14s} : {sum(mcp_tools.values())}개")


async def run_benchmark() -> None:
    """벤치마크 실행"""
    from src.pipeline.eval.benchmark import run_benchmark as _run

    test_dir = PROJECT_ROOT / "data" / "test"
    if not test_dir.exists() or not any(test_dir.iterdir()):
        print("테스트 데이터 없음. data/test/ 디렉토리에 데이터를 준비하세요.")
        return

    report = _run(
        test_data_dir=str(test_dir),
        output_path=str(PROJECT_ROOT / "_workspace" / "benchmark_report.json"),
    )

    print(f"\n=== 벤치마크 결과 ===\n")
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.task}: {r.metric}={r.value:.4f} (목표: {r.target}, 샘플: {r.samples})")
    print(f"\n전체 통과: {report.all_passed}")
    print(f"소요 시간: {report.total_duration_seconds:.2f}초")


async def run_pipeline_demo() -> None:
    """파이프라인 데모 실행 (샘플 문서)"""
    from src.pipeline.pipeline_executor import (
        PipelineExecutor, PipelineStage, RecordDocument, RecordType, SecurityLevel,
    )

    print("\n=== 파이프라인 데모 (샘플 문서) ===\n")

    doc = RecordDocument(
        title="2024년 정부혁신 추진계획",
        content="행정안전부는 2024년도 정부혁신 추진계획을 수립하였다. "
                "본 계획은 디지털 정부혁신, 국민참여, 정부내부 혁신 3대 전략으로 구성된다.",
        record_type=RecordType.ELECTRONIC,
        security_level=SecurityLevel.PUBLIC,
        agency="행정안전부",
    )

    executor = PipelineExecutor(
        workspace_dir=PROJECT_ROOT / "_workspace",
        checkpoint_dir=PROJECT_ROOT / "checkpoints",
    )

    print(f"문서: {doc.title}")
    print(f"기관: {doc.agency}")
    print(f"유형: {doc.record_type.value}")
    print(f"보안: {doc.security_level.value}")
    print(f"해시: {doc.input_hash}")

    # 파이프라인 상태 출력
    status = executor.get_pipeline_status()
    print(f"\n파이프라인: {status['total_stages']}단계")
    print(f"핸들러 등록 필요: 추론 서버 실행 후 핸들러를 등록하세요")

    # 감사추적 저장 데모
    from src.pipeline.pipeline_executor import AuditEntry
    doc.audit_trail.append(AuditEntry(
        user_id="demo",
        agent_name="nara-ai-demo",
        stage="demo",
        action="pipeline_demo",
        input_hash=doc.input_hash,
        output_summary="데모 실행 완료",
        confidence=1.0,
        reasoning="초기 환경 검증용 데모 실행",
    ))

    filepath = executor.save_audit_trail(doc)
    print(f"\n감사추적 저장: {filepath}")


async def run_pii_demo() -> None:
    """PII 탐지 데모"""
    from src.agents.redaction.agent import RedactionAgent

    print("\n=== PII 탐지 데모 ===\n")

    agent = RedactionAgent()
    test_texts = [
        "신청인 홍길동(주민번호: 850101-1234567)은 서울시 강남구에 거주합니다.",
        "연락처: 010-9876-5432, 이메일: hong@example.com",
        "여권번호 M12345678, 운전면허 11-123456-78",
        "기록물 관리에 관한 법률을 준수합니다. (PII 없음)",
    ]

    for text in test_texts:
        detections = agent.detect_pii(text)
        masked = agent.mask_content(text, detections)
        print(f"원본: {text}")
        if detections:
            for d in detections:
                print(f"  탐지: {d.pii_name} ({d.severity}) → {d.masked_text}")
            print(f"마스킹: {masked}")
        else:
            print("  PII 없음")
        print()


async def run_ocr_postprocess_demo() -> None:
    """OCR 후처리 데모"""
    from src.ocr.postprocess.corrector import OCRPostProcessor

    print("\n=== OCR 후처리 데모 ===\n")

    processor = OCRPostProcessor()
    test_texts = [
        "행정안전뷰에서 발행한 공공기록뭄 관리 지침",
        "國家記錄院은 大韓民國의 기록물을 관리하는 機關이다.",
        "2024. 3. 15 작성된 보존기갼 10년 문서",
    ]

    for text in test_texts:
        result = processor.correct(text)
        print(f"원본:   {text}")
        print(f"교정:   {result.corrected}")
        print(f"신뢰도: {result.confidence:.2f}, 교정 {len(result.corrections)}건")
        for c in result.corrections:
            print(f"  [{c['type']}] {c['from']} → {c['to']}")
        print()

    # 기관명 추출
    test_text = "행정안전부와 국가기록원이 공동으로 작성하고 교육부가 검토한 문서"
    agencies = processor.extract_agencies(test_text)
    print(f"기관명 추출: {test_text}")
    print(f"  결과: {agencies}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NARA-AI: AI 기반 국가기록물 지능형 검색·분류·활용 체계",
    )
    parser.add_argument(
        "--mode",
        choices=["status", "benchmark", "pipeline", "pii-demo", "ocr-demo", "all-demo"],
        default="status",
        help="실행 모드",
    )
    args = parser.parse_args()

    print_banner()

    if args.mode == "status":
        asyncio.run(run_status())
    elif args.mode == "benchmark":
        asyncio.run(run_benchmark())
    elif args.mode == "pipeline":
        asyncio.run(run_pipeline_demo())
    elif args.mode == "pii-demo":
        asyncio.run(run_pii_demo())
    elif args.mode == "ocr-demo":
        asyncio.run(run_ocr_postprocess_demo())
    elif args.mode == "all-demo":
        asyncio.run(run_status())
        asyncio.run(run_pii_demo())
        asyncio.run(run_ocr_postprocess_demo())
        asyncio.run(run_pipeline_demo())
        asyncio.run(run_benchmark())


if __name__ == "__main__":
    main()
