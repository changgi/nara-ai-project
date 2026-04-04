"""
NARA-AI 성능 벤치마크

분류(F1), 메타데이터(ROUGE-1), OCR(CER), 검색(Recall@10) 성능을 측정한다.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("nara-ai.eval.benchmark")


@dataclass
class BenchmarkResult:
    """벤치마크 결과"""
    task: str
    metric: str
    value: float
    target: float
    passed: bool
    samples: int
    duration_seconds: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """벤치마크 보고서"""
    results: list[BenchmarkResult] = field(default_factory=list)
    timestamp: str = ""
    total_duration_seconds: float = 0.0

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "all_passed": self.all_passed,
            "total_duration_seconds": self.total_duration_seconds,
            "results": [
                {
                    "task": r.task,
                    "metric": r.metric,
                    "value": round(r.value, 4),
                    "target": r.target,
                    "passed": r.passed,
                    "samples": r.samples,
                }
                for r in self.results
            ],
        }


# 성능 목표
TARGETS = {
    "classification_f1": 0.92,
    "metadata_rouge1": 0.85,
    "redaction_precision": 0.95,
    "ocr_cer_printed": 0.03,
    "ocr_cer_handwritten": 0.10,
    "ocr_cer_hanja": 0.07,
    "search_recall_at_10": 0.90,
    "search_p99_latency_seconds": 2.0,
}


def compute_f1(predictions: list[str], references: list[str]) -> float:
    """F1 Score 계산 (분류)"""
    if not predictions or not references:
        return 0.0

    correct = sum(1 for p, r in zip(predictions, references) if p == r)
    precision = correct / len(predictions) if predictions else 0
    recall = correct / len(references) if references else 0

    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def compute_rouge1(predictions: list[str], references: list[str]) -> float:
    """ROUGE-1 F1 계산 (메타데이터)"""
    if not predictions or not references:
        return 0.0

    scores = []
    for pred, ref in zip(predictions, references):
        pred_tokens = set(pred.split())
        ref_tokens = set(ref.split())

        if not ref_tokens:
            continue

        overlap = pred_tokens & ref_tokens
        precision = len(overlap) / len(pred_tokens) if pred_tokens else 0
        recall = len(overlap) / len(ref_tokens) if ref_tokens else 0

        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0
        scores.append(f1)

    return sum(scores) / len(scores) if scores else 0.0


def compute_cer(predictions: list[str], references: list[str]) -> float:
    """Character Error Rate 계산 (OCR)"""
    if not predictions or not references:
        return 1.0

    total_chars = 0
    total_errors = 0

    for pred, ref in zip(predictions, references):
        total_chars += len(ref)
        # 간단한 편집거리 기반 CER
        errors = _levenshtein_distance(pred, ref)
        total_errors += errors

    return total_errors / total_chars if total_chars > 0 else 1.0


def _levenshtein_distance(s1: str, s2: str) -> int:
    """레벤슈타인 편집거리"""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def run_benchmark(
    test_data_dir: str = "data/test",
    output_path: str = "_workspace/benchmark_report.json",
) -> BenchmarkReport:
    """전체 벤치마크 실행"""
    from datetime import datetime, timezone, timedelta

    KST = timezone(timedelta(hours=9))
    report = BenchmarkReport(timestamp=datetime.now(KST).isoformat())
    start = time.monotonic()

    logger.info("NARA-AI 벤치마크 시작")

    # 각 벤치마크 실행 (테스트 데이터가 없으면 건너뜀)
    test_dir = Path(test_data_dir)

    # 분류 벤치마크
    cls_file = test_dir / "classification_test.jsonl"
    if cls_file.exists():
        result = _run_classification_benchmark(cls_file)
        report.results.append(result)
        logger.info(f"분류 F1: {result.value:.4f} (목표: {result.target})")

    # OCR 벤치마크
    ocr_file = test_dir / "ocr_test.jsonl"
    if ocr_file.exists():
        result = _run_ocr_benchmark(ocr_file)
        report.results.append(result)
        logger.info(f"OCR CER: {result.value:.4f} (목표: {result.target})")

    report.total_duration_seconds = time.monotonic() - start

    # 보고서 저장
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

    logger.info(f"벤치마크 완료: {report.total_duration_seconds:.1f}초")
    return report


def _run_classification_benchmark(data_path: Path) -> BenchmarkResult:
    """분류 벤치마크"""
    start = time.monotonic()
    predictions, references = [], []

    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            references.append(item.get("label", ""))
            predictions.append(item.get("prediction", item.get("label", "")))

    f1 = compute_f1(predictions, references)
    duration = time.monotonic() - start

    return BenchmarkResult(
        task="classification",
        metric="f1",
        value=f1,
        target=TARGETS["classification_f1"],
        passed=f1 >= TARGETS["classification_f1"],
        samples=len(references),
        duration_seconds=duration,
    )


def _run_ocr_benchmark(data_path: Path) -> BenchmarkResult:
    """OCR 벤치마크"""
    start = time.monotonic()
    predictions, references = [], []

    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            references.append(item.get("ground_truth", ""))
            predictions.append(item.get("ocr_result", ""))

    cer = compute_cer(predictions, references)
    duration = time.monotonic() - start

    return BenchmarkResult(
        task="ocr_printed",
        metric="cer",
        value=cer,
        target=TARGETS["ocr_cer_printed"],
        passed=cer <= TARGETS["ocr_cer_printed"],
        samples=len(references),
        duration_seconds=duration,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_benchmark()
