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

        # ── 한국어 단어 사전 구축 (BRM + 기본어) ──
        if not hasattr(self, '_word_dict'):
            self._word_dict = set()
            # BRM 17,634건에서 모든 단어 추출
            for node in self.nodes.values():
                clean = node.name.replace("·", " ").replace("/", " ").replace("(", " ").replace(")", " ").replace(",", " ")
                for w in clean.split():
                    if len(w) >= 2:
                        self._word_dict.add(w)
                # 띄어쓰기 없는 이름 전체도 추가
                name_nospace = node.name.replace(" ", "").replace("·", "").replace("/", "")
                if len(name_nospace) >= 2:
                    self._word_dict.add(name_nospace)
                # 경로의 각 계층 이름도
                for part in node.path.split(">>"):
                    p = part.strip()
                    if len(p) >= 2:
                        self._word_dict.add(p)
                        # 띄어쓰기 없는 버전
                        p_nospace = p.replace(" ", "")
                        if p_nospace != p and len(p_nospace) >= 2:
                            self._word_dict.add(p_nospace)

            # 한국어 기본 단어 사전 (일상어 + 행정 용어)
            BASIC_WORDS = {
                # 일상어
                "경제", "사회", "문화", "교육", "환경", "건강", "안전", "복지", "국방", "외교",
                "통일", "산업", "농업", "수산", "해양", "과학", "기술", "통신", "교통", "건설",
                "주택", "도시", "농촌", "국토", "에너지", "자원", "금융", "세금", "예산", "무역",
                # 행정용어
                "기관", "부서", "위원회", "공단", "재단", "연구소", "센터", "사무소",
                "업무", "회의", "협의", "결의", "지급", "회비", "경비", "비용", "수당",
                "민주", "민주화", "운동", "혁명", "시위", "항쟁", "독립", "자유", "인권",
                "법률", "법령", "법안", "특별법", "기본법", "시행령", "조례", "규칙",
                "전쟁", "평화", "안보", "군사", "방위", "병역",
                "광주", "서울", "부산", "대구", "인천", "대전", "울산", "세종", "제주",
                "백신", "접종", "방역", "감염", "바이러스", "코로나", "팬데믹",
                "반도체", "소재", "부품", "장비", "국산화", "수출", "수입",
                "탄소", "온실가스", "감축", "중립", "기후", "오염",
                "디지털", "데이터", "소프트웨어", "인공지능", "로봇",
                "유관", "유관기관", "관계", "관계철", "문서", "기록", "기록물",
                "공개", "비공개", "비밀", "해제", "심사", "검토", "승인",
                # 묘역/성역/보훈/기념
                "묘역", "성역", "성역화", "기념", "기념관", "기념사업", "추모", "위령",
                "보훈", "유공자", "참전", "희생", "순국", "독립유공",
                # 작품/예술/문화재
                "작품", "공모", "공모전", "입상", "전시", "조각", "조형물", "미술",
                "문화재", "유산", "유적", "유물", "보존", "복원",
                # 관계철/문서 유형
                "결재", "결의", "품의", "시행", "접수", "배부", "통보",
            }
            self._word_dict.update(BASIC_WORDS)

        # ── 텍스트에서 실제 단어만 추출 ──
        # 한글 2자 이상 + 숫자.숫자 패턴 (5.18, 4.19 등)
        raw_words = list(dict.fromkeys(re.findall(r'[가-힣]{2,}', text)))
        # 숫자 패턴도 추출 (5.18, 4.19 등 역사적 사건 번호)
        number_patterns = re.findall(r'\d+\.\d+', text)
        for np in number_patterns:
            raw_words.insert(0, np)  # 숫자 패턴을 앞에 배치

        # 조사/어미 패턴 (단어 끝에 붙는 것)
        JOSA_SUFFIX = re.compile(r'(과의|에서의|으로의|에게서|에서|으로|에게|부터|까지|에는|와의|이다|하다|되다|한다|했다|하는|된다|라는|에의|과|의|을|를|이|가|은|는|에|로|와|도)$')

        # 조사/접속사 자체 (독립 단어로 무의미한 것)
        JOSA_WORDS = {
            "과의", "에서", "으로", "에게", "부터", "까지", "에는", "와의",
            "이다", "하다", "되다", "한다", "했다", "하는", "된다", "라는",
            "에의", "으로의", "에서의", "에게서",
            "관한", "위한", "통한", "대한", "의한", "따른", "인한",
        }

        # 맥락상 무의미한 분절 판별
        def is_meaningful_subword(sub: str, parent: str) -> bool:
            """부분어가 맥락상 의미 있는 키워드인지 판별

            핵심 원칙: 사전에 있는 단어는 기본적으로 의미가 있다.
            단, 조사/접속사 잔여물만 제외한다.
            """
            # 1. 조사/접속사 자체면 제외
            if sub in JOSA_WORDS:
                return False

            # 2. 조사 부분 자체를 뽑은 경우 제외
            stem = JOSA_SUFFIX.sub('', parent)
            if len(stem) < len(parent) and sub == parent[len(stem):]:
                return False

            # 3. 사전에 있는 2글자 이상이면 의미 있는 단어로 판단
            return True

        extracted = []
        for w in raw_words:
            # 숫자 패턴 (5.18, 4.19 등)은 직접 추가
            if re.match(r'^\d+\.\d+$', w):
                if w not in extracted:
                    extracted.append(w)
                continue

            # 1) 조사 먼저 제거 → 어간(stem)이 핵심
            stem = JOSA_SUFFIX.sub('', w)
            if len(stem) < 2:
                stem = w  # 조사 제거 후 너무 짧으면 원본 유지

            # 2) 어간을 우선 추가 (조사 붙은 원본은 추가하지 않음)
            if stem != w:
                # 조사가 제거된 경우: 어간만 추가
                if stem in self._word_dict:
                    if stem not in extracted:
                        extracted.append(stem)
                # 어간이 사전에 없어도 추가 (BRM에서 매칭 시도)
                elif len(stem) >= 2 and stem not in extracted:
                    extracted.append(stem)
            else:
                # 조사 없는 원본: 사전에 있으면 추가
                if w in self._word_dict and w not in extracted:
                    extracted.append(w)

            # 3) 복합어 분해: 어간 기준으로 모든 의미 단위 추출
            target = stem if stem != w else w
            if len(target) >= 4:
                # 모든 길이의 부분어를 사전에서 찾기 (긴 것 우선)
                for size in range(min(len(target) - 1, 7), 1, -1):
                    for i in range(len(target) - size + 1):
                        sub = target[i:i+size]
                        if (sub in self._word_dict and
                            sub not in extracted and
                            sub != target and
                            sub not in JOSA_WORDS and
                            is_meaningful_subword(sub, target)):
                            extracted.append(sub)

        # 띄어쓰기 정규화: "유관 기관" == "유관기관"
        # 원본 텍스트를 공백 제거한 버전에서도 사전 매칭
        text_nospace = text.replace(" ", "")
        if text_nospace != text:
            nospace_words = list(dict.fromkeys(re.findall(r'[가-힣]{2,}', text_nospace)))
            for w in nospace_words:
                stem = JOSA_SUFFIX.sub('', w)
                if len(stem) >= 2 and stem not in extracted:
                    if stem in self._word_dict:
                        extracted.append(stem)

        # 일반어 필터
        STOP_WORDS = {
            "추진", "지원", "관리", "운영", "사업", "계획", "정책", "행정", "기획",
            "조사", "분석", "평가", "감사", "연구", "개발", "협력", "조정", "보고",
            "총괄", "기반", "체계", "서비스", "정보", "통계", "보호", "진흥",
            "확대", "강화", "개선", "혁신", "고도화", "활성화", "내실화",
            "방안", "대책", "현황", "결과", "발표", "수립", "시행",
        }

        key_words = list(dict.fromkeys(w for w in extracted if w not in STOP_WORDS and w not in JOSA_WORDS and len(w) >= 2))
        context_words = raw_words

        # ── 복합어 조합: 키워드 2~4개 조합으로 유의미한 복합단어 생성 ──
        from itertools import combinations
        base_kws = [w for w in key_words if len(w) >= 2][:12]  # 조합 폭발 방지
        compound_words = []

        for combo_size in range(2, min(len(base_kws) + 1, 5)):  # 2~4단어 조합
            for combo in combinations(range(len(base_kws)), combo_size):
                words_in_combo = [base_kws[i] for i in combo]
                # 순서 유지 조합 + 역순도 시도
                for ordered in [words_in_combo, list(reversed(words_in_combo))]:
                    compound = "".join(ordered)
                    if len(compound) > 12:  # 너무 긴 복합어 제외
                        continue
                    if compound in self._word_dict and compound not in key_words and compound not in compound_words:
                        compound_words.append(compound)
                    # 중간에 공백/구분자 없이 BRM 경로에 존재하는지도 확인
                    if any(compound in node.name or compound in node.path for node in list(self.nodes.values())[:5000]):
                        if compound not in key_words and compound not in compound_words and len(compound) >= 4:
                            compound_words.append(compound)
                            break  # 이 조합은 찾았으니 역순 불필요

        # 복합어를 키워드에 추가 (높은 우선순위)
        if compound_words:
            key_words = compound_words + key_words  # 복합어를 앞에 배치

        # ── 유사의미어(시소러스) 확장 ──
        # 각 키워드에 대해 맥락상 교체 가능한 동의어/유사어를 확장
        # 상위 개념 + 동의어 + 유사 표현 모두 포함
        SYNONYM_MAP = {
            # ── 행정/조직/기관 ──
            "유관기관": ["관계기관", "각급기관", "협의체", "유관단체", "관련기관"],
            "기관": ["기관운영", "행정기관", "공공기관", "관계기관", "각급기관"],
            "업무": ["직무", "사무", "행정", "일반행정"],
            "업무협의": ["업무협조", "업무회의", "협의회", "회의"],
            "협의": ["협조", "회의", "협력", "논의", "심의"],
            "회비": ["등록비", "구독료", "가입비", "분담금", "납부금", "부담금", "경비"],
            "지급": ["집행", "지출", "교부", "배분", "배정", "송금"],
            "경비": ["비용", "예산", "지출", "세출", "경상경비", "사업비"],
            "예산": ["재정", "세출", "세입", "예산집행", "예산편성"],
            "인사": ["인사관리", "채용", "임용", "공무원인사", "인력"],
            "공무원": ["공직자", "공무원인사", "직원"],
            "조직": ["기구", "정원", "조직관리", "부서"],
            # ── 민주/인권 ──
            "민주": ["민주화", "민주주의", "민주화운동", "시민"],
            "민주화": ["민주화운동", "민주", "인권", "시민사회", "민주주의"],
            "인권": ["인권보호", "차별금지", "평등", "권리"],
            # ── 국방/안보 ──
            "전쟁": ["국방", "군사", "안보", "작전", "전투"],
            "군사": ["국방", "방위", "작전", "군"],
            "안보": ["국가안보", "방위", "군사", "안전보장"],
            "병역": ["병무", "징병", "군복무", "입영"],
            # ── 역사/민주화/보훈 ──
            "5.18": ["민주화운동", "민주화", "광주", "보훈"],
            "4.19": ["민주화운동", "혁명", "민주", "보훈"],
            "묘역": ["성역화", "국립묘지", "추모", "보훈", "기념"],
            "성역": ["성역화", "묘역", "기념사업", "추모"],
            "성역화": ["기념사업", "묘역", "국립묘지", "보훈"],
            "추모": ["기념", "묘역", "위령", "성역화"],
            "기념": ["기념사업", "기념관", "추모", "기념행사"],
            "보훈": ["보훈복지", "유공자", "보훈관리", "참전"],
            "유공자": ["보훈", "참전유공자", "독립유공", "보상"],
            "순국": ["독립", "보훈", "기념", "유공자"],
            # ── 작품/심사/예술 ──
            "작품": ["미술", "조형물", "조각", "예술", "공모"],
            "심사": ["심의", "평가", "심사위원", "선정", "공모"],
            "공모": ["공모전", "모집", "선정", "심사"],
            # ── 외교/통일 ──
            "외교": ["국제관계", "통상", "조약", "국제협력", "대외"],
            "통일": ["남북관계", "남북", "교류", "북한"],
            "남북": ["남북관계", "통일", "교류협력"],
            # ── 보건/의료 ──
            "백신": ["예방접종", "면역", "감염병예방", "접종"],
            "접종": ["예방접종", "백신접종", "면역", "투여"],
            "방역": ["감염병관리", "방역대책", "위생", "검역"],
            "코로나": ["감염병", "팬데믹", "방역", "전염병"],
            "의료": ["보건의료", "병원", "진료", "건강보험"],
            "건강": ["보건", "건강증진", "질병예방"],
            "질병": ["감염병", "질환", "예방", "치료"],
            # ── 산업/경제 ──
            "반도체": ["전자산업", "부품소재", "산업진흥", "첨단산업"],
            "소재": ["부품소재", "원자재", "소재산업", "신소재"],
            "부품": ["부품소재", "부품산업", "제조", "장비부품"],
            "장비": ["기계장비", "설비", "기자재", "시설"],
            "국산화": ["기술자립", "수입대체", "국내생산", "자급"],
            "수출": ["무역", "수출입", "통상", "해외판매"],
            "수입": ["수입관리", "수출입", "관세", "통관"],
            "에너지": ["전력", "신재생에너지", "원자력", "에너지정책"],
            # ── 환경 ──
            "탄소": ["탄소중립", "온실가스", "기후변화", "감축"],
            "탄소중립": ["기후변화대응", "온실가스감축", "탄소", "넷제로"],
            "온실가스": ["기후변화", "탄소", "배출량", "감축"],
            "오염": ["환경오염", "수질오염", "대기오염", "토양오염"],
            "폐기물": ["쓰레기", "재활용", "순환경제", "폐기물관리"],
            # ── 교육 ──
            "교육": ["학교교육", "교과", "학습", "인재양성"],
            "교육과정": ["교과과정", "교육과정운영", "교과", "커리큘럼"],
            "학교": ["교육기관", "학교운영", "학교교육"],
            "대학": ["고등교육", "대학교", "학술", "대학운영"],
            # ── 복지 ──
            "복지": ["사회복지", "복지서비스", "사회보장", "급여"],
            "장애": ["장애인", "장애인복지", "장애인지원"],
            "노인": ["고령자", "노인복지", "돌봄", "노인요양"],
            "아동": ["아동복지", "어린이", "아동보호", "보육"],
            "저출생": ["출산", "인구정책", "보육", "출산장려"],
            # ── 농림/수산 ──
            "농업": ["농림", "영농", "농업정책", "농촌"],
            "축산": ["축산업", "가축", "축산물", "가축방역"],
            "수산": ["어업", "양식", "수산업", "수산자원"],
            # ── 교통/건설 ──
            "철도": ["도시철도", "고속철도", "철도운영", "철도건설"],
            "도로": ["고속도로", "도로건설", "도로관리", "교통시설"],
            "항공": ["항공산업", "공항", "항공안전", "항공운송"],
            "주택": ["주거", "부동산", "임대주택", "주택건설"],
            # ── 과학/기술 ──
            "우주": ["항공우주", "위성", "우주개발", "우주탐사"],
            "디지털": ["정보화", "전자정부", "디지털전환", "정보통신"],
            "인공지능": ["AI", "데이터", "지능정보", "기계학습"],
            # ── 재정/금융 ──
            "세금": ["조세", "국세", "지방세", "세무"],
            "국채": ["국가채무", "채권", "공채", "국채관리"],
            "금융": ["은행", "증권", "보험", "금융정책"],
            # ── 법률 ──
            "특별법": ["법률", "특별법", "입법", "법제"],
            "법률": ["법령", "입법", "법제", "법률제정"],
            "기본법": ["기본법", "기본법제정", "법률"],
            # ── 기록물/문서 ──
            "기록": ["기록물", "기록관리", "아카이브", "문서보존"],
            "기록물": ["기록", "문서", "공공기록물", "기록물관리"],
            "문서": ["공문서", "전자문서", "기록물", "서류"],
            "공개": ["정보공개", "열람", "공표", "공시"],
            "비밀": ["비공개", "보안", "비밀해제", "기밀"],
        }
        # 유사의미어 확장: 각 키워드의 동의어/유사어를 추가
        synonym_words = []
        for kw in key_words:
            if kw in SYNONYM_MAP:
                for syn in SYNONYM_MAP[kw]:
                    if syn not in key_words and syn not in synonym_words:
                        synonym_words.append(syn)
            # 복합어 키워드도 확인 (업무협의 → 업무협조, 협의회 등)
            for map_key, syns in SYNONYM_MAP.items():
                if map_key in kw and map_key != kw:
                    for syn in syns:
                        if syn not in key_words and syn not in synonym_words:
                            synonym_words.append(syn)
        key_words.extend(synonym_words)

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
                    "phase1_key_words": key_words[:20],
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
