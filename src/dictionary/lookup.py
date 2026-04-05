# -*- coding: utf-8 -*-
"""
사전 연동 MCP — 단어 검증 + 정의 수집 + DB 축적

4개 소스:
1. 표준국어대사전 (stdict.korean.go.kr) — 공식 국어사전
2. 다음사전 (dic.daum.net) — 국어/영어/한자 통합
3. 나무위키 (namu.wiki) — 대중적 지식
4. 위키피디아 (ko.wikipedia.org) — 백과사전

기능:
- is_real_word(word): 사전에 존재하는 실제 단어인지 확인
- lookup(word): 4개 소스에서 정의/설명 수집
- collect_and_store(word): DB에 축적
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wmrvypokepngnbcgsjkn.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndtcnZ5cG9rZXBuZ25iY2dzamtuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODA4OTAsImV4cCI6MjA5MDQ1Njg5MH0.NK2DrPR2n_q8ChqjOrh0LRDCC0l6ZKHIQSj_jqjLRHE"
)


@dataclass
class DictEntry:
    """사전 검색 결과"""
    word: str
    source: str           # stdict, daum, namuwiki, wikipedia
    exists: bool          # 사전에 존재하는지
    definition: str = ""  # 정의/설명 (첫 200자)
    category: str = ""    # 품사/분류
    url: str = ""         # 출처 URL
    related: list[str] = field(default_factory=list)  # 관련어
    collected_at: str = ""


class DictionaryLookup:
    """4개 사전 통합 조회"""

    def __init__(self):
        self.client = httpx.Client(timeout=10, follow_redirects=True, headers={
            "User-Agent": "NARA-AI/1.0 (National Archives AI System)"
        })
        self._cache: dict[str, list[DictEntry]] = {}

    def lookup(self, word: str) -> list[DictEntry]:
        """4개 소스에서 단어 조회"""
        if word in self._cache:
            return self._cache[word]

        entries = []
        entries.append(self._lookup_stdict(word))
        entries.append(self._lookup_daum(word))
        entries.append(self._lookup_wikipedia(word))
        entries.append(self._lookup_namuwiki(word))

        self._cache[word] = entries
        return entries

    def is_real_word(self, word: str) -> bool:
        """실제 단어인지 확인 (1개 이상 사전에 존재)"""
        entries = self.lookup(word)
        return any(e.exists for e in entries)

    def get_definition(self, word: str) -> str:
        """가장 좋은 정의 반환"""
        entries = self.lookup(word)
        for e in entries:
            if e.exists and e.definition:
                return e.definition
        return ""

    def _lookup_stdict(self, word: str) -> DictEntry:
        """표준국어대사전 검색"""
        url = f"https://stdict.korean.go.kr/api/search.do"
        entry = DictEntry(word=word, source="stdict", exists=False,
                          url=f"https://stdict.korean.go.kr/search/searchResult.do?pageSize=10&searchKeyword={word}")
        try:
            # 표준국어대사전 Open API (key 불필요한 검색)
            r = self.client.get(
                "https://stdict.korean.go.kr/api/search.do",
                params={"key": "", "q": word, "req_type": "json", "num": 3},
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    items = data.get("channel", {}).get("item", [])
                    if items:
                        first = items[0] if isinstance(items, list) else items
                        entry.exists = True
                        entry.definition = first.get("sense", {}).get("definition", "")[:200] if isinstance(first.get("sense"), dict) else ""
                        entry.category = first.get("pos", "")
                except (json.JSONDecodeError, KeyError):
                    # HTML 응답인 경우 단어 존재 여부만 확인
                    if word in r.text:
                        entry.exists = True
        except Exception:
            pass
        entry.collected_at = datetime.now(KST).isoformat()
        return entry

    def _lookup_daum(self, word: str) -> DictEntry:
        """다음사전 검색"""
        entry = DictEntry(word=word, source="daum", exists=False,
                          url=f"https://dic.daum.net/search.do?q={word}")
        try:
            r = self.client.get(f"https://dic.daum.net/search.do", params={"q": word, "dic": "kor"})
            if r.status_code == 200:
                # 검색 결과에 단어가 포함되어 있으면 존재
                if f'>{word}<' in r.text or f'"{word}"' in r.text:
                    entry.exists = True
                # 정의 추출 시도
                match = re.search(r'<span class="txt_search">(.*?)</span>', r.text)
                if match:
                    entry.definition = re.sub(r'<[^>]+>', '', match.group(1))[:200]
                    entry.exists = True
        except Exception:
            pass
        entry.collected_at = datetime.now(KST).isoformat()
        return entry

    def _lookup_wikipedia(self, word: str) -> DictEntry:
        """한국어 위키피디아 검색"""
        entry = DictEntry(word=word, source="wikipedia", exists=False,
                          url=f"https://ko.wikipedia.org/wiki/{word}")
        try:
            r = self.client.get(
                "https://ko.wikipedia.org/api/rest_v1/page/summary/" + word,
                headers={"Accept": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("type") != "disambiguation":
                    entry.exists = True
                    entry.definition = data.get("extract", "")[:200]
                    entry.url = data.get("content_urls", {}).get("desktop", {}).get("page", entry.url)
                else:
                    entry.exists = True
                    entry.definition = "동음이의어 문서"
        except Exception:
            pass
        entry.collected_at = datetime.now(KST).isoformat()
        return entry

    def _lookup_namuwiki(self, word: str) -> DictEntry:
        """나무위키 검색 (API 없음, 존재 확인만)"""
        entry = DictEntry(word=word, source="namuwiki", exists=False,
                          url=f"https://namu.wiki/w/{word}")
        try:
            r = self.client.get(f"https://namu.wiki/w/{word}")
            if r.status_code == 200 and "문서가 없습니다" not in r.text:
                entry.exists = True
                # 첫 문단 추출 시도
                match = re.search(r'<div class="wiki-paragraph">(.*?)</div>', r.text, re.DOTALL)
                if match:
                    text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                    entry.definition = text[:200]
        except Exception:
            pass
        entry.collected_at = datetime.now(KST).isoformat()
        return entry

    def close(self):
        self.client.close()


async def store_to_supabase(entries: list[DictEntry]) -> int:
    """사전 결과를 Supabase에 저장"""
    if not entries:
        return 0

    rows = [
        {
            "word": e.word,
            "source": e.source,
            "exists": e.exists,
            "definition": e.definition[:500],
            "category": e.category,
            "url": e.url,
            "collected_at": e.collected_at,
        }
        for e in entries
    ]

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/dictionary_cache",
            json=rows,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
        )
        return len(rows) if r.status_code in (200, 201) else 0


async def check_from_supabase(word: str) -> list[dict]:
    """Supabase 캐시에서 조회"""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/dictionary_cache",
            params={"word": f"eq.{word}", "select": "*"},
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        return r.json() if r.status_code == 200 else []


# 싱글톤
_dict_lookup: Optional[DictionaryLookup] = None

def get_dict_lookup() -> DictionaryLookup:
    global _dict_lookup
    if _dict_lookup is None:
        _dict_lookup = DictionaryLookup()
    return _dict_lookup
