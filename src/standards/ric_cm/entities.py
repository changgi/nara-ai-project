"""
RiC-CM 1.0 엔티티 정의

국가기록원 지식그래프의 19개 핵심 엔티티를 정의한다.
각 엔티티는 Cloud Spanner Property Graph의 노드 유형에 매핑된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Optional


class EntityType(str, Enum):
    """RiC-CM 1.0 엔티티 유형"""
    # 기록물 엔티티
    RECORD = "Record"                         # 기록물
    RECORD_SET = "RecordSet"                   # 기록물 집합
    RECORD_PART = "RecordPart"                 # 기록물 부분
    INSTANTIATION = "Instantiation"            # 구현체 (물리적 형태)

    # 행위자 엔티티
    AGENT = "Agent"                           # 행위자
    PERSON = "Person"                         # 인물
    CORPORATE_BODY = "CorporateBody"          # 기관/조직
    FAMILY = "Family"                         # 가문
    POSITION = "Position"                     # 직위

    # 활동 엔티티
    ACTIVITY = "Activity"                     # 활동
    MANDATE = "Mandate"                       # 권한/위임
    RULE = "Rule"                             # 규칙/법규

    # 시공간 엔티티
    DATE = "Date"                             # 날짜
    PLACE = "Place"                           # 장소
    EVENT = "Event"                           # 사건

    # 개념 엔티티
    CONCEPT = "Concept"                       # 개념
    RECORD_RESOURCE_HOLDING = "RecordResourceHolding"  # 소장 정보
    DOCUMENTARY_FORM_TYPE = "DocumentaryFormType"      # 문서 유형

    # 한국 확장 엔티티
    BRM_FUNCTION = "BRMFunction"              # BRM 업무기능 (한국 고유)


class RelationType(str, Enum):
    """RiC-CM 1.0 핵심 관계 유형 (142개 중 핵심 30개)"""
    # 기록물 관계
    IS_PART_OF = "isPartOf"
    HAS_PART = "hasPart"
    INCLUDES = "includes"
    IS_INCLUDED_IN = "isIncludedIn"
    IS_ASSOCIATED_WITH = "isAssociatedWith"

    # 생산 관계
    CREATED_BY = "createdBy"
    HAS_CREATOR = "hasCreator"
    ACCUMULATED_BY = "accumulatedBy"
    HAS_ACCUMULATOR = "hasAccumulator"

    # 관리 관계
    MANAGED_BY = "managedBy"
    HAS_MANAGER = "hasManager"
    OWNED_BY = "ownedBy"
    HAS_OWNER = "hasOwner"

    # 시간 관계
    HAS_BEGINNING_DATE = "hasBeginningDate"
    HAS_END_DATE = "hasEndDate"
    HAS_DATE = "hasDate"

    # 공간 관계
    HAS_OR_HAD_LOCATION = "hasOrHadLocation"
    IS_OR_WAS_LOCATED_IN = "isOrWasLocatedIn"

    # 주제 관계
    HAS_SUBJECT = "hasSubject"
    IS_SUBJECT_OF = "isSubjectOf"

    # 활동 관계
    IS_ASSOCIATED_WITH_ACTIVITY = "isAssociatedWithActivity"
    RESULTED_FROM = "resultedFrom"
    RESULTED_IN = "resultedIn"

    # 권한 관계
    IS_REGULATED_BY = "isRegulatedBy"
    REGULATES = "regulates"

    # 한국 확장 관계
    HAS_BRM_CODE = "hasBRMCode"             # BRM 업무기능 연결
    HAS_RETENTION_PERIOD = "hasRetentionPeriod"  # 보존기간
    HAS_SECURITY_LEVEL = "hasSecurityLevel"       # 보안 등급
    TRANSFERRED_TO = "transferredTo"              # 이관
    RECLASSIFIED_AS = "reclassifiedAs"            # 재분류


@dataclass
class RiCEntity:
    """RiC-CM 엔티티 기본 모델"""
    id: str
    entity_type: EntityType
    name: str
    name_kr: str = ""                        # 한국어 이름
    description: str = ""
    identifiers: list[str] = field(default_factory=list)
    date_range: Optional[tuple[str, str]] = None  # (시작일, 종료일) ISO 8601
    properties: dict[str, Any] = field(default_factory=dict)

    def to_spanner_node(self) -> dict[str, Any]:
        """Cloud Spanner Property Graph 노드로 변환"""
        return {
            "id": self.id,
            "type": self.entity_type.value,
            "name": self.name,
            "name_kr": self.name_kr,
            "description": self.description,
            "identifiers": self.identifiers,
            "date_start": self.date_range[0] if self.date_range else None,
            "date_end": self.date_range[1] if self.date_range else None,
            "properties": self.properties,
        }


@dataclass
class RiCRelation:
    """RiC-CM 관계 모델"""
    source_id: str
    target_id: str
    relation_type: RelationType
    description: str = ""
    date_range: Optional[tuple[str, str]] = None
    properties: dict[str, Any] = field(default_factory=dict)
    certainty: float = 1.0  # 0.0~1.0, AI 추출 시 신뢰도

    def to_spanner_edge(self) -> dict[str, Any]:
        """Cloud Spanner Property Graph 엣지로 변환"""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.relation_type.value,
            "description": self.description,
            "date_start": self.date_range[0] if self.date_range else None,
            "date_end": self.date_range[1] if self.date_range else None,
            "certainty": self.certainty,
            "properties": self.properties,
        }


# 한국 공공기록물법 기반 BRM 업무기능 분류 체계 (최상위)
BRM_TOP_LEVEL = {
    "A": "일반공공행정",
    "B": "공공질서및안전",
    "C": "통일외교",
    "D": "국방",
    "E": "교육",
    "F": "문화및관광",
    "G": "환경",
    "H": "사회복지",
    "I": "보건",
    "J": "농림해양수산",
    "K": "산업중소기업에너지",
    "L": "교통및물류",
    "M": "통신",
    "N": "국토및지역개발",
    "O": "과학기술",
    "P": "재정금융",
}
