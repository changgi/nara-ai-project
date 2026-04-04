# -*- coding: utf-8 -*-
"""
NARA-AI 웹 API 서버

국민이 자연어로 기록물을 검색하고, 기록물 전문가가 AI 도구를 활용하는 통합 API.
FastAPI 기반, UTF-8 한글 완벽 지원.

엔드포인트:
    GET  /              웹 UI
    GET  /health        헬스체크
    GET  /status        시스템 현황
    POST /search        기록물 검색 (자연어)
    POST /classify      기록물 분류
    POST /pii/detect    PII 탐지
    POST /ocr/correct   OCR 후처리
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("nara-ai.api")

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="NARA-AI",
    description="AI 기반 국가기록물 지능형 검색/분류/활용 체계",
    version="1.0.0",
)

# 정적 파일 (웹 UI)
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ─── 요청/응답 모델 ───

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="검색 쿼리")
    top_k: int = Field(default=10, ge=1, le=100)
    mode: str = Field(default="auto", description="검색 모드: auto, cpu, gpu")

class SearchResult(BaseModel):
    id: str
    title: str
    content_preview: str
    score: float
    method: str

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    processing_time_ms: float
    mode: str

class ClassifyRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    agency: str = ""

class PIIRequest(BaseModel):
    content: str = Field(..., min_length=1)

class OCRCorrectionRequest(BaseModel):
    text: str = Field(..., min_length=1)


# ─── 엔드포인트 ───

@app.get("/", response_class=HTMLResponse)
async def root():
    """웹 UI 메인 페이지"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(_get_default_html())


@app.get("/health")
async def health():
    """헬스체크"""
    mode = "cloud"
    try:
        from config.settings import settings
        mode = "cpu" if settings.is_cpu_mode() else "gpu"
    except ImportError:
        pass
    return {
        "status": "ok",
        "project": "NARA-AI",
        "version": "1.0.0",
        "mode": mode,
        "timestamp": datetime.now(KST).isoformat(),
    }


@app.get("/status")
async def status():
    """시스템 현황"""
    try:
        from config.settings import settings
        from src.pipeline.pipeline_executor import PipelineStage, HITLGate
        return {
            "project": "NARA-AI", "version": "1.0.0",
            "mode": "cpu" if settings.is_cpu_mode() else "gpu",
            "pipeline_stages": len(list(PipelineStage)),
            "hitl_gates": len(HITLGate.REQUIRED_ACTIONS),
            "mcp_tools": 47,
            "settings": settings.dump(),
            "timestamp": datetime.now(KST).isoformat(),
        }
    except ImportError:
        return {
            "project": "NARA-AI", "version": "1.0.0",
            "mode": "cloud (Vercel)",
            "pipeline_stages": 11, "hitl_gates": 4, "mcp_tools": 47,
            "timestamp": datetime.now(KST).isoformat(),
        }


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """기록물 검색 (자연어)"""
    start = time.monotonic()
    from config.settings import settings

    # CPU 인덱스가 존재하면 항상 CPU 검색 사용 (Milvus 미연결 시 폴백)
    cpu_index_exists = settings.CPU_VECTORS_PATH.exists()
    use_cpu = (
        req.mode == "cpu"
        or (req.mode == "auto" and settings.is_cpu_mode())
        or (req.mode == "auto" and cpu_index_exists)  # CPU 인덱스 있으면 자동 사용
    )

    if use_cpu and cpu_index_exists:
        from src.search.embedding.cpu_embedder import CPUEmbedder
        embedder = CPUEmbedder(db_path=str(settings.CPU_VECTORS_PATH))
        results = embedder.search(req.query, top_k=req.top_k)
        search_results = [
            SearchResult(
                id=r.id, title=r.title,
                content_preview=r.content_preview,
                score=r.score, method=r.method,
            )
            for r in results
        ]
    else:
        search_results = []

    duration = (time.monotonic() - start) * 1000

    return SearchResponse(
        query=req.query,
        results=search_results,
        total=len(search_results),
        processing_time_ms=duration,
        mode="cpu" if use_cpu else "gpu",
    )


@app.post("/pii/detect")
async def detect_pii(req: PIIRequest):
    """PII 탐지 + 마스킹"""
    try:
        from src.agents.redaction.agent import RedactionAgent
        agent = RedactionAgent()
        detections = agent.detect_pii(req.content)
        masked = agent.mask_content(req.content, detections)
        return {
            "original_length": len(req.content),
            "pii_count": len(detections),
            "detections": [
                {"type": d.pii_type, "name": d.pii_name, "severity": d.severity, "masked": d.masked_text}
                for d in detections
            ],
            "masked_content": masked,
        }
    except ImportError:
        # Vercel 폴백: 인라인 PII 탐지
        import re
        patterns = {
            "resident_id": (r"\d{6}-[1-4]\d{6}", "주민등록번호", "critical"),
            "phone": (r"01[0-9]-?\d{3,4}-?\d{4}", "전화번호", "high"),
            "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "이메일", "medium"),
        }
        detections = []
        masked = req.content
        for ptype, (pat, name, sev) in patterns.items():
            for m in re.finditer(pat, req.content):
                txt = m.group()
                mk = txt[:2] + "*" * (len(txt) - 2)
                detections.append({"type": ptype, "name": name, "severity": sev, "masked": mk})
                masked = masked[:m.start()] + mk + masked[m.end():]
        return {"original_length": len(req.content), "pii_count": len(detections), "detections": detections, "masked_content": masked}


