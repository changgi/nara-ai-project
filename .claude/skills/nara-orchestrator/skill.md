---
name: nara-orchestrator
description: "NARA-AI 프로젝트 전체 빌드 오케스트레이터. 5명의 에이전트 팀(project-lead, ml-engineer, backend-engineer, infra-engineer, qa-engineer)을 조율하여 국가기록원 AI 시스템을 구축한다. 'NARA-AI 구축', '프로젝트 실행', '전체 빌드', '시스템 구축', '하네스 실행', '에이전트 팀 실행', '국가기록원 프로젝트' 관련 작업 시 반드시 이 스킬을 사용할 것. 개별 모듈(OCR, 검색, MCP 등)만 작업할 때는 해당 전문 스킬을 직접 사용하라."
---

# NARA-AI 프로젝트 오케스트레이터

국가기록원 AI 기반 지능형 기록물 검색/분류/활용 체계를 구축하는 에이전트 팀 오케스트레이터이다.

**실행 모드**: 에이전트 팀 (Pipeline + Fan-out/Fan-in 하이브리드)

## 프로젝트 비전

> "국민을 위한, 국민에 의한, 국민에게 혜택이 돌아가는" AI 기록물 관리 시스템
>
> 290만 전자기록물과 100만 페이지 비전자기록물에 AI를 적용하여,
> 국민이 국가기록에 자연어로 접근하고, 기록물 전문가의 업무를 10배 효율화한다.

## 팀 구성

| 에이전트 | subagent_type | 역할 |
|---------|--------------|------|
| project-lead | general-purpose | 아키텍처 설계, 통합 조율, 산출물 종합 |
| ml-engineer | general-purpose | 모델 학습, OCR, 임베딩, 추론 서빙 |
| backend-engineer | general-purpose | MCP 서버, RAG, 벡터DB, LangGraph |
| infra-engineer | general-purpose | Docker, K8s, 모니터링, 보안 인프라 |
| qa-engineer | general-purpose | 통합 검증, 경계면 테스트, 컴플라이언스 |

## Phase 구조

```
Phase 1: 기반 구축 (infra-engineer 주도)
    ↓
Phase 2: 코어 모듈 병렬 개발 (Fan-out)
    ├── ml-engineer: 모델 학습 + OCR 파이프라인
    ├── backend-engineer: MCP 서버 + RAG + 벡터DB
    └── infra-engineer: Docker + 모니터링
    ↓ (qa-engineer: 각 모듈 완성 시 점진적 검증)
Phase 3: 통합 (project-lead 주도)
    ↓
Phase 4: 최종 검증 (qa-engineer 주도)
```

## Phase 1: 기반 구축

**리더**: project-lead
**참여**: infra-engineer, backend-engineer

1. `_workspace/` 디렉토리 생성
2. 프로젝트 구조 초기화 (`harness init` 참조)
3. Docker Compose 환경 구성 (Milvus, 모니터링)
4. `.env` 설정 및 의존성 설치
5. 기존 코드베이스 분석 (harness.ts, CLAUDE.md, config/)

**산출물:**
- `_workspace/00_architecture.md`: 아키텍처 설계서
- `_workspace/01_infra_setup.md`: 인프라 구성 보고서
- Docker Compose 파일, K8s 매니페스트, 환경 설정

## Phase 2: 코어 모듈 병렬 개발 (Fan-out)

**실행 방식**: 3명이 병렬로 작업, qa-engineer가 각 모듈 완성 시 점진적 검증

### Track A: ml-engineer
1. 학습 설정 파일 생성 (`config/training/`)
2. SFT 학습 파이프라인 구현 (`src/pipeline/train/`)
3. OCR 3모델 앙상블 파이프라인 (`src/ocr/`)
4. 임베딩 서버 구현 (`src/search/embedding/`)
5. vLLM 추론 서빙 설정 (`src/pipeline/serve/`)

### Track B: backend-engineer
1. MCP 서버 공통 프레임워크 (`src/mcp-servers/common/`)
2. mcp-archive 서버 (ARAM-ADK 래핑)
3. mcp-iarna 서버 (지식그래프)
4. mcp-law + mcp-ramp 서버
5. Milvus 스키마 + RAG 파이프라인 (`src/search/`)
6. LangGraph 오케스트레이터 (`src/agents/orchestrator/`)

