# NARA-AI QA 통합 검증 보고서

**작성**: QA Engineer (qa-engineer)
**일자**: 2026-04-04
**범위**: 전체 프로젝트 통합 정합성 검증
**버전**: v1.0 -> **v1.1 (재검증)**

---

## 0. 재검증 이력 (v1.1, 2026-04-04)

v1.0에서 발견된 Critical 3건 + Major 3건이 수정되어 재검증 수행.

| 이슈 ID | 수정 내용 | 재검증 결과 | 근거 |
|---------|----------|-----------|------|
| Critical-01 | MetadataAgent/RedactionAgent 모델명을 `nara-classifier-v1`로 통일 | **Pass** | `metadata/agent.py:52`, `redaction/agent.py:94` 모두 `nara-classifier-v1` 확인, QA-C01 주석 포함 |
| Critical-02 | 오케스트레이터 감사추적에 user_id, agent_name, input_hash 추가 | **Pass** | `orchestrator/graph.py:100-104` classifier_node, `:138-142` metadata_node, `:177-179` redaction_node 모두 3개 필드 추가 확인, `hashlib` import 추가 확인 (line 11) |
| Critical-03 | test_ocr_ensemble.py + test_search_rag.py 추가 | **Pass** | `tests/unit/test_ocr_ensemble.py` (12 tests: OCR 앙상블/레이아웃/후처리), `tests/unit/test_search_rag.py` (14 tests: QueryAnalyzer/MilvusConfig/벤치마크 메트릭/오케스트레이터 그래프) 확인 |
| Major-01 (M01) | Milvus sparse metric_type을 IP로 통일 | **Pass** | `rag/pipeline.py:166` `"metric_type": "IP"` 확인, QA-M01 주석 포함, `milvus/client.py:91`의 IP와 일치 |
| Major-02 (M02) | GraphSearcher를 JSON-RPC 2.0으로 변경 | **Pass** | `rag/pipeline.py:198-203` JSON-RPC 2.0 형식 (`jsonrpc`, `method`, `params`, `id`) 확인, URL `localhost:3002/jsonrpc`, QA-M02 주석 포함 |
| Major-03 (M03) | mcp-archive description 수정 | **Pass** | `archive/index.ts:49` description이 `"5 tools, 추후 10으로 확장"`으로 변경 확인, 실제 도구 수 5와 일치 |

---

## 1. 검증 요약

### v1.0 (초기 검증)

| 영역 | Pass | Fail | Untested | 판정 |
|------|------|------|----------|------|
| 구조 검증 | 12 | 0 | 0 | **Pass** |
| 경계면 교차 비교 | 9 | 4 | 1 | **Fail** |
| 법률 준수 검증 | 10 | 2 | 0 | **Fail** |
| 성능 목표 매핑 | 7 | 1 | 0 | **Pass (경고)** |
| 테스트 커버리지 | 4 | 3 | 0 | **Fail** |

### v1.1 (재검증 후)

| 영역 | Pass | Fail | Untested | 판정 |
|------|------|------|----------|------|
| 구조 검증 | 12 | 0 | 0 | **Pass** |
| 경계면 교차 비교 | 12 | 1 | 1 | **Pass (경고)** |
| 법률 준수 검증 | 11 | 1 | 0 | **Pass (경고)** |
| 성능 목표 매핑 | 7 | 1 | 0 | **Pass (경고)** |
| 테스트 커버리지 | 6 | 1 | 0 | **Pass (경고)** |

**종합 판정**: **Conditional Pass** -- Critical 0건, Major 4건 잔존 (비차단)

---

## 2. 구조 검증

### 2.1 에이전트 정의 파일 (.claude/agents/)

| 파일 | 존재 | frontmatter 유효 | 판정 |
|------|------|-----------------|------|
| project-lead.md | O | O (name, description) | Pass |
| ml-engineer.md | O | O | Pass |
| backend-engineer.md | O | O | Pass |
| infra-engineer.md | O | O | Pass |
| qa-engineer.md | O | O | Pass |

### 2.2 스킬 파일 (.claude/skills/)

| 스킬 | 존재 | frontmatter (name, description) | 판정 |
|------|------|-------------------------------|------|
| model-training/skill.md | O | O | Pass |
| ocr-pipeline/skill.md | O | O | Pass |
| rag-search/skill.md | O | O | Pass |
| mcp-server-dev/skill.md | O | O | Pass |
| compliance-audit/skill.md | O | O | Pass |
| nara-orchestrator/skill.md | O | O | Pass |

