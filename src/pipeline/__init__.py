"""
NARA-AI 11단계 처리 파이프라인
국가기록물 AI 기반 지능형 검색·분류·활용 체계

파이프라인 단계:
1. ingest       - 기록물 수집 (RAMP/파일시스템)
2. layout       - 레이아웃 분석 (YOLO-DocLayout)
3. ocr          - OCR 앙상블 (Qwen3-VL + PaddleOCR-VL + TrOCR)
4. ocr_post     - OCR 후처리 (맞춤법 교정, 구조화)
5. classify     - 기록물 분류 (BRM 업무기능 매핑)
6. metadata     - 메타데이터 자동 생성
7. redaction    - 비밀해제 심사 지원
8. embedding    - 벡터 임베딩 생성
9. graph        - 지식그래프 노드/관계 생성
10. quality     - 품질 검증 게이트
11. security    - 보안 스캐닝 (PII, 취약점)
"""

__version__ = "1.0.0"
