# -*- coding: utf-8 -*-
"""
NARA-AI 유니버설 API — 로컬 / Vercel / AWS Lambda / Docker 통합

하나의 FastAPI 앱이 환경을 자동 감지하여 최적 모드로 동작한다.
src/ 모듈이 있으면 풀 기능, 없으면 인라인 폴백으로 동작.

환경 감지:
  VERCEL=1           → Vercel Serverless
  AWS_LAMBDA_*       → AWS Lambda
  DOCKER=1 / /.dockerenv → Docker 컨테이너
  그 외              → 로컬 개발 환경
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════
# UTF-8 보장
# ═══════════════════════════════════════════
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════
# 환경 감지
# ═══════════════════════════════════════════
def detect_env() -> str:
    """실행 환경 자동 감지"""
    if os.getenv("VERCEL"):
        return "vercel"
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "aws_lambda"
    if os.getenv("DOCKER") or Path("/.dockerenv").exists():
        return "docker"
    return "local"


ENV = detect_env()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wmrvypokepngnbcgsjkn.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndtcnZ5cG9rZXBuZ25iY2dzamtuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODA4OTAsImV4cCI6MjA5MDQ1Njg5MH0.NK2DrPR2n_q8ChqjOrh0LRDCC0l6ZKHIQSj_jqjLRHE"
)


# ═══════════════════════════════════════════
# 모듈 동적 로딩 (src/ 있으면 풀 기능, 없으면 폴백)
# ═══════════════════════════════════════════
HAS_SRC = False
try:
    from config.settings import settings as _settings
    HAS_SRC = True
except ImportError:
    _settings = None

# CPU 검색 엔진
_cpu_embedder = None
def get_cpu_embedder():
    global _cpu_embedder
    if _cpu_embedder is not None:
        return _cpu_embedder
    try:
        from src.search.embedding.cpu_embedder import CPUEmbedder
        db_path = str(_settings.CPU_VECTORS_PATH) if _settings else str(BASE_DIR / "data" / "db" / "cpu_vectors.pkl")
        if Path(db_path).exists():
            _cpu_embedder = CPUEmbedder(db_path=db_path)
            return _cpu_embedder
    except ImportError:
        pass
    return None

# PII 탐지기
def get_pii_detector():
    try:
        from src.agents.redaction.agent import RedactionAgent
        return RedactionAgent()
    except ImportError:
        return None

# OCR 교정기
def get_ocr_corrector():
    try:
        from src.ocr.postprocess.corrector import OCRPostProcessor
        return OCRPostProcessor()
    except ImportError:
        return None


# ═══════════════════════════════════════════
# 인라인 폴백 (src/ 없을 때 사용)
# ═══════════════════════════════════════════
PII_PATTERNS = {
    "resident_id": (r"\d{6}-[1-4]\d{6}", "주민등록번호", "critical"),
    "phone": (r"01[0-9]-?\d{3,4}-?\d{4}", "전화번호", "high"),
    "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "이메일", "medium"),
    "passport": (r"[A-Z]{1,2}\d{7,8}", "여권번호", "critical"),
    "driver_license": (r"\d{2}-\d{6}-\d{2}", "운전면허번호", "critical"),
    "account": (r"\d{3,4}-\d{2,6}-\d{2,6}", "계좌번호", "high"),
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


def inline_detect_pii(content: str) -> dict:
    detections = []
    masked = content
    for ptype, (pat, name, sev) in PII_PATTERNS.items():
        for m in re.finditer(pat, content):
            txt = m.group()
            mk = txt[:2] + "*" * (len(txt) - 2)
            detections.append({"type": ptype, "name": name, "severity": sev, "masked": mk})
    for ptype, (pat, name, sev) in PII_PATTERNS.items():
        for m in reversed(list(re.finditer(pat, masked))):
            txt = m.group()
            mk = txt[:2] + "*" * (len(txt) - 2)
            masked = masked[:m.start()] + mk + masked[m.end():]
    return {"pii_count": len(detections), "detections": detections, "masked_content": masked}


def inline_correct_ocr(text: str) -> dict:
    corrected = text
    corrections = []
    for wrong, right in OCR_CORRECTIONS.items():
        if wrong in corrected:
            corrected = corrected.replace(wrong, right)
            corrections.append({"type": "domain", "from": wrong, "to": right})
    for h, hr in HANJA_MAP.items():
        if h in corrected:
            corrected = corrected.replace(h, hr)
            corrections.append({"type": "hanja", "from": h, "to": hr})
    agencies = list(set(re.findall(r'[가-힣]{2,10}(?:부|처|청|원|위원회|공단)', corrected)))
    dates = re.findall(r'\d{4}-\d{2}-\d{2}|\d{4}년\s?\d{1,2}월\s?\d{1,2}일', corrected)
    return {
        "original": text, "corrected": corrected,
        "confidence": max(0.5, 1.0 - len(corrections) * 0.02),
        "corrections_count": len(corrections), "corrections": corrections,
        "agencies": agencies, "dates": dates,
    }


async def supabase_search(query: str, top_k: int = 10) -> list[dict]:
    """Supabase REST API 검색 (Vercel/AWS 폴백)"""
    import httpx
    words = [w.strip() for w in query.split() if len(w.strip()) >= 2]
    if not words:
        return []
    conditions = " or ".join(f"title.ilike.%25{w}%25,content.ilike.%25{w}%25" for w in words)
    url = f"{SUPABASE_URL}/rest/v1/nara_records?or=({conditions})&select=id,title,content,agency&limit={top_k}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            })
            data = r.json() if r.status_code == 200 else []
    except Exception:
        data = []
    results = []
    for row in data:
        text = (row.get("title", "") + " " + row.get("content", "")).lower()
        match_count = sum(1 for w in words if w.lower() in text)
        score = match_count / len(words) if words else 0
        results.append({
            "id": row.get("id", ""), "title": row.get("title", ""),
            "content_preview": row.get("content", "")[:200],
            "score": round(score, 4), "method": "supabase",
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ═══════════════════════════════════════════
# FastAPI 앱
# ═══════════════════════════════════════════
app = FastAPI(
    title="NARA-AI",
    description="AI 기반 국가기록물 지능형 검색/분류/활용 체계 (유니버설 API)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (로컬/Docker에서만)
static_dir = BASE_DIR / "static"
if static_dir.exists() and ENV in ("local", "docker"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ─── 요청/응답 모델 ───

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    mode: str = Field(default="auto")

class PIIRequest(BaseModel):
    content: str = Field(..., min_length=1)

class OCRRequest(BaseModel):
    text: str = Field(..., min_length=1)

class ClassifyRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    agency: str = ""

class MetadataRequest(BaseModel):
    content: str = Field(..., min_length=1)

class RedactionReviewRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    security_level: str = "secret"
    years_since_creation: int = 0


# ─── BRM 카테고리 ───

BRM_CATEGORIES = {
    "A": "일반공공행정", "B": "공공질서및안전", "C": "통일외교", "D": "국방",
    "E": "교육", "F": "문화및관광", "G": "환경", "H": "사회복지",
    "I": "보건", "J": "농림해양수산", "K": "산업중소기업에너지",
    "L": "교통및물류", "M": "통신", "N": "국토및지역개발",
    "O": "과학기술", "P": "재정금융",
}


# ─── 엔드포인트 ───

@app.get("/", response_class=HTMLResponse)
async def root():
    """웹 UI"""
    for path in [BASE_DIR / "public" / "index.html", static_dir / "index.html"]:
        if path.exists():
            return FileResponse(str(path))
    return HTMLResponse("<h1>NARA-AI</h1><p>웹 UI: static/index.html 또는 public/index.html 필요</p>")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "project": "NARA-AI",
        "version": "1.0.0",
        "env": ENV,
        "has_src": HAS_SRC,
        "has_cpu_index": get_cpu_embedder() is not None,
        "timestamp": datetime.now(KST).isoformat(),
    }


@app.get("/status")
async def status():
    info: dict[str, Any] = {
        "project": "NARA-AI", "version": "1.0.0", "env": ENV,
        "has_src": HAS_SRC,
        "pipeline_stages": 11, "hitl_gates": 4, "mcp_tools": 47,
        "timestamp": datetime.now(KST).isoformat(),
    }
    if HAS_SRC and _settings:
        info["settings"] = _settings.dump()
    return info


@app.post("/search")
async def search(req: SearchRequest):
    start = time.monotonic()

    # 1순위: 로컬 CPU 인덱스
    embedder = get_cpu_embedder()
    if embedder:
        results = embedder.search(req.query, top_k=req.top_k)
        search_results = [
            {"id": r.id, "title": r.title, "content_preview": r.content_preview,
             "score": r.score, "method": r.method}
            for r in results
        ]
        mode = "cpu"
    else:
        # 2순위: Supabase 클라우드 검색
        search_results = await supabase_search(req.query, req.top_k)
        mode = "cloud (Supabase)"

    duration = (time.monotonic() - start) * 1000
    return {
        "query": req.query, "results": search_results,
        "total": len(search_results), "processing_time_ms": round(duration, 1),
        "mode": mode, "env": ENV,
    }


@app.post("/pii/detect")
async def detect_pii(req: PIIRequest):
    agent = get_pii_detector()
    if agent:
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
    else:
        result = inline_detect_pii(req.content)
        return {"original_length": len(req.content), **result}


@app.post("/ocr/correct")
async def correct_ocr(req: OCRRequest):
    corrector = get_ocr_corrector()
    if corrector:
        result = corrector.correct(req.text)
        return {
            "original": result.original, "corrected": result.corrected,
            "confidence": result.confidence,
            "corrections_count": len(result.corrections),
            "corrections": result.corrections,
            "agencies": corrector.extract_agencies(result.corrected),
            "dates": corrector.extract_dates(result.corrected),
        }
    else:
        return inline_correct_ocr(req.text)


# ─── 새 엔드포인트: 분류, 메타데이터, 비밀해제, 통계, 파이프라인 ───

@app.post("/classify")
async def classify_record(req: ClassifyRequest):
    """BRM 업무기능 분류 (실제 17,634건 BRM 데이터 기반)"""
    text = f"{req.title} {req.content} {req.agency}"

    # 실제 BRM 트리 사용 시도
    try:
        from src.brm.parser import get_brm_tree
        tree = get_brm_tree()
        if tree._loaded:
            results = tree.classify_text(text)
            if results:
                top = results[0]
                return {
                    "brm_code": top["brm_name"],
                    "brm_name": top["brm_name"],
                    "confidence": top["confidence"],
                    "reasoning": f"BRM 17,634건 데이터 기반 분류. '{req.title}'에서 '{top['brm_name']}' 관련 키워드 매칭.",
                    "alternatives": results[1:4],
                    "data_source": "행정안전부 정부기능별분류체계 (17,634건)",
                }
    except ImportError:
        pass

    # 폴백: 인라인 키워드 분류
    content_lower = text.lower()
    scores = {}
    keywords_map = {
        "일반공공행정": ["행정", "기록물", "공무원", "정부혁신", "인사", "조직"],
        "공공질서및안전": ["경찰", "소방", "재난", "치안", "안전"],
        "통일·외교": ["외교", "통일", "남북", "전쟁", "독립운동", "국제"],
        "국방": ["국방", "군사", "안보", "병역", "방위"],
        "교육": ["교육", "학교", "교과", "입시", "장학"],
        "문화체육관광": ["문화", "관광", "유산", "박물관", "콘텐츠", "실록"],
        "환경": ["환경", "생태", "탄소", "미세먼지", "폐기물"],
        "사회복지": ["복지", "수급", "저출생", "노인", "장애", "아동"],
        "보건": ["보건", "의료", "코로나", "감염", "건강"],
        "농림": ["농업", "축산", "식량", "스마트팜"],
        "해양수산": ["수산", "해양", "어업", "항만"],
        "산업·통상·중소기업": ["산업", "반도체", "에너지", "중소기업", "소상공인", "통상"],
        "교통및물류": ["교통", "철도", "항공", "물류", "도로"],
        "통신": ["통신", "5G", "디지털", "네트워크", "방송"],
        "지역개발": ["국토", "택지", "도시재생", "주택", "지역"],
        "과학기술": ["과학", "기술", "R&D", "우주", "양자", "AI", "연구"],
        "재정·세제·금융": ["재정", "세금", "국채", "금융", "예산", "세제"],
    }
    for code, kws in keywords_map.items():
        match_count = sum(1 for kw in kws if kw in content_lower)
        if match_count > 0:
            scores[code] = match_count / len(kws)

    if not scores:
        scores["일반공공행정"] = 0.3

    sorted_codes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = sorted_codes[0]
    alternatives = [
        {"brm_name": c, "confidence": round(s, 2)}
        for c, s in sorted_codes[1:4]
    ]

    return {
        "brm_code": top[0],
        "brm_name": top[0],
        "confidence": round(min(top[1] * 2, 0.95), 2),
        "reasoning": f"키워드 매칭 기반 분류. '{req.title}'에서 '{top[0]}' 관련 키워드 탐지.",
        "alternatives": alternatives,
        "data_source": "인라인 폴백 (BRM CSV 미로드)",
    }


@app.post("/metadata")
async def generate_metadata(req: MetadataRequest):
    """메타데이터 자동 생성"""
    content = req.content
    # 제목 추출 (첫 문장 또는 첫 50자)
    first_sentence = content.split(".")[0].strip() if "." in content else content[:50]
    title = first_sentence[:60]

    # 요약 (첫 200자)
    summary = content[:200].strip()

    # 키워드 추출 (빈도 기반)
    import re as _re
    words = _re.findall(r'[가-힣]{2,}', content)
    from collections import Counter
    word_freq = Counter(words)
    stopwords = {"있다", "하다", "되다", "이다", "위한", "따라", "관련", "대한", "통해"}
    keywords = [w for w, _ in word_freq.most_common(20) if w not in stopwords and len(w) >= 2][:10]

    # NER (패턴 기반)
    agencies = list(set(_re.findall(r'[가-힣]{2,10}(?:부|처|청|원|위원회|공단|재단)', content)))
    dates = _re.findall(r'\d{4}년\s?\d{1,2}월\s?\d{1,2}일|\d{4}년|\d{4}-\d{2}-\d{2}', content)
    persons = list(set(_re.findall(r'[가-힣]{2,4}(?:씨|님|장관|청장|위원장|대통령)', content)))

    entities = []
    for a in agencies:
        entities.append({"text": a, "entity_type": "ORGANIZATION", "confidence": 0.85})
    for d in dates:
        entities.append({"text": d, "entity_type": "DATE", "confidence": 0.90})
    for p in persons:
        entities.append({"text": p, "entity_type": "PERSON", "confidence": 0.75})

    return {
        "title_suggestion": title,
        "summary": summary,
        "keywords": keywords,
        "named_entities": entities,
        "entity_count": len(entities),
    }


@app.post("/redaction/review")
async def redaction_review(req: RedactionReviewRequest):
    """비밀해제 심사 도우미 (HITL 필수)"""
    # PII 탐지
    pii_result = inline_detect_pii(req.content)

    # 공개 적합성 판단
    recommendation = "비공개 유지"
    reasoning_parts = []
    legal_basis = "공공기록물법 제34조"

    if req.years_since_creation >= 30:
        recommendation = "공개"
        reasoning_parts.append(f"생산 후 {req.years_since_creation}년 경과 → 30년 원칙적 공개 대상")
        legal_basis = "공공기록물법 제34조 (30년 경과 기록물 공개 원칙)"

    if pii_result["pii_count"] > 0:
        if recommendation == "공개":
            recommendation = "부분공개"
            reasoning_parts.append(f"PII {pii_result['pii_count']}건 탐지 → 가명처리 후 부분공개")
        else:
            reasoning_parts.append(f"PII {pii_result['pii_count']}건 탐지")

    security_concerns = []
    sensitive_keywords = ["국가안보", "군사기밀", "외교비밀", "수사기밀"]
    for kw in sensitive_keywords:
        if kw in req.content:
            security_concerns.append(f"'{kw}' 키워드 포함")
            recommendation = "비공개 유지"
            reasoning_parts.append(f"'{kw}' 관련 내용 포함 → 비공개 유지 권고")

    if not reasoning_parts:
        reasoning_parts.append("특별한 공개 제한 사유 없음")

    confidence = 0.85 if req.years_since_creation >= 30 else 0.6

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reasoning": ". ".join(reasoning_parts),
        "legal_basis": legal_basis,
        "security_concerns": security_concerns,
        "pii_summary": {
            "count": pii_result["pii_count"],
            "detections": pii_result["detections"],
        },
        "hitl_required": True,
        "hitl_warning": "이 결과는 AI 추천이며, 최종 비밀해제 결정은 반드시 기록물관리 전문가가 수행해야 합니다.",
    }


@app.get("/brm/tree")
async def brm_tree():
    """BRM 분류체계 트리 (17,634건)"""
    try:
        from src.brm.parser import get_brm_tree
        tree = get_brm_tree()
        return {
            "stats": tree.get_stats(),
            "top_categories": tree.get_top_categories(),
            "data_source": "행정안전부 정부기능별분류체계 (2024.11.30)",
        }
    except ImportError:
        return {
            "stats": {"total_nodes": 0},
            "top_categories": [{"name": k, "children_count": 0} for k in BRM_CATEGORIES.values()],
            "data_source": "인라인 폴백 (BRM CSV 미로드)",
        }


@app.get("/brm/children/{parent_id}")
async def brm_children(parent_id: str):
    """BRM 하위 분류 조회"""
    try:
        from src.brm.parser import get_brm_tree
        tree = get_brm_tree()
        return {"parent_id": parent_id, "children": tree.get_children(parent_id)}
    except ImportError:
        return {"parent_id": parent_id, "children": []}


@app.get("/brm/search")
async def brm_search(q: str, level: str = "", limit: int = 20):
    """BRM 검색"""
    try:
        from src.brm.parser import get_brm_tree
        tree = get_brm_tree()
        return {"query": q, "results": tree.search(q, level=level, limit=limit)}
    except ImportError:
        return {"query": q, "results": []}


@app.get("/brm/api")
async def brm_api_proxy(page: int = 1, per_page: int = 10):
    """공공데이터포털 BRM API 프록시"""
    try:
        from src.brm.parser import fetch_brm_api
        return await fetch_brm_api(page=page, per_page=per_page)
    except Exception as e:
        return {"error": str(e)}


@app.get("/stats")
async def get_stats():
    """기록물 통계 대시보드"""
    # Supabase에서 통계 조회
    stats = {"brm_distribution": {}, "agency_distribution": {}, "total_records": 0}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/nara_records?select=id,brm_code,agency",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            )
            if r.status_code == 200:
                records = r.json()
                stats["total_records"] = len(records)
                for rec in records:
                    code = rec.get("brm_code", "?")
                    agency = rec.get("agency", "미상")
                    brm_name = BRM_CATEGORIES.get(code, code)
                    stats["brm_distribution"][brm_name] = stats["brm_distribution"].get(brm_name, 0) + 1
                    stats["agency_distribution"][agency] = stats["agency_distribution"].get(agency, 0) + 1
    except Exception:
        pass

    # CPU 인덱스 통계
    embedder = get_cpu_embedder()
    if embedder and hasattr(embedder, 'documents'):
        stats["cpu_index_records"] = len(embedder.documents)

    stats["brm_categories"] = BRM_CATEGORIES
    stats["system"] = {
        "env": ENV, "has_src": HAS_SRC,
        "pipeline_stages": 11, "hitl_gates": 4, "mcp_tools": 47,
        "ai_agents": 6, "gpu_profiles": 12,
    }

    # BRM DB 통계
    try:
        import httpx as _hx
        async with _hx.AsyncClient(timeout=10) as _c:
            _headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            brm_r = await _c.get(f"{SUPABASE_URL}/rest/v1/brm_nodes?select=level&limit=20000", headers=_headers)
            if brm_r.status_code == 200:
                brm_data = brm_r.json()
                brm_levels = {}
                for row in brm_data:
                    lv = row.get("level", "?")
                    brm_levels[lv] = brm_levels.get(lv, 0) + 1
                stats["brm_db"] = {"total": len(brm_data), "levels": brm_levels}

            bsc_r = await _c.get(f"{SUPABASE_URL}/rest/v1/bsc_nodes?select=id&limit=1", headers={**_headers, "Prefer": "count=exact"})
            stats["bsc_total"] = int(bsc_r.headers.get("content-range", "0/0").split("/")[-1]) if bsc_r.status_code == 200 else 0

            cul_r = await _c.get(f"{SUPABASE_URL}/rest/v1/culture_nodes?select=id&limit=1", headers={**_headers, "Prefer": "count=exact"})
            stats["culture_total"] = int(cul_r.headers.get("content-range", "0/0").split("/")[-1]) if cul_r.status_code == 200 else 0
    except Exception:
        pass

    return stats


@app.get("/pipeline")
async def get_pipeline():
    """11단계 파이프라인 정보"""
    stages = [
        {"id": 1, "name": "수집 (Ingest)", "desc": "RAMP/파일시스템에서 기록물 수집", "icon": "📥"},
        {"id": 2, "name": "레이아웃 (Layout)", "desc": "YOLO-DocLayout 문서 영역 분석", "icon": "📐"},
        {"id": 3, "name": "OCR", "desc": "3모델 앙상블 (Qwen3-VL + PaddleOCR + TrOCR)", "icon": "🔍"},
        {"id": 4, "name": "후처리 (Post)", "desc": "맞춤법 교정, 한자 병기, 구조화", "icon": "✏️"},
        {"id": 5, "name": "분류 (Classify)", "desc": "BRM 업무기능 자동 매핑 (F1>=0.92)", "icon": "🏷️"},
        {"id": 6, "name": "메타데이터 (Metadata)", "desc": "제목/요약/키워드/NER 자동 생성", "icon": "📋"},
        {"id": 7, "name": "비밀해제 (Redaction)", "desc": "PII 탐지 + 공개 적합성 [HITL 필수]", "icon": "🔓", "hitl": True},
        {"id": 8, "name": "임베딩 (Embedding)", "desc": "BGE-M3-Korean 1024차원 벡터화", "icon": "🧮"},
        {"id": 9, "name": "그래프 (Graph)", "desc": "RiC-CM 1.0 지식그래프 노드/관계", "icon": "🕸️"},
        {"id": 10, "name": "품질 (Quality)", "desc": "6항목 품질 검증 게이트", "icon": "✅"},
        {"id": 11, "name": "보안 (Security)", "desc": "4중 보안 스캐닝 (ISMS-P)", "icon": "🛡️"},
    ]
    hitl_gates = [
        {"action": "비밀해제 심사", "law": "공공기록물법 제34조", "desc": "비공개→공개 전환 최종 결정"},
        {"action": "보존기간 변경", "law": "공공기록물법 제38조", "desc": "보존기간 연장/단축 승인"},
        {"action": "분류 이의", "law": "공공기록물법 제33조", "desc": "AI 분류에 대한 이의 처리"},
        {"action": "폐기 승인", "law": "공공기록물법 제26조", "desc": "기록물 폐기 2인 이상 승인"},
    ]
    compliance = [
        {"name": "AI 기본법", "date": "2026.1", "items": ["HITL 4개", "감사추적", "설명가능성", "편향방지"]},
        {"name": "ISMS-P", "date": "2027.7", "items": ["JWT+RBAC", "PII 6종", "4중 스캔", "TLS 1.3"]},
        {"name": "N2SF", "date": "적용중", "items": ["에어갭", "망분리", "데이터주권", "CSAP"]},
        {"name": "공공기록물법", "date": "적용중", "items": ["비밀해제HITL", "폐기2인승인", "30년공개", "감사10년"]},
    ]
    return {"stages": stages, "hitl_gates": hitl_gates, "compliance": compliance}