### 2.3 디렉토리 구조 vs CLAUDE.md 설계

CLAUDE.md에 정의된 구조와 실제 디렉토리가 일치하는지 확인:

| 디렉토리 | 설계 | 실제 | 판정 |
|----------|------|------|------|
| src/models/ | O | O | Pass |
| src/agents/ (6개 에이전트) | O | O (classifier, metadata, redaction, search, quality, orchestrator) | Pass |
| src/ocr/ | O | O | Pass |
| src/search/ (milvus, embedding, rag) | O | O | Pass |
| src/pipeline/ (ingest, train, eval, serve) | O | O | Pass |
| src/mcp-servers/ (5개) | O | O (archive, iarna, nara, law, ramp) | Pass |
| src/standards/ | O | O | Pass |
| tests/ (unit, integration) | O | O | Pass |
| infra/ (docker, k8s, monitoring) | O | O | Pass |

**구조 검증 결과**: Pass (12/12)

---

## 3. 경계면 교차 비교 (핵심)

### 3.1 MCP 서버 Zod 스키마 vs LangGraph 오케스트레이터 도구 호출

**[Major-01] mcp-archive 도구 수 불일치 -- RESOLVED (v1.1)**

- ~~description이 "10 tools"이나 실제 5개 도구만 등록~~
- **수정 확인**: `archive/index.ts:49` description이 `"5 tools, 추후 10으로 확장"`으로 변경, 실제 도구 수와 일치
- **재검증**: Pass

**[Pass] MCP Zod 스키마 -> Python 에이전트 매핑 일관성**

교차 비교 결과:

| MCP 도구 (TS Zod) | Python 에이전트 메서드 | 파라미터 일치 | 판정 |
|-------------------|---------------------|-------------|------|
| classify_record(title, content, agency?) | ClassifierAgent.classify(title, content, agency="") | O | Pass |
| generate_metadata(content, existingMetadata?) | MetadataAgent.generate(content, existing_metadata=None) | O | Pass |
| review_redaction(title, content, currentLevel, yearsSinceCreation) | RedactionAgent.review(title, content, current_level, years_since_creation) | O | Pass |

**[Pass] LangGraph 오케스트레이터 -> Python 에이전트 호출 일관성**

| 오케스트레이터 노드 | 에이전트 메서드 | 파라미터 | 판정 |
|-------------------|-------------|---------|------|
| classifier_node | ClassifierAgent.classify(title, content, agency) | 일치 | Pass |
| metadata_node | MetadataAgent.generate(content) | 일치 | Pass |
| redaction_node | RedactionAgent.review(title, content) | 일치 | Pass |
| quality_node | 인라인 구현 | N/A | Pass |

### 3.2 vLLM 추론 API 호출 일관성

**[Pass] 모든 에이전트가 동일한 OpenAI-compatible API 형식 사용**

| 에이전트 | 엔드포인트 | 형식 | 모델명 | 판정 |
|---------|----------|------|-------|------|
| ClassifierAgent | `localhost:8000/v1/chat/completions` | OpenAI chat | nara-classifier-v1 | Pass |
| MetadataAgent | `localhost:8000/v1/chat/completions` | OpenAI chat | nara-metadata-v1 | Pass |
| RedactionAgent | `localhost:8000/v1/chat/completions` | OpenAI chat | nara-redaction-v1 | Pass |
| SearchAgent (RAG) | `localhost:8000/v1/chat/completions` | OpenAI chat | nara-classifier-v1 | Pass |
| RAGPipeline | `localhost:8000/v1/chat/completions` | OpenAI chat | nara-classifier-v1 | Pass |

**[Critical-01] vLLM 모델명 불일치 -- RESOLVED (v1.1)**

- ~~K8s deployment에서 `nara-classifier-v1`만 서빙하나, MetadataAgent/RedactionAgent가 다른 모델명 사용~~
- **수정 확인**: MetadataAgent(`metadata/agent.py:52`)와 RedactionAgent(`redaction/agent.py:94`) 모두 `nara-classifier-v1`로 통일
- **재검증**: Pass

### 3.3 임베딩 서버 API vs RAG 파이프라인 호출

**[Pass] 임베딩 요청/응답 형식 일치**

