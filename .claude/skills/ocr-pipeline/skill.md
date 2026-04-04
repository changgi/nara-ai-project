---
name: ocr-pipeline
description: "기록물 OCR 파이프라인 구축 스킬. Qwen3-VL(8B) + PaddleOCR-VL(0.9B) + TrOCR 3모델 앙상블, YOLO-DocLayout 레이아웃 분석, 한자/한글 혼용 문서 처리, OCR 후처리(맞춤법 교정, 구조화), 비전자기록물(식민지기 토지대장, 건축도면, 마이크로필름) 디지털화를 수행한다. 'OCR', '문자인식', '텍스트 추출', '문서 스캔', '디지털화', '한자 인식', '필사체', '레이아웃 분석', '문서 이미지' 관련 작업 시 반드시 이 스킬을 사용할 것."
---

# OCR 파이프라인 구축

국가기록원의 비전자기록물(100만+ 페이지)을 디지털 텍스트로 변환하는 3모델 앙상블 OCR 파이프라인을 구축한다.

## 파이프라인 아키텍처

```
문서 이미지 입력
    ↓
[1] YOLO-DocLayout: 레이아웃 분석 (텍스트/표/그림/서명 영역 분리)
    ↓
[2] 영역별 OCR 모델 라우팅:
    ├── 활자체 → PaddleOCR-VL (0.9B, 배치 처리 50-100p/min/GPU)
    ├── 필사체 → TrOCR (한국어 필사체 특화)
    ├── 한자혼용 → Qwen3-VL (8B, 32개 언어 네이티브)
    └── 표/양식 → PaddleOCR-VL (구조화 모드)
    ↓
[3] 앙상블 투표 (3모델 결과 교차 검증)
    ↓
[4] 후처리:
    ├── 맞춤법 교정 (한국어/한자)
    ├── 구조화 (문단/목록/표 복원)
    └── 메타데이터 추출 (날짜, 기관명, 인명)
    ↓
텍스트 출력 (JSON 구조화)
```

## 3모델 앙상블 구성

### Qwen3-VL (8B) -- 주력 모델
- OCRBench 905점, 32개 언어 네이티브 지원
- 한국어 + 중국어(한자) 동시 처리 가능
- 문맥 기반 OCR로 손상/불명확 문자 추론
- GPU: 1장 (8001 포트 vLLM 서빙)

### PaddleOCR-VL (0.9B) -- 고속 배치 처리
- 50-100 페이지/분/GPU 처리 속도
- 표/양식 구조화 인식 우수
- 경량 모델로 대량 배치에 적합
- GPU: 0.5장 (다른 워크로드와 공유)

### TrOCR -- 필사체 특화
- 한국어 필사체/손글씨 전문
- AI Hub 1,000만+ 옛한글 학습 데이터 활용
- DEEP OCR+ 99% 정확도 기반 전이학습
- GPU: 0.5장

## 레이아웃 분석

```python
# src/ocr/layout/detector.py
from ultralytics import YOLO

class DocumentLayoutDetector:
    """YOLO-DocLayout 기반 문서 레이아웃 분석"""

    CATEGORIES = [
        "text",       # 본문 텍스트
        "title",      # 제목
        "table",      # 표
        "figure",     # 그림/사진
        "signature",  # 서명/도장
        "header",     # 머리글
        "footer",     # 바닥글
        "margin_note" # 난외 주기
    ]

    def detect(self, image_path: str) -> list[LayoutRegion]:
        """레이아웃 영역 검출 및 OCR 모델 라우팅"""
        ...
```

## 문서 유형별 처리 전략

| 문서 유형 | 주요 특성 | 주력 모델 | CER 목표 |
|----------|----------|----------|---------|
| 현대 공문서 (활자) | 표준 한글 활자체 | PaddleOCR-VL | ≤ 3% |
| 일제강점기 문서 | 한자+일본어 혼용 | Qwen3-VL | ≤ 7% |
| 필사 기록물 | 손글씨, 붓글씨 | TrOCR | ≤ 10% |
| 토지대장 | 양식+한자+숫자 | PaddleOCR-VL + Qwen3-VL | ≤ 5% |
| 건축도면 | 기술 도면+텍스트 | Qwen3-VL (비전) | ≤ 8% |
| 마이크로필름 | 저해상도, 노이즈 | 전처리+앙상블 | ≤ 12% |

## 후처리 파이프라인

```python
# src/ocr/postprocess/corrector.py
class OCRPostProcessor:
    """OCR 결과 후처리: 맞춤법 교정, 구조화, 메타데이터 추출"""

    def correct_spelling(self, text: str) -> str:
        """한국어 맞춤법 교정 (기록물 도메인 사전 포함)"""
        ...

    def restore_structure(self, regions: list[LayoutRegion]) -> Document:
        """문단/목록/표 구조 복원"""
        ...

    def extract_metadata(self, text: str) -> dict:
        """NER 기반 메타데이터 추출: 날짜, 기관명, 인명, 지명"""
        ...
```

## 처리량 목표

- 8 B200 GPU 기준: ~1,500-3,800 페이지/시간
- 목표: 100만 페이지를 약 10-28일 내 처리 완료
- 배치 크기 최적화로 GPU 유휴 시간 최소화

## 품질 보증

- 각 문서 유형별 500건 이상의 골드 스탠다드 테스트셋 구축
- CER(Character Error Rate) 자동 측정 + 전문가 표본 검수(5%)
- 신뢰도 점수 0.8 미만 결과는 수동 검수 대기열로 이동
