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

    def search(self, keyword: str, level: str = "", limit: int = 20) -> list[dict[str, Any]]:
        """BRM 키워드 검색"""
        results = []
        keyword_lower = keyword.lower()
        for node in self.nodes.values():
            if level and node.level != level:
                continue
            if keyword_lower in node.name.lower() or keyword_lower in node.path.lower():
                results.append({
                    "id": node.id,
                    "name": node.name,
                    "level": node.level,
                    "path": node.path,
                    "agencies": node.agencies[:3],
                })
                if len(results) >= limit:
                    break
        return results

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
        """텍스트를 BRM 5계층 전체 경로로 분류

        반환: [{"node_id", "name", "level", "path", "path_parts", "confidence", "agencies"}]
        path_parts: ["정책분야", "정책영역", "대기능", "중기능", "소기능"]
        """
        text_lower = text.lower()
        candidates: list[tuple[float, Any]] = []

        for node in self.nodes.values():
            if node.level not in ("소기능", "중기능", "대기능"):
                continue
            # 이름의 각 단어가 텍스트에 포함되는지 확인
            name_clean = node.name.replace("·", " ").replace("/", " ").replace("(", " ").replace(")", " ")
            name_words = [w for w in name_clean.split() if len(w) >= 2]
            if not name_words:
                continue
            match_count = sum(1 for w in name_words if w in text_lower)
            if match_count == 0:
                continue

            score = match_count / len(name_words)
            # 레벨이 세밀할수록 보너스 (소기능 > 중기능 > 대기능)
            level_bonus = {"소기능": 0.1, "중기능": 0.05, "대기능": 0.0}
            score += level_bonus.get(node.level, 0)

            candidates.append((score, node))

        # 점수순 정렬, 상위 10개
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[:10]

        # 중복 경로 제거 (같은 상위 경로면 가장 세밀한 것만)
        seen_paths = set()
        results = []
        for score, node in top:
            # 경로를 정책분야>>정책영역>>... 형태로 분해
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            # 상위 3단계까지를 키로 사용 (중복 제거)
            path_key = ">>".join(path_parts[:3]) if len(path_parts) >= 3 else node.path
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            results.append({
                "node_id": node.id,
                "name": node.name,
                "level": node.level,
                "path": node.path,
                "path_parts": path_parts,
                "confidence": round(min(score * 1.5, 0.98), 2),
                "agencies": node.agencies[:5],
            })
            if len(results) >= 5:
                break

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
