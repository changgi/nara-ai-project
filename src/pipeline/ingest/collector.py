"""
기록물 수집 모듈

RAMP 플랫폼(48개 중앙부처) 및 파일시스템에서 기록물을 수집한다.
11단계 파이프라인의 1단계(ingest).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger("nara-ai.pipeline.ingest")

KST = timezone(timedelta(hours=9))


@dataclass
class IngestSource:
    """수집 소스 정의"""
    name: str
    source_type: str       # "ramp", "filesystem", "api"
    endpoint: str          # URL 또는 디렉토리 경로
    agency: str = ""       # 생산기관
    enabled: bool = True


@dataclass
class IngestResult:
    """수집 결과"""
    source: str
    total_records: int
    successful: int
    failed: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)


# 기본 수집 소스
DEFAULT_SOURCES = [
    IngestSource("RAMP 전자기록물", "ramp", "http://localhost:3005", "행정안전부"),
    IngestSource("디지털화 기록물", "filesystem", "data/raw/non-electronic/", "국가기록원"),
    IngestSource("OCR 대상", "filesystem", "data/raw/ocr-gt/", "국가기록원"),
]


class RecordCollector:
    """기록물 수집기"""

    def __init__(self, sources: list[IngestSource] | None = None):
        self.sources = sources or DEFAULT_SOURCES
        self.client = httpx.AsyncClient(timeout=30.0)

    async def collect_from_ramp(
        self,
        source: IngestSource,
        since: str | None = None,
        limit: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        """RAMP 플랫폼에서 메타데이터 수집"""
        try:
            response = await self.client.post(
                f"{source.endpoint}/tools/ingest_metadata",
                json={"since": since, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()

            for record in data.get("records", []):
                yield {
                    "id": record.get("id", ""),
                    "title": record.get("title", ""),
                    "content": record.get("content", ""),
                    "agency": record.get("agency", source.agency),
                    "record_type": "electronic",
                    "date_created": record.get("date_created"),
                    "source": source.name,
                    "ingested_at": datetime.now(KST).isoformat(),
                }
        except Exception as e:
            logger.error(f"RAMP 수집 실패 ({source.name}): {e}")

    async def collect_from_filesystem(
        self,
        source: IngestSource,
        extensions: tuple[str, ...] = (".pdf", ".tif", ".tiff", ".jpg", ".png"),
    ) -> AsyncIterator[dict[str, Any]]:
        """파일시스템에서 기록물 파일 수집"""
        base_path = Path(source.endpoint)
        if not base_path.exists():
            logger.warning(f"경로 없음: {base_path}")
            return

        for ext in extensions:
            for filepath in sorted(base_path.rglob(f"*{ext}")):
                yield {
                    "id": filepath.stem,
                    "title": filepath.stem.replace("_", " "),
                    "content": "",
                    "file_path": str(filepath),
                    "agency": source.agency,
                    "record_type": self._detect_record_type(filepath),
                    "source": source.name,
                    "ingested_at": datetime.now(KST).isoformat(),
                }

    def _detect_record_type(self, path: Path) -> str:
        """파일 확장자로 기록물 유형 추정"""
        ext = path.suffix.lower()
        type_map = {
            ".pdf": "electronic",
            ".tif": "paper",
            ".tiff": "paper",
            ".jpg": "photo",
            ".png": "photo",
            ".mp3": "audio_video",
            ".mp4": "audio_video",
            ".dwg": "architectural",
        }
        return type_map.get(ext, "electronic")

    async def collect_all(self, since: str | None = None) -> IngestResult:
        """모든 소스에서 기록물 수집"""
        import time
        start = time.monotonic()
        total = 0
        successful = 0
        failed = 0
        errors: list[str] = []

        for source in self.sources:
            if not source.enabled:
                continue

            logger.info(f"수집 시작: {source.name} ({source.source_type})")

            try:
                if source.source_type == "ramp":
                    async for record in self.collect_from_ramp(source, since):
                        total += 1
                        successful += 1
                elif source.source_type == "filesystem":
                    async for record in self.collect_from_filesystem(source):
                        total += 1
                        successful += 1
            except Exception as e:
                failed += 1
                errors.append(f"{source.name}: {str(e)}")
                logger.error(f"수집 실패: {source.name} - {e}")

        duration = time.monotonic() - start

        logger.info(f"수집 완료: {successful}/{total}건 성공 ({duration:.1f}초)")
        return IngestResult(
            source="all",
            total_records=total,
            successful=successful,
            failed=failed,
            duration_seconds=duration,
            errors=errors,
        )

    async def close(self) -> None:
        await self.client.aclose()