| 호출자 | 요청 형식 | 서버 기대값 | 판정 |
|-------|----------|-----------|------|
| SearchAgent._get_embedding() | `{"texts": [text], "model": "bge-m3-korean", "return_sparse": False}` | EmbeddingRequest(texts, model, return_sparse) | Pass |
| MilvusSearcher.dense_search() | `{"texts": [query], "model": "bge-m3-korean", "return_sparse": False}` | 동일 | Pass |
| MilvusSearcher.sparse_search() | `{"texts": [query], "model": "bge-m3-korean", "return_sparse": True}` | 동일 | Pass |

**[Pass] 임베딩 응답 파싱 일관성**

- 서버 응답: `{"embeddings": [[...1024 floats...]], "sparse_embeddings": [...], ...}`
- SearchAgent: `response.json()["embeddings"][0]` -- 일치
- MilvusSearcher: `emb_response.json()["embeddings"][0]` -- 일치

**[Major-02] Milvus sparse 검색 metric_type 불일치 -- RESOLVED (v1.1)**

- ~~`rag/pipeline.py`에서 `"metric_type": "BM25"` 사용, `milvus/client.py`에서 `"IP"`로 인덱스 생성~~
- **수정 확인**: `rag/pipeline.py:166` metric_type을 `"IP"`로 통일, `milvus/client.py:91`과 일치
- **재검증**: Pass

### 3.4 파이프라인 11단계 입출력 매칭

**[Pass] PipelineStage enum 정의 (11개)**

`ingest -> layout -> ocr -> ocr_post -> classify -> metadata -> redaction -> embedding -> graph -> quality -> security`

**[Pass] LangGraph 오케스트레이터 노드 순서 vs 파이프라인 순서**

오케스트레이터: `classifier -> metadata -> redaction -> (HITL) -> quality -> END`
- 4개 핵심 에이전트 노드의 순서가 파이프라인 5~10단계와 일치

**[Major-03] 오케스트레이터에 일부 파이프라인 단계 미구현**

오케스트레이터(graph.py)에는 다음 노드만 등록:
- classifier, metadata, redaction, quality, hitl_wait

파이프라인 11단계 중 누락된 노드:
- ingest, layout, ocr, ocr_post (전처리 4단계)
- embedding (벡터 임베딩)
- graph (지식그래프 삽입)
- security (보안 스캔)

이는 설계상 의도적일 수 있으나(전처리는 별도 실행), PipelineExecutor와 오케스트레이터 간 역할 분담이 문서화되어 있지 않음.
- **수정 담당**: backend-engineer (문서화) 또는 누락 노드 구현

**[Pass] 단계 간 데이터 전달 형식**

| 생산자 -> 소비자 | 전달 필드 | 타입 일치 | 판정 |
|----------------|----------|---------|------|
| classifier -> metadata | content (ocr_text 또는 content) | str | Pass |
| metadata -> redaction | title, content | str | Pass |
| redaction -> quality | classification_confidence, ocr_confidence, keywords, summary | float/list | Pass |

### 3.5 GraphSearcher -> IARNA MCP 서버 연동

**[Major-04] GraphSearcher API 호출 형식 불일치 -- RESOLVED (v1.1)**

- ~~`rag/pipeline.py` GraphSearcher가 REST 형식 `/tools/vibe_query`로 호출~~
- **수정 확인**: `rag/pipeline.py:198-203` JSON-RPC 2.0 형식으로 변경 (`"jsonrpc": "2.0"`, `"method": "tools/call"`, `"params": {"name": "vibe_query", ...}`)
- **재검증**: Pass

---

## 4. 법률 준수 검증

### 4.1 HITL 게이트 (4개 필수)

| HITL 액션 | 코드 정의 | 법적 근거 | 판정 |
|----------|----------|----------|------|
| redaction_decision | HITLGate.REQUIRED_ACTIONS + orchestrator hitl_wait | 공공기록물법 제34조 | Pass |
| retention_override | HITLGate.REQUIRED_ACTIONS | 공공기록물법 제38조 | Pass |
| classification_dispute | HITLGate.REQUIRED_ACTIONS | 공공기록물법 제33조 | Pass |
| disposal_approval | HITLGate.REQUIRED_ACTIONS | 공공기록물법 제38조 | Pass |

**HITL 게이트 판정**: Pass (4/4)

