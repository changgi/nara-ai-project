"""
OCR 후처리: 맞춤법 교정, 구조화, 메타데이터 추출

OCR 앙상블 결과를 정제하여 검색 가능한 텍스트로 변환한다.
기록물 도메인 사전(기관명, 법률 용어, 역사적 인명/지명)을 활용한다.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("nara-ai.ocr.postprocess")


@dataclass
class CorrectionResult:
    """교정 결과"""
    original: str
    corrected: str
    corrections: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class StructuredDocument:
    """구조화된 문서"""
    title: str = ""
    sections: list[dict[str, Any]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


# 기록물 도메인 사전 (흔한 OCR 오류 패턴)
DOMAIN_CORRECTIONS: dict[str, str] = {
    "행정안전뷰": "행정안전부",
    "국가기록완": "국가기록원",
    "공공기록뭄": "공공기록물",
    "대한밍국": "대한민국",
    "보존기갼": "보존기간",
    "비밀해재": "비밀해제",
    "기록관리기괸": "기록관리기관",
    "전자기록뭄": "전자기록물",
    "메타테이터": "메타데이터",
}

# 한자 → 한글 대응표 (자주 등장하는 기록물 용어)
HANJA_MAPPING: dict[str, str] = {
    "記錄": "기록",
    "文書": "문서",
    "保存": "보존",
    "機關": "기관",
    "行政": "행정",
    "國家": "국가",
    "政府": "정부",
    "法律": "법률",
    "公開": "공개",
    "秘密": "비밀",
    "檢索": "검색",
    "分類": "분류",
    "廢棄": "폐기",
    "移管": "이관",
}


class OCRPostProcessor:
    """OCR 후처리 파이프라인"""

    def __init__(self):
        self.domain_dict = DOMAIN_CORRECTIONS
        self.hanja_dict = HANJA_MAPPING

    def correct(self, text: str) -> CorrectionResult:
        """OCR 텍스트 교정 (도메인 사전 + 규칙 기반)"""
        corrected = text
        corrections: list[dict[str, str]] = []

        # 1. 도메인 사전 교정
        for wrong, right in self.domain_dict.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
                corrections.append({"type": "domain", "from": wrong, "to": right})

        # 2. 한자 병기 처리
        for hanja, hangul in self.hanja_dict.items():
            if hanja in corrected:
                # 한자 뒤에 한글 병기 추가 (원본 한자 보존)
                corrected = corrected.replace(hanja, f"{hanja}({hangul})")
                corrections.append({"type": "hanja", "from": hanja, "to": f"{hanja}({hangul})"})

        # 3. 공통 OCR 오류 패턴 교정
        corrected = self._fix_common_errors(corrected, corrections)

        # 4. 불필요한 공백/줄바꿈 정리
        corrected = self._normalize_whitespace(corrected)

        confidence = 1.0 - (len(corrections) * 0.02)  # 교정 많을수록 신뢰도 감소
        confidence = max(0.5, min(1.0, confidence))

        return CorrectionResult(
            original=text,
            corrected=corrected,
            corrections=corrections,
            confidence=confidence,
        )

    def _fix_common_errors(self, text: str, corrections: list[dict[str, str]]) -> str:
        """공통 OCR 오류 패턴 교정"""
        # 숫자 오류: O→0, l→1, I→1
        patterns = [
            (r'(\d)O(\d)', r'\g<1>0\g<2>'),  # 1O2 → 102
            (r'(\d)l(\d)', r'\g<1>1\g<2>'),  # 1l2 → 112
        ]
        for pattern, replacement in patterns:
            new_text = re.sub(pattern, replacement, text)
            if new_text != text:
                corrections.append({"type": "pattern", "from": "숫자 오류", "to": "교정"})
                text = new_text

        # 날짜 형식 정규화: 2024. 1. 1 → 2024-01-01
        text = re.sub(
            r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})',
            lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
            text,
        )

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """공백/줄바꿈 정규화"""
        text = re.sub(r' {3,}', '  ', text)       # 3개 이상 공백 → 2개
        text = re.sub(r'\n{4,}', '\n\n\n', text)  # 4개 이상 줄바꿈 → 3개
        return text.strip()

    def structurize(self, text: str, regions: list[dict[str, Any]] | None = None) -> StructuredDocument:
        """텍스트를 구조화된 문서로 변환"""
        doc = StructuredDocument()

        lines = text.split('\n')
        current_section: dict[str, Any] = {"heading": "", "content": []}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 제목 추출 (첫 번째 큰 텍스트 블록)
            if not doc.title and len(stripped) < 100:
                doc.title = stripped
                continue

            # 섹션 구분 (번호 매기기 패턴)
            if re.match(r'^[1-9IⅠⅡⅢⅣⅤㄱ-ㅎ가-힣]\s*[\.·)]\s*', stripped):
                if current_section["content"]:
                    doc.sections.append(current_section)
                current_section = {"heading": stripped, "content": []}
            else:
                current_section["content"].append(stripped)

        if current_section["content"]:
            doc.sections.append(current_section)

        return doc

    def extract_dates(self, text: str) -> list[str]:
        """텍스트에서 날짜 추출 (다양한 형식)"""
        patterns = [
            r'\d{4}-\d{2}-\d{2}',           # 2024-01-01
            r'\d{4}\.\s?\d{1,2}\.\s?\d{1,2}', # 2024. 1. 1
            r'\d{4}년\s?\d{1,2}월\s?\d{1,2}일', # 2024년 1월 1일
            r'(昭和|大正|明治)\s?\d{1,2}年',  # 일제강점기 일본 연호
        ]
        dates: list[str] = []
        for pattern in patterns:
            dates.extend(re.findall(pattern, text))
        return dates

    def extract_agencies(self, text: str) -> list[str]:
        """텍스트에서 기관명 추출"""
        # 기관명 패턴: ~부, ~처, ~청, ~원, ~위원회, ~공단
        pattern = r'[가-힣]{2,10}(?:부|처|청|원|위원회|공단|연구소|연구원|대학교)'
        return list(set(re.findall(pattern, text)))
