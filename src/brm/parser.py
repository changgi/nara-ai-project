# -*- coding: utf-8 -*-
"""
BRM 정부기능별분류체계 파서

행정안전부 정부기능별분류체계 CSV (17,634건)를 파싱하여
5계층 구조 (정책분야→정책영역→대기능→중기능→소기능)로 제공한다.

공공데이터포털 API 연동도 지원.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 공공데이터포털 API 설정
DATA_GO_KR_API_KEY = os.getenv(
    "DATA_GO_KR_API_KEY",
    "54cc7e1280432ff67a19bbbdcf88021d35c4c7d34aef5ff81b6f4b948f8b9227"
)
BRM_API_BASE = "https://api.odcloud.kr/api/15062615/v1"
BRM_API_ENDPOINTS = {
    "endpoint_1": f"{BRM_API_BASE}/uddi:4f6f8261-0137-4cb1-be92-eee0752d3c1d",
    "endpoint_2": f"{BRM_API_BASE}/uddi:518ef78b-964b-4a55-bcf9-cdbeccd9e9d8",
    "endpoint_3": f"{BRM_API_BASE}/uddi:5cf8e011-80f5-44ed-a639-a99c48cdd74e",
    "endpoint_4": f"{BRM_API_BASE}/uddi:fca3d5a5-7418-4c6e-aad6-ff6fabfd723b",
}

# BRM 계층 레벨
BRM_LEVELS = ["정책분야", "정책영역", "대기능", "중기능", "소기능"]


@dataclass
class BRMNode:
    """BRM 분류 노드"""
    id: str                      # 분류체계ID
    name: str                    # 분류체계명
    level: str                   # 정책분야/정책영역/대기능/중기능/소기능
    parent_id: str               # 상위과제ID ('0'이면 루트)
    path: str                    # 분류체계경로 (>> 구분)
    agencies: list[str] = field(default_factory=list)  # 수행기관
    agency_codes: list[str] = field(default_factory=list)  # 기관코드
    effective_date: str = ""     # 시행시기
    children: list["BRMNode"] = field(default_factory=list)


class BRMTree:
    """BRM 5계층 트리"""

    def __init__(self):
        self.nodes: dict[str, BRMNode] = {}
        self.roots: list[BRMNode] = []  # 정책분야 (17개)
        self._loaded = False

    def load_csv(self, csv_path: str) -> int:
        """CSV 파일에서 BRM 데이터 로드"""
        count = 0
        # CP949 → UTF-8
        with open(csv_path, "r", encoding="cp949", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                level = row.get("분류체계단계", "").strip()
                if level not in BRM_LEVELS:
                    continue

                node_id = row.get("분류체계ID", "").strip()
                agencies_raw = row.get("수행기관", "")
                agencies = [a.strip() for a in agencies_raw.split("|") if a.strip()] if agencies_raw else []
                codes_raw = row.get("기관코드", "")
                codes = [c.strip() for c in codes_raw.split("|") if c.strip()] if codes_raw else []

                node = BRMNode(
                    id=node_id,
                    name=row.get("분류체계명", "").strip(),
                    level=level,
                    parent_id=row.get("상위과제ID", "0").strip(),
                    path=row.get("분류체계경로", "").strip(),
                    agencies=agencies,
                    agency_codes=codes,
                    effective_date=row.get("시행시기", "").strip(),
                )
                self.nodes[node_id] = node
                count += 1

        # 부모-자식 관계 구축
        for node in self.nodes.values():
            if node.parent_id == "0" or node.parent_id not in self.nodes:
                if node.level == "정책분야":
                    self.roots.append(node)
            else:
                parent = self.nodes.get(node.parent_id)
                if parent:
                    parent.children.append(node)

        self._loaded = True
        return count

    def get_top_categories(self) -> list[dict[str, Any]]:
        """정책분야 (대분류) 17개 반환"""
        return [
            {
                "id": n.id,
                "name": n.name,
                "children_count": len(n.children),
                "path": n.path,
            }
            for n in sorted(self.roots, key=lambda x: x.name)
        ]

    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """특정 노드의 하위 분류 반환"""
        parent = self.nodes.get(parent_id)
        if not parent:
            return []
        return [
            {
                "id": c.id,
                "name": c.name,
                "level": c.level,
                "children_count": len(c.children),
                "agencies": c.agencies[:5],
            }
            for c in sorted(parent.children, key=lambda x: x.name)
        ]

    def search(self, keyword: str, level: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """BRM 키워드 검색 (페이지네이션, 전체 건수 포함)"""
        all_matches = []
        keyword_lower = keyword.lower()
        for node in self.nodes.values():
            if level and node.level != level:
                continue
            if keyword_lower in node.name.lower() or keyword_lower in node.path.lower():
                all_matches.append({
                    "id": node.id,
                    "name": node.name,
                    "level": node.level,
                    "path": node.path,
                    "agencies": node.agencies[:3],
                })

        total = len(all_matches)
        # 레벨 우선순위 정렬: 정책분야 > 정책영역 > 대기능 > 중기능 > 소기능
        level_order = {"정책분야": 0, "정책영역": 1, "대기능": 2, "중기능": 3, "소기능": 4}
        all_matches.sort(key=lambda x: (level_order.get(x["level"], 9), x["name"]))

        page = all_matches[offset:offset + limit]
        return {"results": page, "total": total, "offset": offset, "limit": limit}

    def get_stats(self) -> dict[str, Any]:
        """통계"""
        level_counts = {}
        agency_set = set()
        for node in self.nodes.values():
            level_counts[node.level] = level_counts.get(node.level, 0) + 1
            agency_set.update(node.agencies)
        return {
            "total_nodes": len(self.nodes),
            "levels": level_counts,
            "top_categories": len(self.roots),
            "unique_agencies": len(agency_set),
        }

    def classify_text(self, text: str) -> list[dict[str, Any]]:
        """BRM 맥락 기반 3단계 분류 (추정→추적→정밀화)

        단순 키워드 매칭이 아닌, 텍스트의 맥락(의미)을 이해하여
        17,634건 BRM 중 가장 적합한 위치를 찾는다.

        1단계 추정: 텍스트의 핵심 주제어로 직접 매칭되는 BRM 노드 탐색
        2단계 추적: 매칭된 노드의 상위 경로를 추적하여 영역 확정
        3단계 정밀화: 확정된 영역 내에서 가장 구체적인 노드 선택
        """
        import re
        text_lower = text.lower()

        # 텍스트에서 핵심 주제어 추출 (2글자 이상 한글)
        text_words = list(dict.fromkeys(re.findall(r'[가-힣]{2,}', text)))  # 순서 유지 중복 제거

        # 일반어 (BRM 17,634건 중 수백 개에 등장) vs 구체어 구분
        STOP_WORDS = {
            "추진", "지원", "관리", "운영", "사업", "계획", "정책", "행정", "기획",
            "조사", "분석", "평가", "감사", "연구", "개발", "협력", "조정", "보고",
            "총괄", "기반", "체계", "시스템", "서비스", "정보", "데이터", "통계",
            "예산", "재정", "인력", "조직", "제도", "법령", "규정", "기준",
            "홍보", "소통", "대외", "국제", "보호", "진흥", "확충",
            "확대", "강화", "개선", "혁신", "고도화", "활성화", "내실화",
            "방안", "대책", "현황", "결과", "발표", "수립", "시행",
        }
        # 핵심 주제어 = 일반어를 제외한 구체적 단어
        key_words = [w for w in text_words if w not in STOP_WORDS and len(w) >= 2]
        context_words = text_words  # 맥락 파악용 전체 단어

        # ═══ 1단계: 추정 (핵심 주제어로 직접 후보 찾기) ═══
        # BRM 노드의 이름 또는 전체 경로에 핵심 주제어가 포함되는지 확인
        direct_hits: list[tuple[float, Any, list[str]]] = []

        for node in self.nodes.values():
            node_text = f"{node.name} {node.path}".lower()
            matched = []
            score = 0.0

            # 핵심 주제어 매칭 (높은 가중치)
            for kw in key_words:
                if kw in node.name:
                    score += 3.0  # 이름에 직접 포함: 최고점
                    matched.append(kw)
                elif kw in node_text:
                    score += 1.0  # 경로에 포함: 중간점
                    matched.append(f"({kw})")

            if score == 0:
                continue

            # 맥락어 보너스 (일반어지만 맥락 확인용)
            for cw in context_words:
                if cw in STOP_WORDS and cw in node_text:
                    score += 0.1  # 맥락 일치 소폭 보너스

            # 레벨 세밀도 보너스
            level_bonus = {"소기능": 0.5, "중기능": 0.3, "대기능": 0.1, "정책영역": 0.0, "정책분야": -0.2}
            score += level_bonus.get(node.level, 0)

            direct_hits.append((score, node, matched))

        # ═══ 2단계: 추적 (상위 영역 패턴 분석) ═══
        # 1단계 후보들의 경로를 분석하여 가장 많이 등장하는 상위 영역 확인
        area_votes: dict[str, float] = {}
        for score, node, matched in direct_hits:
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            # 각 경로 수준에 점수 부여
            for depth, part in enumerate(path_parts):
                weight = score * (0.5 ** depth)  # 상위일수록 높은 가중치
                area_key = ">>".join(path_parts[:depth+1])
                area_votes[area_key] = area_votes.get(area_key, 0) + weight

        if not area_votes:
            return []

        # 가장 지지를 많이 받은 영역 (정책분야 수준)
        top_area_votes = sorted(area_votes.items(), key=lambda x: x[1], reverse=True)

        # ═══ 3단계: 정밀화 (2단계 영역 일치 보너스 적용) ═══
        # 2단계에서 가장 지지받은 정책분야 상위 3개
        top_area_names = set()
        for area_path, _ in top_area_votes[:10]:
            top_name = area_path.split(">>")[0].strip()
            top_area_names.add(top_name)

        # 영역 일치 보너스: 2단계 추적 결과와 동일 정책분야면 점수 x2
        boosted_hits = []
        for score, node, matched in direct_hits:
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            node_top = path_parts[0] if path_parts else ""
            if node_top in top_area_names:
                score *= 2.0  # 영역 일치 보너스
            boosted_hits.append((score, node, matched))

        boosted_hits.sort(key=lambda x: x[0], reverse=True)
        direct_hits = boosted_hits

        # 전체 매칭 결과 구성 (유사도 순 정렬, 중복 제거 없이 전체 반환)
        max_possible = max(len(key_words) * 3.0 + 0.5, 1)
        results = []
        for score, node, matched in direct_hits:
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            confidence = round(min(score / max_possible * 1.5, 0.99), 3)
            confidence = max(confidence, 0.01)

            node_area = ">>".join(path_parts[:2]) if len(path_parts) >= 2 else ""
            area_rank = next((i for i, (k, _) in enumerate(top_area_votes) if k == node_area), 99)

            results.append({
                "node_id": node.id,
                "name": node.name,
                "level": node.level,
                "path": node.path,
                "path_parts": path_parts,
                "confidence": confidence,
                "score": round(score, 2),
                "agencies": node.agencies[:3],
                "matched_keywords": [m for m in matched if not m.startswith("(")][:5],
                "analysis": {
                    "phase1_key_words": key_words[:5],
                    "phase1_direct_hits": len(direct_hits),
                    "phase2_top_area": top_area_votes[0][0] if top_area_votes else "",
                    "phase2_area_score": round(top_area_votes[0][1] if top_area_votes else 0, 1),
                    "phase2_area_rank": area_rank + 1,
                    "phase3_level": node.level,
                    "phase3_score": round(score, 2),
                },
            })

        return results


# 글로벌 BRM 트리 (싱글톤)
_brm_tree: Optional[BRMTree] = None


def get_brm_tree() -> BRMTree:
    """BRM 트리 로드 (싱글톤)"""
    global _brm_tree
    if _brm_tree is not None and _brm_tree._loaded:
        return _brm_tree

    _brm_tree = BRMTree()
    # CSV 파일 경로 탐색
    base = Path(__file__).resolve().parent.parent.parent
    csv_paths = [
        base / "add" / "행정안전부_정부기능별분류체계_20241130.csv",
        base / "add" / "분류체계정보_기능별분류.csv",
    ]
    for csv_path in csv_paths:
        if csv_path.exists():
            _brm_tree.load_csv(str(csv_path))
            break

    return _brm_tree


async def fetch_brm_api(endpoint_key: str = "endpoint_1", page: int = 1, per_page: int = 100) -> dict:
    """공공데이터포털 BRM API 호출"""
    import httpx
    url = BRM_API_ENDPOINTS.get(endpoint_key, BRM_API_ENDPOINTS["endpoint_1"])
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "page": page,
        "perPage": per_page,
        "returnType": "JSON",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        if r.status_code == 200:
            return r.json()
        return {"error": f"API 호출 실패: {r.status_code}", "text": r.text[:200]}