**[Minor-01]** 오케스트레이터(graph.py)의 HITL 분기는 redaction 후에만 존재. retention_override, classification_dispute, disposal_approval에 대한 HITL 분기가 오케스트레이터에 미구현. PipelineExecutor에서는 4개 모두 초기화되지만, LangGraph 그래프에서는 1개만 활성화됨.

### 4.2 PII 패턴 (6종 이상 필수)

| PII 유형 | 정규식 정의 | severity | 판정 |
|---------|-----------|----------|------|
| resident_id (주민번호) | `\d{6}-[1-4]\d{6}` | critical | Pass |
| phone (전화번호) | `01[0-9]-?\d{3,4}-?\d{4}` | high | Pass |
| email (이메일) | 표준 이메일 패턴 | medium | Pass |
| passport (여권번호) | `[A-Z]{1,2}\d{7,8}` | critical | Pass |
| driver_license (운전면허) | `\d{2}-\d{6}-\d{2}` | critical | Pass |
| account (계좌번호) | `\d{3,4}-\d{2,6}-\d{2,6}` | high | Pass |

**PII 패턴 판정**: Pass (6/6 이상)

compliance-audit/skill.md의 PII_PATTERNS와 redaction/agent.py의 PII_PATTERNS가 동일 6종을 정의함을 확인.

### 4.3 감사추적 필수 필드

compliance-audit/skill.md에서 요구하는 11개 필드:
`decision_id, timestamp, user_id, agent_name, action, input_hash, output, confidence, reasoning, hitl_required, hitl_decision`

| 컴포넌트 | 감사추적 필드 | 누락 | 판정 |
|---------|-------------|------|------|
| pipeline_executor.py AuditEntry | 11개 전체 정의 | 없음 | Pass |
| orchestrator graph.py audit_trail | stage, timestamp, result, confidence, reasoning | user_id, agent_name, input_hash 누락 | **Fail** |
| server-base.ts AuditLogEntry | timestamp, server, tool, userId, inputHash, success, durationMs | reasoning, confidence, hitl_required 누락 | **Fail** |
| types.ts AuditEntrySchema | 11개 전체 (Zod) | 없음 | Pass |

**[Critical-02] 오케스트레이터 감사추적 필수 필드 누락 -- RESOLVED (v1.1)**

- ~~`orchestrator/graph.py`의 audit_trail에 `user_id`, `agent_name`, `input_hash` 누락~~
- **수정 확인**: classifier_node(`:100-104`), metadata_node(`:138-142`), redaction_node(`:177-179`) 모두 3개 필드 추가됨. `hashlib` import(line 11) 추가. `user_id`는 `state.get("user_id", "system")`으로 전달, `agent_name`은 `"nara-ai-{역할}"` 형식, `input_hash`는 SHA-256 16자 해시.
- **재검증**: Pass

**[Major-05] MCP 서버 감사로그에 AI 의사결정 필드 누락**

- `server-base.ts`의 AuditLogEntry에 `reasoning`, `confidence`, `hitl_required` 필드 없음
- types.ts의 AuditEntrySchema(Zod)에는 전체 정의되어 있으나, 실제 createAuditEntry() 함수에서 사용하지 않음
- **수정 담당**: backend-engineer (AuditLogEntry에 필드 추가, createAuditEntry 확장)

### 4.4 에어갭 네트워크 설정

**[Pass] Docker Compose 에어갭 설정**

```yaml
networks:
  nara-internal:
    driver: bridge
    internal: true  # 외부 네트워크 차단
```

모든 서비스가 `nara-internal` 네트워크에만 연결됨을 확인.

**[Pass] Kubernetes 에어갭 설정**

```yaml
kind: NetworkPolicy
metadata:
  name: deny-external
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to: [namespaceSelector: national-archives-ai]
    - to: [ipBlock: 10.0.0.0/8]
```

외부 Egress 차단, 내부 네트워크만 허용.

**[Pass] Docker/K8s 에어갭 일관성**: 양쪽 모두 외부 네트워크 차단 설정이 적용됨.

**[Minor-02]** mcp-nara/index.ts에 US NARA Catalog API URL (`https://catalog.archives.gov/api/v2`) 하드코딩. 에어갭 환경에서는 호출 불가하며, 주석에 "로컬 캐시/미러 사용"으로 기재되어 있으나 실제 캐시 구현은 없음.

---

## 5. 성능 목표 매핑