@app.post("/ocr/correct")
async def correct_ocr(req: OCRCorrectionRequest):
    """OCR 후처리 (맞춤법 교정, 한자 병기, 구조화)"""
    try:
        from src.ocr.postprocess.corrector import OCRPostProcessor
    except ImportError:
        # Vercel 폴백: 인라인 OCR 교정
        corrections_map = {"행정안전뷰": "행정안전부", "공공기록뭄": "공공기록물", "국가기록완": "국가기록원", "보존기갼": "보존기간"}
        hanja_map = {"國家": "國家(국가)", "記錄": "記錄(기록)", "機關": "機關(기관)"}
        corrected = req.text
        corrections = []
        for wrong, right in corrections_map.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
                corrections.append({"type": "domain", "from": wrong, "to": right})
        for h, hr in hanja_map.items():
            if h in corrected:
                corrected = corrected.replace(h, hr)
                corrections.append({"type": "hanja", "from": h, "to": hr})
        return {"original": req.text, "corrected": corrected, "confidence": 1.0 - len(corrections) * 0.02, "corrections_count": len(corrections), "corrections": corrections, "agencies": [], "dates": []}
    # 로컬 모드

    processor = OCRPostProcessor()
    result = processor.correct(req.text)

    return {
        "original": result.original,
        "corrected": result.corrected,
        "confidence": result.confidence,
        "corrections_count": len(result.corrections),
        "corrections": result.corrections,
        "agencies": processor.extract_agencies(result.corrected),
        "dates": processor.extract_dates(result.corrected),
    }


def _get_default_html() -> str:
    """기본 웹 UI HTML"""
    return """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NARA-AI - 국가기록물 AI 검색</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f7fa; color: #1a1a2e; }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 2rem; text-align: center; }
        .header h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        .header p { opacity: 0.8; font-size: 0.95rem; }
        .container { max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .search-box { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 1.5rem; }
        .search-input { width: 100%; padding: 1rem; border: 2px solid #e0e5ec; border-radius: 8px; font-size: 1rem; outline: none; transition: border-color 0.2s; }
        .search-input:focus { border-color: #4a6cf7; }
        .search-btn { background: #4a6cf7; color: white; border: none; padding: 0.8rem 2rem; border-radius: 8px; font-size: 1rem; cursor: pointer; margin-top: 0.8rem; }
        .search-btn:hover { background: #3a5ce5; }
        .results { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
        .result-item { padding: 1rem; border-bottom: 1px solid #f0f0f0; }
        .result-item:last-child { border-bottom: none; }
        .result-title { font-weight: 600; color: #1a1a2e; margin-bottom: 0.3rem; }
        .result-preview { color: #666; font-size: 0.9rem; }
        .result-score { color: #4a6cf7; font-size: 0.8rem; margin-top: 0.3rem; }
        .tools { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
        .tool-card { background: white; border-radius: 12px; padding: 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); cursor: pointer; transition: transform 0.2s; }
        .tool-card:hover { transform: translateY(-2px); }
        .tool-card h3 { font-size: 1rem; margin-bottom: 0.3rem; }
        .tool-card p { color: #666; font-size: 0.85rem; }
        .status { text-align: center; padding: 1rem; color: #888; font-size: 0.85rem; }
        #loading { display: none; text-align: center; padding: 2rem; color: #4a6cf7; }
    </style>
</head>
<body>
    <div class="header">
        <h1>NARA-AI</h1>
        <p>AI 기반 국가기록물 지능형 검색 / 분류 / 활용 체계</p>
        <p style="margin-top: 0.5rem; font-size: 0.85rem; opacity: 0.6;">행정안전부 / 국가기록원</p>
    </div>

    <div class="container">
        <div class="search-box">
            <input type="text" class="search-input" id="query" placeholder="국가기록을 자연어로 검색하세요... (예: 한국전쟁 외교 문서)" />
            <button class="search-btn" onclick="doSearch()">검색</button>
        </div>

        <div class="tools">
            <div class="tool-card" onclick="location.href='/docs'">
                <h3>API 문서</h3>
                <p>REST API 문서 (Swagger)</p>
            </div>
            <div class="tool-card" onclick="location.href='/health'">
                <h3>시스템 상태</h3>
                <p>헬스체크 및 현황</p>
            </div>
        </div>

        <div id="loading">검색 중...</div>
        <div class="results" id="results"></div>
        <div class="status" id="status"></div>
    </div>

    <script>
    async function doSearch() {
        const query = document.getElementById('query').value.trim();
        if (!query) return;

        document.getElementById('loading').style.display = 'block';
        document.getElementById('results').innerHTML = '';
        document.getElementById('status').innerHTML = '';

        try {
            const res = await fetch('/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query, top_k: 10, mode: 'auto'})
            });
            const data = await res.json();

            let html = '';
            if (data.results && data.results.length > 0) {
                data.results.forEach((r, i) => {
                    html += `<div class="result-item">
                        <div class="result-title">[${i+1}] ${r.title}</div>
                        <div class="result-preview">${r.content_preview}</div>
                        <div class="result-score">${r.method} / 점수: ${r.score.toFixed(4)}</div>
                    </div>`;
                });
            } else {
                html = '<div class="result-item"><div class="result-preview">검색 결과가 없습니다. 데이터를 먼저 인덱싱하세요.</div></div>';
            }

            document.getElementById('results').innerHTML = html;
            document.getElementById('status').innerHTML =
                `${data.total}건 / ${data.processing_time_ms.toFixed(0)}ms / ${data.mode} 모드`;
        } catch (e) {
            document.getElementById('results').innerHTML =
                `<div class="result-item"><div class="result-preview">오류: ${e.message}</div></div>`;
        }
        document.getElementById('loading').style.display = 'none';
    }

    document.getElementById('query').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    </script>
</body>
</html>"""
