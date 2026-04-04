"""
NARA-AI SFT 학습 데이터 준비 스크립트

원시 기록물 데이터를 SFT 학습용 JSONL 형식으로 변환한다.
3가지 과업: 분류, 메타데이터, 비밀해제

출력 형식 (JSONL):
{"instruction": "...", "input": "...", "output": "..."}
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("nara-ai.data.prepare")


def prepare_classification_data(
    input_dir: str,
    output_path: str,
    max_samples: int = 50000,
) -> int:
    """분류 학습 데이터 생성

    입력: 기록물 메타데이터 (제목, 본문, 기관, BRM 코드)
    출력: instruction-input-output JSONL
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output, "w", encoding="utf-8") as f:
        for source_file in sorted(Path(input_dir).glob("*.json*")):
            with open(source_file, "r", encoding="utf-8") as sf:
                for line in sf:
                    if count >= max_samples:
                        break

                    try:
                        record = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue

                    title = record.get("title", "")
                    content = record.get("content", "")[:2000]
                    agency = record.get("agency", "")
                    brm_code = record.get("brm_code", "")
                    brm_name = record.get("brm_name", "")

                    if not title or not brm_code:
                        continue

                    entry = {
                        "instruction": "다음 기록물을 BRM 업무기능으로 분류하세요. BRM 코드와 이름을 JSON으로 응답하세요.",
                        "input": f"제목: {title}\n생산기관: {agency}\n본문: {content}",
                        "output": json.dumps({
                            "brm_code": brm_code,
                            "brm_name": brm_name,
                            "confidence": 1.0,
                            "reasoning": f"'{title}'은(는) {brm_name} 업무에 해당합니다.",
                        }, ensure_ascii=False),
                    }

                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1

    logger.info(f"분류 데이터 생성: {count}건 → {output}")
    return count


def prepare_metadata_data(
    input_dir: str,
    output_path: str,
    max_samples: int = 30000,
) -> int:
    """메타데이터 학습 데이터 생성"""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output, "w", encoding="utf-8") as f:
        for source_file in sorted(Path(input_dir).glob("*.json*")):
            with open(source_file, "r", encoding="utf-8") as sf:
                for line in sf:
                    if count >= max_samples:
                        break

                    try:
                        record = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue

                    content = record.get("content", "")
                    if not content or len(content) < 100:
                        continue

                    entry = {
                        "instruction": "다음 기록물에서 메타데이터(제목, 요약, 키워드, 개체명)를 추출하세요. JSON으로 응답하세요.",
                        "input": content[:3000],
                        "output": json.dumps({
                            "title_suggestion": record.get("title", ""),
                            "summary": record.get("summary", "")[:200],
                            "keywords": record.get("keywords", [])[:10],
                            "named_entities": record.get("entities", []),
                            "confidence": 1.0,
                        }, ensure_ascii=False),
                    }

                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1

    logger.info(f"메타데이터 데이터 생성: {count}건 → {output}")
    return count


def prepare_redaction_data(
    input_dir: str,
    output_path: str,
    max_samples: int = 20000,
) -> int:
    """비밀해제 학습 데이터 생성"""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output, "w", encoding="utf-8") as f:
        for source_file in sorted(Path(input_dir).glob("*.json*")):
            with open(source_file, "r", encoding="utf-8") as sf:
                for line in sf:
                    if count >= max_samples:
                        break

                    try:
                        record = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue

                    content = record.get("content", "")
                    if not content:
                        continue

                    entry = {
                        "instruction": (
                            "다음 비공개 기록물의 공개 전환 적합성을 검토하세요. "
                            "공공기록물법 제33-35조에 따라 판단하고 JSON으로 응답하세요."
                        ),
                        "input": f"제목: {record.get('title', '')}\n"
                                 f"보안등급: {record.get('security_level', 'secret')}\n"
                                 f"생산 경과: {record.get('years_since', 0)}년\n"
                                 f"본문: {content[:2000]}",
                        "output": json.dumps({
                            "recommendation": record.get("redaction_decision", "비공개 유지"),
                            "confidence": float(record.get("confidence", 0.8)),
                            "reasoning": record.get("reasoning", ""),
                            "security_concerns": record.get("concerns", []),
                            "legal_basis": record.get("legal_basis", "공공기록물법 제34조"),
                        }, ensure_ascii=False),
                    }

                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1

    logger.info(f"비밀해제 데이터 생성: {count}건 → {output}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="NARA-AI SFT 데이터 준비")
    parser.add_argument("--input_dir", default="data/raw/electronic/")
    parser.add_argument("--output_dir", default="data/processed/sft/")
    parser.add_argument("--task", choices=["all", "classification", "metadata", "redaction"], default="all")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.task in ("all", "classification"):
        prepare_classification_data(args.input_dir, str(output_dir / "classification-50k.jsonl"))

    if args.task in ("all", "metadata"):
        prepare_metadata_data(args.input_dir, str(output_dir / "metadata-gen-30k.jsonl"))

    if args.task in ("all", "redaction"):
        prepare_redaction_data(args.input_dir, str(output_dir / "redaction-20k.jsonl"))

    logger.info("데이터 준비 완료")


if __name__ == "__main__":
    main()