### 5.1 벤치마크 목표 vs 스킬 문서 목표

| 메트릭 | benchmark.py TARGETS | model-training skill.md | 일치 | 판정 |
|-------|---------------------|----------------------|------|------|
| classification_f1 | 0.92 | >= 0.92 | O | Pass |
| metadata_rouge1 | 0.85 | >= 0.85 | O | Pass |
| redaction_precision | 0.95 | >= 0.95 | O | Pass |
| ocr_cer_printed | 0.03 (3%) | <= 3% | O | Pass |
| ocr_cer_handwritten | 0.10 (10%) | <= 10% | O | Pass |
| ocr_cer_hanja | 0.07 (7%) | <= 7% | O | Pass |
| search_recall_at_10 | 0.90 | (rag/pipeline.py docstring) >= 0.90 | O | Pass |
| search_p99_latency | 2.0s | (search/agent.py docstring) <= 2s | O | Pass |

**성능 목표 매핑**: Pass (8/8 일치)

### 5.2 에이전트 docstring 목표 vs 코드 구현

| 에이전트 | docstring 목표 | 코드 임계값 | 일치 | 판정 |
|---------|--------------|-----------|------|------|
| classifier | F1 >= 0.92 | confidence_threshold=0.85 (HITL 분기용) | N/A (목적 다름) | Pass |
| metadata | ROUGE-1 >= 0.85 | N/A (런타임 평가) | Pass | Pass |
| redaction | Precision >= 0.95 | hitl_pending=True (항상) | Pass | Pass |
| search | Recall@10 >= 0.90 | timeout=10.0s | Pass | Pass |
| quality | N/A | classification_confidence=0.85, ocr_confidence=0.70 | Pass | Pass |

**[Minor-03]** benchmark.py의 run_benchmark()에서 classification과 OCR 벤치마크만 구현. metadata_rouge1, redaction_precision, search_recall_at_10 벤치마크 실행 함수가 미구현.

---

## 6. 테스트 커버리지

### 6.1 단위 테스트

| 테스트 파일 | 테스트 대상 | 테스트 수 | 판정 |
|-----------|-----------|---------|------|
| test_pipeline.py | PipelineStage, RecordDocument, HITLGate, AuditEntry, PipelineExecutor, SecurityLevel | ~15 | Pass |
| test_redaction.py | PII 탐지 (6종), 마스킹, 패턴 유효성 | ~9 | Pass |
| test_ocr_ensemble.py **(v1.1 추가)** | OCR 앙상블 모델 라우팅, CER 목표, 문서 유형, 레이아웃 감지, BoundingBox, 후처리 교정, 한자 병기, 날짜/기관 추출 | ~12 | Pass |
| test_search_rag.py **(v1.1 추가)** | QueryAnalyzer 의도 분류 (4종), MilvusConfig, 벤치마크 메트릭 (F1/ROUGE-1/CER), 성능 목표 8개, 오케스트레이터 그래프 빌드, RecordProcessingState 정의 | ~14 | Pass |

### 6.2 통합 테스트

| 테스트 파일 | 테스트 대상 | 테스트 수 | 판정 |
|-----------|-----------|---------|------|
| test_mcp_servers.py | 헬스체크, Milvus 연결, 경계면 검증 (도구 수, 파이프라인 단계, HITL, 보안등급, PII 패턴, RiC-CM, BRM, OCR 앙상블) | ~12 | Pass |

### 6.3 미커버 영역

**[Major-06] 핵심 모듈 단위 테스트 부재 -- PARTIALLY RESOLVED (v1.1)**

v1.1에서 test_ocr_ensemble.py와 test_search_rag.py가 추가되어 OCR 앙상블, RAG QueryAnalyzer, 벤치마크 메트릭, 오케스트레이터 그래프 빌드 등이 커버됨. 그러나 아래 모듈에 대한 직접적인 단위 테스트는 여전히 부재:

| 모듈 | 테스트 존재 | v1.1 변경 | 중요도 |
|------|----------|----------|-------|
| classifier/agent.py | X | (vLLM 호출 모킹 필요) | Medium -- 통합 테스트에서 간접 커버 |
| metadata/agent.py | X | (vLLM 호출 모킹 필요) | Medium |
| search/agent.py | X | QueryAnalyzer 부분 커버 | Medium |
| quality/agent.py | X | - | Low |
| orchestrator/graph.py | **O (v1.1)** | 그래프 빌드 + 상태 정의 테스트 | **Resolved** |
| embedding/server.py | X | - | Low |
| rag/pipeline.py | **O (v1.1)** | QueryAnalyzer 테스트 | **Partially Resolved** |
| milvus/client.py | **O (v1.1)** | MilvusConfig 테스트 | **Partially Resolved** |
| ocr/pipeline | **O (v1.1)** | 앙상블/레이아웃/후처리 12 tests | **Resolved** |

