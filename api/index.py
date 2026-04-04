# -*- coding: utf-8 -*-
"""
NARA-AI Vercel Serverless API

외부 의존성 없이 동작하는 경량 API.
Vercel에서 자동으로 /* 엔드포인트로 서빙됨.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

KST = timezone(timedelta(hours=9))

app = FastAPI(title="NARA-AI", version="1.0.0")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    mode: str = "auto"

class PIIRequest(BaseModel):
    content: str = Field(..., min_length=1)

class OCRRequest(BaseModel):
    text: str = Field(..., min_length=1)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "project": "NARA-AI",
        "version": "1.0.0",
        "mode": "cloud (Vercel)",
        "timestamp": datetime.now(KST).isoformat(),
    }


@app.get("/status")
def status():
    return {
        "project": "NARA-AI",
        "version": "1.0.0",
        "mode": "cloud (Vercel)",
        "pipeline_stages": 11,
        "hitl_gates": 4,
        "mcp_tools": 47,
        "ai_agents": 6,
        "gpu_profiles": 12,
        "timestamp": datetime.now(KST).isoformat(),
    }


PII_PATTERNS = {
    "resident_id": (r"\d{6}-[1-4]\d{6}", "주민등록번호", "critical"),
    "phone": (r"01[0-9]-?\d{3,4}-?\d{4}", "전화번호", "high"),
    "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "이메일", "medium"),
    "passport": (r"[A-Z]{1,2}\d{7,8}", "여권번호", "critical"),
    "driver_license": (r"\d{2}-\d{6}-\d{2}", "운전면허번호", "critical"),
    "account": (r"\d{3,4}-\d{2,6}-\d{2,6}", "계좌번호", "high"),
}

@app.post("/pii/detect")
def detect_pii(req: PIIRequest):
    detections = []
    masked = req.content
    for ptype, (pat, name, sev) in PII_PATTERNS.items():
        for m in re.finditer(pat, req.content):
            txt = m.group()
            mk = txt[:2] + "*" * (len(txt) - 2)
            detections.append({"type": ptype, "name": name, "severity": sev, "masked": mk})
    # 역순 마스킹 (offset 보존)
    for ptype, (pat, name, sev) in PII_PATTERNS.items():
        for m in reversed(list(re.finditer(pat, masked))):
            txt = m.group()
            mk = txt[:2] + "*" * (len(txt) - 2)
            masked = masked[:m.start()] + mk + masked[m.end():]
    return {
        "original_length": len(req.content),
        "pii_count": len(detections),
        "detections": detections,
        "masked_content": masked,
    }


OCR_CORRECTIONS = {
    "행정안전뷰": "행정안전부", "공공기록뭄": "공공기록물",
    "국가기록완": "국가기록원", "보존기갼": "보존기간",
    "대한밍국": "대한민국", "비밀해재": "비밀해제",
    "메타테이터": "메타데이터", "기록관리기괸": "기록관리기관",
}
HANJA_MAP = {
    "國家": "國家(국가)", "記錄": "記錄(기록)", "機關": "機關(기관)",
    "文書": "文書(문서)", "保存": "保存(보존)", "行政": "行政(행정)",
    "政府": "政府(정부)", "法律": "法律(법률)", "公開": "公開(공개)",
    "秘密": "秘密(비밀)",
}

@app.post("/ocr/correct")
def correct_ocr(req: OCRRequest):
    corrected = req.text
    corrections = []
    for wrong, right in OCR_CORRECTIONS.items():
        if wrong in corrected:
            corrected = corrected.replace(wrong, right)
            corrections.append({"type": "domain", "from": wrong, "to": right})
    for h, hr in HANJA_MAP.items():
        if h in corrected:
            corrected = corrected.replace(h, hr)
            corrections.append({"type": "hanja", "from": h, "to": hr})
    confidence = max(0.5, 1.0 - len(corrections) * 0.02)
    # 기관명 추출
    agencies = list(set(re.findall(r'[가-힣]{2,10}(?:부|처|청|원|위원회|공단)', corrected)))
    # 날짜 추출
    dates = re.findall(r'\d{4}-\d{2}-\d{2}|\d{4}년\s?\d{1,2}월\s?\d{1,2}일', corrected)
    return {
        "original": req.text,
        "corrected": corrected,
        "confidence": confidence,
        "corrections_count": len(corrections),
        "corrections": corrections,
        "agencies": agencies,
        "dates": dates,
    }


@app.post("/search")
def search(req: SearchRequest):
    return {
        "query": req.query,
        "results": [],
        "total": 0,
        "processing_time_ms": 0,
        "mode": "cloud",
        "message": "클라우드 모드: 로컬 서버(run.bat)에서 검색 데이터를 인덱싱 후 사용하세요.",
    }
