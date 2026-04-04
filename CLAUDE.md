# NARA-AI — Claude Code 프로젝트 컨텍스트

## 프로젝트 개요
AI 기반 국가기록물 지능형 검색·분류·활용 체계 구축
- **주관**: 행정안전부 / 국가기록원 기록관리교육센터
- **GPU**: NVIDIA B200 16~32장 (국가 AI 프로젝트 배분)
- **기간**: 2027~2028 (2개년)
- **핵심**: 한국어 기록관리 특화 LLM + OCR + RAG + MCP 에이전트

## 기술 스택
- **LLM**: EXAONE 3.5 8B / Solar Pro 2 / Qwen 2.5 (CPT → SFT → DPO)
- **OCR**: Qwen3-VL 8B + PaddleOCR-VL + TrOCR (앙상블)
- **벡터 DB**: Milvus 2.6 (BGE-M3-Korean, RaBitQ, Lindera 한국어)
- **그래프 DB**: Cloud Spanner Property Graph (RiC-CM 1.0)
- **에이전트**: LangGraph 오케스트레이터 + 5개 MCP 서버
- **서빙**: vLLM (PagedAttention)
- **학습**: DeepSpeed ZeRO-3 / FSDP2 / QLoRA+DoRA

## 디렉토리 구조
```
nara-ai-project/
├── harness/            # 프로젝트 하네스 (CLI 도구)
├── config/             # 설정 (MCP 레지스트리, DeepSpeed, .env)
├── src/
│   ├── models/         # 모델 (base, finetuned, configs)
│   ├── agents/         # 에이전트 (classifier, metadata, redaction, search, quality, orchestrator)
│   ├── ocr/            # OCR (pipeline, models, postprocess)
│   ├── search/         # 검색 (milvus, embedding, rag)
│   ├── pipeline/       # 파이프라인 (ingest, preprocess, train, eval, serve)
│   ├── mcp-servers/    # MCP 서버 5개 (ramp, archive, iarna, nara, law)
│   └── standards/      # 국제 표준 (ric-cm, isadg, iso15489)
├── data/               # 데이터 (raw, processed, embeddings)
├── tests/              # 테스트 (unit, integration, benchmark, security)
├── infra/              # 인프라 (docker, k8s, monitoring)
├── docs/               # 문서 (tdd, prd, api, reports)
├── scripts/            # 학습·서빙 스크립트
└── checkpoints/        # 모델 체크포인트
```

## 기존 자산 10종 (통합 대상)
1. Records AI Agent Workspace v3.5 — 237 API, 19 스킬, MCP 8도구
2. IARNA v2.1 — Spanner PG, 12 MCP 도구, Vibe Query
3. ARAM-ADK v15~v40 — Go 42 에이전트, 120 엔진
4. NARA-CLAW v1.0 — 5 MCP 서버, 60 도구, Vision OCR
5. NextSAST v7.1 — SAST 보안 점검, ISMS-P 검증
6. 기록이 AI Agent v11 — 공공기록물법 자문
7. Council Hub v9.5 — 41 AI 에이전트 토론
8. KAMP v3 — 30개 기관 대시보드
9. GAMP v1.0 — 12개국 기록관 협력
10. TNA Korea v19.1 — 영국 기록 연구

## 하네스 (에이전트 팀)

하네스 기반 에이전트 팀으로 프로젝트를 실행한다.
실행 모드: Pipeline + Fan-out/Fan-in 하이브리드.

### 에이전트 (.claude/agents/)
| 에이전트 | 역할 |
|---------|------|
| project-lead | 아키텍처 설계, 통합 조율 |
| ml-engineer | 모델 학습, OCR, 임베딩, 추론 서빙 |
| backend-engineer | MCP 서버, RAG, 벡터DB, LangGraph |
| infra-engineer | Docker, K8s, 모니터링, 보안 |
| qa-engineer | 통합 검증, 경계면 테스트, 컴플라이언스 |

### 스킬 (.claude/skills/)
| 스킬 | 트리거 |
|------|--------|
| nara-orchestrator | 전체 빌드, 에이전트 팀 실행 |
| model-training | 파인튜닝, SFT, DPO, DeepSpeed |
| ocr-pipeline | OCR, 문자인식, 디지털화 |
| rag-search | 검색, RAG, 벡터DB, 임베딩 |
| mcp-server-dev | MCP 서버, LangGraph |
| compliance-audit | 컴플라이언스, 보안 감사, ISMS-P |

## 주요 명령어
```bash
# 하네스 CLI
npm run init          # 초기화
npm run check         # 헬스체크
npm run train -- sft-classifier  # 학습
npm run serve         # 서빙
npm run pipeline      # 전체 파이프라인
npm run eval          # 벤치마크

# 배포
bash scripts/deploy/start-services.sh   # 전체 서비스 시작
bash scripts/deploy/stop-services.sh    # 전체 서비스 중지

# 학습
bash scripts/training/train_sft.sh 4    # SFT 학습 (4 GPU)
python scripts/data/prepare_sft_data.py # 학습 데이터 준비

# 테스트
PYTHONPATH=. pytest tests/unit/ -v      # 단위 테스트
PYTHONPATH=. pytest tests/integration/  # 통합 테스트
```

## 서비스 포트 매핑
| 서비스 | 포트 | 설명 |
|--------|------|------|
| vLLM LLM | 8000 | 분류/메타/비밀해제 추론 |
| vLLM OCR | 8001 | Qwen3-VL 비전 OCR |
| Embedding | 8002 | BGE-M3-Korean |
| Milvus | 19530 | 벡터DB |
| MCP Archive | 3001 | ARAM-ADK 래핑 |
| MCP IARNA | 3002 | 지식그래프 |
| MCP NARA | 3003 | 국제 아카이브 |
| MCP Law | 3004 | 법률 자문 |
| MCP RAMP | 3005 | RAMP 연동 |
| Prometheus | 9090 | 모니터링 |
| Grafana | 3000 | 대시보드 |

## 개발 규칙
- TypeScript strict, ESM only
- Python 3.11+, type hints 필수
- 모든 MCP 서버는 /health GET 엔드포인트 필수
- 감사추적(audit trail) 활성화 — LangGraph 체크포인팅
- 감사추적 필수 필드: user_id, agent_name, input_hash, timestamp, confidence, hitl_required
- 비공개기록물 관련 코드는 보안 리뷰 필수
- 개인정보 처리 시 가명처리(§28의2) 적용
- 모든 에이전트는 단일 모델명(nara-classifier-v1) 사용

## 성능 목표
| 과업 | 메트릭 | 목표 |
|------|--------|------|
| 분류 | F1 | ≥ 0.92 |
| 메타데이터 | ROUGE-1 | ≥ 0.85 |
| 비밀해제 PII | Precision | ≥ 0.95 |
| OCR 활자/한자/필사 | CER | ≤ 3%/7%/10% |
| 검색 | Recall@10 | ≥ 0.90 |
| 검색 레이턴시 | P99 | ≤ 2초 |

## 법률 준수
- AI 기본법 (2026.1): HITL 4개, 감사추적, 설명가능성
- ISMS-P (2027.7): JWT+RBAC, PII 6종 탐지, 4중 보안스캔
- N2SF "민감": 에어갭 (Docker internal: true, K8s NetworkPolicy)
- 공공기록물법: 제6/33/34/35/38조