**[Major-07] 통합 테스트의 경계면 검증이 정적 검증에 한정**

- test_mcp_servers.py의 TestBoundaryVerification 클래스가 값 비교만 수행 (코드 import 후 len() 체크)
- 실제 네트워크 호출을 통한 경계면 동작 검증 없음
- MCP 서버 Zod 스키마 vs Python 에이전트 파라미터의 동적 교차 검증 부재

---

## 7. 이슈 요약

### Critical (즉시 수정 필요) -- v1.1: 전부 해결

| ID | 이슈 | v1.1 상태 |
|----|------|----------|
| ~~Critical-01~~ | ~~vLLM 모델명 불일치~~ | **RESOLVED** -- 모델명 `nara-classifier-v1`로 통일 |
| ~~Critical-02~~ | ~~오케스트레이터 감사추적 필수 필드 누락~~ | **RESOLVED** -- user_id, agent_name, input_hash 추가 |
| ~~Critical-03~~ | ~~핵심 모듈 단위 테스트 부재~~ | **RESOLVED** -- test_ocr_ensemble.py, test_search_rag.py 추가 (26+ tests) |

### Major (다음 스프린트 내 수정) -- v1.1: 3건 해결, 4건 잔존

| ID | 이슈 | v1.1 상태 | 수정 담당 |
|----|------|----------|---------|
| ~~Major-01~~ | ~~mcp-archive description 불일치~~ | **RESOLVED** | - |
| ~~Major-02~~ | ~~Milvus sparse metric_type 불일치~~ | **RESOLVED** | - |
| Major-03 | 오케스트레이터에 11단계 중 7단계 노드 미구현 (역할 분담 미문서화) | **Open** | backend-engineer |
| ~~Major-04~~ | ~~GraphSearcher REST -> JSON-RPC~~ | **RESOLVED** | - |
| Major-05 | MCP 서버 AuditLogEntry에 reasoning/confidence/hitl_required 필드 누락 | **Open** | backend-engineer |
| Major-06 | 일부 에이전트(classifier, metadata, search) vLLM 호출 모킹 단위 테스트 부재 | **Open (축소)** | 전원 |
| Major-07 | 통합 테스트가 정적 값 검증에 한정, 동적 경계면 검증 부재 | **Open** | qa-engineer |

### Minor (개선 권고)

| ID | 이슈 | 수정 담당 |
|----|------|---------|
| Minor-01 | 오케스트레이터 HITL 분기가 redaction만 활성화 (retention/classification/disposal 미활성) | backend-engineer |
| Minor-02 | mcp-nara에 외부 API URL 하드코딩 (에어갭 환경 캐시 미구현) | backend-engineer |
| Minor-03 | benchmark.py에 metadata/redaction/search 벤치마크 실행 함수 미구현 | ml-engineer |

---

## 8. 교차 비교 세부 결과

### 8.1 TypeScript(MCP) <-> Python(Agent) 타입 매핑

| TypeScript 타입 (types.ts) | Python 타입 (pipeline_executor.py) | 일치 |
|---------------------------|----------------------------------|------|
| RecordTypeSchema (7종) | RecordType enum (7종) | O |
| SecurityLevelSchema (4종) | SecurityLevel enum (4종) | O |
| BRM_TOP_LEVEL (16개 키) | BRM_CATEGORIES (16개 키) | O |
| RetentionPeriods (6종) | 미정의 | X (Minor) |
| SERVICE_PORTS (12개) | 각 에이전트 default 파라미터 | O (일치 확인) |

### 8.2 포트 매핑 일관성

