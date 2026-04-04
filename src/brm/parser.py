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
        """BRM 3단계 반복 분류 (이산화 → 추상화 → 정밀화)

        1단계 이산화: 텍스트에서 키워드 추출, 전체 BRM과 1차 매칭
        2단계 추상화: 1차 후보의 상위 정책분야/정책영역을 추출, 영역 범위 축소
        3단계 정밀화: 축소된 영역 내에서 소기능 레벨까지 정밀 매칭

        반환: 각 결과에 분석 과정(analysis)이 포함됨
        """
        text_lower = text.lower()
        import re
        text_words = set(re.findall(r'[가-힣]{2,}', text))
        text_words_lower = {w.lower() for w in text_words}

        # 일반적인 단어 (BRM 전체에 광범위하게 등장) → 가중치 감쇄
        COMMON_WORDS = {
            "추진", "지원", "관리", "운영", "사업", "계획", "정책", "행정", "기획",
            "조사", "분석", "평가", "감사", "교육", "연구", "개발", "협력", "조정",
            "총괄", "기반", "체계", "시스템", "서비스", "정보", "데이터", "통계",
            "예산", "재정", "인력", "조직", "제도", "법령", "규정", "기준",
            "홍보", "소통", "대외", "국제", "안전", "보호", "복지", "진흥",
            "확대", "강화", "개선", "혁신", "고도화", "활성화",
        }
        def word_weight(w: str) -> float:
            """단어의 구체성에 따른 가중치 (일반적일수록 낮음)"""
            if w in COMMON_WORDS:
                return 0.15  # 일반 단어: 15%
            if len(w) >= 4:
                return 1.2   # 긴 단어 (구체적): 120%
            return 1.0       # 기본

        # ═══ 1단계: 이산화 (전체 BRM 1차 스캔) ═══
        phase1_scores: dict[str, float] = {}  # 정책분야별 점수
        phase1_hits: dict[str, list] = {}     # 정책분야별 매칭 노드

        for node in self.nodes.values():
            name_clean = node.name.replace("·", " ").replace("/", " ").replace("(", " ").replace(")", " ")
            name_words = {w for w in name_clean.split() if len(w) >= 2}
            if not name_words:
                continue

            # 양방향 매칭 (일반 단어 감쇄 적용)
            forward = sum(word_weight(w) for w in name_words if w in text_lower)
            reverse = sum(word_weight(w) for w in text_words_lower if w in node.name.lower())
            match_count = max(forward, reverse)

            if match_count == 0:
                continue

            score = match_count / max(len(name_words), 1)
            # 경로에서 정책분야 추출
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            top_area = path_parts[0] if path_parts else "기타"

            if top_area not in phase1_scores:
                phase1_scores[top_area] = 0
                phase1_hits[top_area] = []
            phase1_scores[top_area] += score
            phase1_hits[top_area].append((score, node))

        if not phase1_scores:
            return []

        # ═══ 2단계: 추상화 (상위 영역 축소) ═══
        # 정책분야별 누적 점수로 상위 3개 영역 선택
        sorted_areas = sorted(phase1_scores.items(), key=lambda x: x[1], reverse=True)
        top_areas = [area for area, _ in sorted_areas[:3]]

        # 선택된 영역 내에서 정책영역 수준 추상화
        phase2_domains: dict[str, float] = {}  # "정책분야>>정책영역" 별 점수
        for area in top_areas:
            for score, node in phase1_hits.get(area, []):
                path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
                domain_key = ">>".join(path_parts[:2]) if len(path_parts) >= 2 else area
                phase2_domains[domain_key] = phase2_domains.get(domain_key, 0) + score

        sorted_domains = sorted(phase2_domains.items(), key=lambda x: x[1], reverse=True)
        top_domains = [d for d, _ in sorted_domains[:5]]

        # ═══ 3단계: 정밀화 (소기능 레벨 정밀 매칭) ═══
        phase3_candidates: list[tuple[float, Any]] = []

        for node in self.nodes.values():
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            domain_key = ">>".join(path_parts[:2]) if len(path_parts) >= 2 else ""

            # 2단계에서 선택된 영역에 속하는 노드만
            if domain_key not in top_domains:
                continue

            name_clean = node.name.replace("·", " ").replace("/", " ").replace("(", " ").replace(")", " ")
            name_words = [w for w in name_clean.split() if len(w) >= 2]
            if not name_words:
                continue

            # 정밀 매칭: 단어별 가중치 (일반 단어 감쇄)
            score = 0.0
            matched_words = []
            for w in name_words:
                wt = word_weight(w)
                if w in text_lower:
                    score += wt
                    matched_words.append(w)
                elif any(w in tw for tw in text_words_lower):
                    score += wt * 0.5  # 부분 매칭
                    matched_words.append(f"~{w}")

            if score == 0:
                continue

            score = score / len(name_words)
            # 레벨 보너스
            level_bonus = {"소기능": 0.15, "중기능": 0.10, "대기능": 0.05, "정책영역": 0.02, "정책분야": 0.0}
            score += level_bonus.get(node.level, 0)
            # 경로 깊이 보너스 (더 구체적일수록)
            score += len(path_parts) * 0.02

            phase3_candidates.append((score, node, matched_words))

        # 점수순 정렬
        phase3_candidates.sort(key=lambda x: x[0], reverse=True)

        # 중복 경로 제거 + 결과 구성
        seen = set()
        results = []
        for score, node, matched in phase3_candidates:
            path_parts = [p.strip() for p in node.path.split(">>") if p.strip()]
            dedup_key = ">>".join(path_parts[:3]) if len(path_parts) >= 3 else node.path
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            confidence = round(min(score * 1.2, 0.98), 2)

            results.append({
                "node_id": node.id,
                "name": node.name,
                "level": node.level,
                "path": node.path,
                "path_parts": path_parts,
                "confidence": confidence,
                "agencies": node.agencies[:5],
                "matched_keywords": matched[:5],
                "analysis": {
                    "phase1_area": path_parts[0] if path_parts else "",
                    "phase1_area_score": round(phase1_scores.get(path_parts[0] if path_parts else "", 0), 2),
                    "phase2_domain": ">>".join(path_parts[:2]) if len(path_parts) >= 2 else "",
                    "phase3_level": node.level,
                    "phase3_match_ratio": f"{len(matched)}/{len(node.name.split())}",
                },
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