### Track C: infra-engineer
1. vLLM 멀티모델 서빙 Docker 구성
2. GPU 리소스 할당 프로파일 (8/16/32 GPU)
3. Prometheus + Grafana 대시보드
4. 보안 스캐닝 파이프라인 (CodeQL, Semgrep, Trivy, TruffleHog)
5. 배포 스크립트 및 CI/CD 파이프라인

### Track QA: qa-engineer (점진적 검증)
- Track A 모듈 완성 → 모델 출력 형식 검증
- Track B 모듈 완성 → MCP 스키마 ↔ LangGraph 경계면 검증
- Track C 모듈 완성 → 인프라 설정 정합성 검증

**산출물:**
- `_workspace/02_model_eval_report.md`
- `_workspace/03_backend_report.md`
- `_workspace/04_infra_report.md`
- `_workspace/05_qa_report.md`
- 전체 소스 코드 (`src/`, `config/`, `scripts/`, `infra/`)

## Phase 3: 통합

**리더**: project-lead
**참여**: 전원

1. MCP 서버 ↔ LangGraph 오케스트레이터 연결
2. 모델 추론 ↔ 벡터DB ↔ RAG 파이프라인 연결
3. OCR 파이프라인 ↔ 메타데이터 생성 ↔ 벡터 인덱싱 연결
4. HITL 게이트 작동 확인
5. 11단계 처리 파이프라인 엔드투엔드 테스트

## Phase 4: 최종 검증

**리더**: qa-engineer
**참여**: 전원

1. 경계면 교차 비교 (4대 검증 영역)
2. 성능 벤치마크 (F1, CER, Recall@10, 레이턴시)
3. ISMS-P 컴플라이언스 감사 (101개 항목)
4. AI 기본법 위험평가 및 투명성 검증
5. N2SF 보안 등급 확인
6. 공공기록물법 적합성 검증

**산출물:**
- `_workspace/06_compliance_report.md`
- `_workspace/99_integration_report.md`

## 데이터 전달 프로토콜

| 전략 | 용도 |
|------|------|
| 태스크 기반 (TaskCreate/TaskUpdate) | 작업 할당, 진행상황 추적, 의존성 관리 |
| 파일 기반 (_workspace/) | 대용량 산출물, 코드, 설정 파일, 보고서 |
| 메시지 기반 (SendMessage) | 실시간 질의응답, 기술 이슈 논의, 경계면 버그 통보 |

**파일명 컨벤션**: `{phase}_{agent}_{artifact}.{ext}`
- 예: `01_infra_docker_compose.yml`, `02_ml_sft_config.yaml`

## 에러 핸들링

| 상황 | 대응 |
|------|------|
| 팀원 1명 실패 | 1회 재시도 → 실패 시 리더가 직접 수행 또는 다른 팀원 재배정 |
| 다수 실패 | 사용자에게 보고, 진행 여부 확인 |
| 타임아웃 | 부분 결과 활용, 미완성 부분 명시 |
| 데이터 충돌 | 양쪽 출처 병기, 삭제 금지 |
| GPU 부족 | 모델 크기 축소(8B → QLoRA), 순차 처리로 전환 |
| 컴플라이언스 위반 | 즉시 중단, project-lead 에스컬레이션 |

## 테스트 시나리오

### 정상 흐름
1. Phase 1에서 인프라 구성 완료
2. Phase 2에서 3개 트랙 병렬 진행, qa-engineer가 각 모듈 점진적 검증
3. Phase 3에서 전체 통합, 11단계 파이프라인 엔드투엔드 동작 확인
4. Phase 4에서 모든 성능 목표 달성, 컴플라이언스 통과

### 에러 흐름
1. Phase 2에서 ml-engineer의 OCR 모델이 CER 목표 미달
2. qa-engineer가 탐지하여 ml-engineer에게 보고
3. ml-engineer가 앙상블 가중치 조정 + 후처리 규칙 추가
4. qa-engineer가 재검증, 목표 달성 확인
5. 나머지 Phase 정상 진행

## 실행 방법

이 오케스트레이터는 에이전트 팀 모드로 실행된다:

```
1. TeamCreate("nara-ai-team")
2. 팀원 스폰 (Agent 도구, model: "opus"):
   - project-lead (리더)
   - ml-engineer
   - backend-engineer
   - infra-engineer
   - qa-engineer
3. TaskCreate로 Phase별 작업 할당
4. 팀원 자체 조율 (SendMessage + TaskUpdate)
5. 리더가 결과 종합
6. TeamDelete로 정리
```
