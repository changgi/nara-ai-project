# NARA-AI 기술설계서 (TDD)

## 1. 시스템 개요

### 1.1 목적
AI 기반 국가기록물 지능형 검색/분류/활용 체계를 구축하여
290만 전자기록물과 100만 페이지 비전자기록물에 대한
국민 접근성을 혁신하고, 기록물 관리 업무를 자동화한다.

### 1.2 범위
- 기록물 자동 분류 (BRM 업무기능 매핑)
- 메타데이터 자동 생성 (제목, 요약, 키워드, NER)
- OCR 디지털화 (3모델 앙상블, 7종 문서)
- 비밀해제 심사 지원 (PII 탐지, HITL)
- 시맨틱 검색 (3계층 하이브리드 RAG)
- 지식그래프 (RiC-CM 1.0, Cloud Spanner)

## 2. 아키텍처

### 2.1 6계층 스택

| 계층 | 구성 |
|------|------|
| L6 사용자 | 국민 검색 / 전문가 도구 / 관리 대시보드 |
| L5 오케스트레이터 | LangGraph StateGraph + HITL 4개 + 감사추적 |
| L4 MCP 서버 | 5서버 47도구 (OAuth 2.1, Zod 검증) |
| L3 데이터 | Milvus 2.6 + Cloud Spanner + NVMe |
| L2 AI 추론 | vLLM x2 + BGE-M3-Korean 임베딩 |
| L1 GPU 인프라 | DGX B200 x16-32, NVLink 5.0, 에어갭 |

### 2.2 11단계 처리 파이프라인

```
ingest → layout → ocr → ocr_post → classify → metadata
    → redaction[HITL] → embedding → graph → quality → security
```

### 2.3 데이터 흐름

```
RAMP(48부처) ──→ 수집(ingest) ──→ 레이아웃 분석
                                      ↓
파일시스템 ────→ OCR 앙상블 ──→ 후처리(교정/구조화)
                                      ↓
                               분류(BRM) + 메타데이터
                                      ↓
                               비밀해제 심사 [HITL 필수]
                                      ↓
                               임베딩(1024d) + 그래프(RiC-CM)
                                      ↓
                               품질 검증 + 보안 스캔
                                      ↓
                               Milvus 인덱싱 ──→ 국민 검색
```

## 3. 모듈 상세

### 3.1 AI 에이전트

| 에이전트 | 모델 | 성능 목표 |
|---------|------|----------|
| ClassifierAgent | EXAONE 3.5 SFT | F1 ≥ 0.92 |
| MetadataAgent | EXAONE 3.5 SFT | ROUGE-1 ≥ 0.85 |
| RedactionAgent | EXAONE 3.5 SFT | PII Precision ≥ 0.95 |
| SearchAgent | BGE-M3-Korean | Recall@10 ≥ 0.90 |
| QualityAgent | 규칙 기반 | 6항목 검증 |
| Orchestrator | LangGraph | HITL 조건부 분기 |

### 3.2 MCP 서버

| 서버 | 포트 | 도구 | 연동 대상 |
|------|------|------|----------|
| mcp-archive | 3001 | 10 | ARAM-ADK 42 Go 에이전트 |
| mcp-iarna | 3002 | 12 | Cloud Spanner 지식그래프 |
| mcp-nara | 3003 | 12 | US NARA, UK TNA, DPLA |
| mcp-law | 3004 | 6 | 공공기록물법 법률 자문 |
| mcp-ramp | 3005 | 7 | RAMP 48개 중앙부처 |

### 3.3 OCR 앙상블

| 모델 | 크기 | 강점 | 대상 |
|------|------|------|------|
| Qwen3-VL | 8B | 한자+한국어, 문맥 OCR | 한자혼용, 건축도면 |
| PaddleOCR-VL | 0.9B | 고속 배치, 표 구조화 | 활자체, 양식 |
| TrOCR | - | 필사체 특화 | 손글씨, 난외주기 |

## 4. 보안 설계

### 4.1 N2SF "민감" 등급
- 물리적 에어갭 (Docker internal network, K8s NetworkPolicy)
- 외부 API 호출 불가, 모든 모델/데이터 사전 로드

### 4.2 인증/인가
- OAuth 2.1 JWT (HS256, 에어갭 대칭키)
- RBAC: admin > archivist > researcher > public
- 보안등급별 접근 제어 (public/restricted/secret/top_secret)

### 4.3 PII 보호
- 6종 PII 자동 탐지 (주민번호, 전화, 이메일, 여권, 운전면허, 계좌)
- SHA-256 기반 비가역 가명처리 (개인정보보호법 제28조의2)

### 4.4 감사추적
- 모든 AI 의사결정에 필수 필드 기록
- user_id, agent_name, input_hash, timestamp, confidence, reasoning, hitl_required
- 10년(3,650일) 보존 (공공기록물법)

## 5. 인프라

### 5.1 GPU 프로파일

| 구성 | GPU | 용도 |
|------|-----|------|
| 8 GPU (MVP) | B200 x8 | SFT 학습 + 추론 + OCR |
| 16 GPU (표준) | B200 x16 | 병렬 학습 + 멀티모델 서빙 |
| 32 GPU (풀) | B200 x32 | 파운데이션 모델 CPT + 대규모 OCR |

### 5.2 모니터링
- Prometheus: GPU 사용률, 추론 레이턴시, MCP 서버 상태
- Grafana: 7패널 시스템 대시보드
- 알림 6개: GPU OOM, 추론 P99>5s, MCP 다운, Milvus 다운, 검색 P99>2s

## 6. 법률 준수

| 법률 | 시행일 | 핵심 요구사항 |
|------|--------|-------------|
| AI 기본법 | 2026.1 | HITL, 감사추적, 설명가능성, 편향방지 |
| ISMS-P | 2027.7 | 101개 항목, 접근통제, 암호화, PII |
| N2SF | 적용 중 | 에어갭, 데이터 주권, CSAP |
| 공공기록물법 | 적용 중 | 제6/33/34/35/38조, 2인 승인 |