| 서비스 | types.ts | docker-compose.yml | K8s | 에이전트 코드 | 판정 |
|-------|---------|-------------------|-----|-----------|------|
| vLLM LLM | 8000 | (docker-compose.gpu.yml) | 8000 | classifier: 8000 | Pass |
| vLLM OCR | 8001 | - | - | - | Untested |
| Embedding | 8002 | 8002 | - | search: 8002 | Pass |
| Milvus | 19530 | 19530 | - | milvus: 19530 | Pass |
| MCP Archive | 3001 | 3001 | - | - | Pass |
| MCP IARNA | 3002 | 3002 | - | rag: 3002 | Pass |
| MCP NARA | 3003 | 3003 | - | - | Pass |
| MCP LAW | 3004 | 3004 | - | - | Pass |
| MCP RAMP | 3005 | 3005 | - | - | Pass |

### 8.3 RBAC 역할 매핑 일관성

| 소스 | 역할 목록 | 보안 등급 매핑 | 판정 |
|------|----------|-------------|------|
| auth.ts ROLE_PERMISSIONS | admin/archivist/researcher/public | 4/3/2/1 등급 | Pass |
| search/agent.py role_permissions | admin/archivist/researcher/public | 4/3/2/1 등급 | Pass |
| compliance-audit/skill.md | admin/archivist/researcher/public | 기재 일치 | Pass |

---

## 9. 권고사항 (v1.1 업데이트)

### 해결 완료 (v1.1)

1. ~~vLLM 모델명 통일~~ -- **Done**
2. ~~오케스트레이터 감사추적 보강~~ -- **Done**
3. ~~핵심 모듈 단위 테스트 추가~~ -- **Done**
4. ~~Milvus sparse metric_type 통일~~ -- **Done**
5. ~~GraphSearcher JSON-RPC 변경~~ -- **Done**

### 잔존 권고사항 (우선순위순)

1. **MCP 서버 감사로그 필드 확장** (Major-05): `server-base.ts` AuditLogEntry에 reasoning, confidence, hitl_required 추가. `types.ts`의 AuditEntrySchema와 일치시킬 것.
2. **오케스트레이터/PipelineExecutor 역할 분담 문서화** (Major-03): LangGraph는 AI 에이전트 노드만 담당하고, PipelineExecutor가 11단계 전체를 관리하는 설계 의도를 CLAUDE.md 또는 아키텍처 문서에 명시.
3. **vLLM 호출 에이전트 모킹 테스트** (Major-06): classifier, metadata, search 에이전트의 `_parse_response()` 등 순수 함수에 대한 단위 테스트. httpx.AsyncClient를 모킹하여 vLLM 없이도 테스트 가능하도록 구성.
4. **동적 경계면 통합 테스트** (Major-07): Docker Compose 환경에서 MCP 서버 <-> LangGraph 간 실제 네트워크 호출 테스트.

---

## 10. 결론

### v1.0 결론 (초기)

NARA-AI 프로젝트의 개별 컴포넌트는 높은 품질로 구현되어 있으나, 경계면에서 Critical 3건이 발견되어 Fail 판정.

### v1.1 결론 (재검증)

**Critical 3건 + Major 3건이 모두 올바르게 수정되었음을 코드 수준에서 확인했습니다.**

수정 품질 평가:
- **C01 (모델명 통일)**: 가장 적절한 해결 방안(C안: 동일 모델명 사용)이 채택됨. SFT 단일 모델을 공유하는 것은 현 단계에 적합.
- **C02 (감사추적 보강)**: 3개 노드(classifier, metadata, redaction) 모두에 user_id, agent_name, input_hash가 일관되게 추가됨. hashlib import도 정상.
- **C03 (테스트 추가)**: OCR 앙상블 12 tests + 검색/RAG/오케스트레이터 14 tests로 기존 대비 커버리지 대폭 개선.
- **M01 (metric_type)**: IP로 통일하여 milvus/client.py와 rag/pipeline.py 간 일관성 확보.
- **M02 (JSON-RPC)**: MCP 프로토콜 표준에 맞게 JSON-RPC 2.0 형식으로 올바르게 변경.
- **M03 (description)**: 실제 도구 수와 일치, 확장 계획 명시.

**잔존 이슈** (Major 4건, Minor 3건): 모두 비차단(non-blocking) 이슈로, 다음 스프린트에서 해결 가능. 특히 Major-03(오케스트레이터 역할 분담 문서화)과 Major-05(MCP 감사로그 필드 확장)는 코드 품질 개선 사항.

**종합 판정: Conditional Pass** -- 프로덕션 배포 전 Major-05(MCP 감사로그) 해결을 권고하나, 현재 수준에서 통합 테스트 진행 가능.
