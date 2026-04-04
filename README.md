# NARA-AI v1.0

**AI 기반 국가기록물 지능형 검색 / 분류 / 활용 체계**

행정안전부 / 국가기록원 | GPU: NVIDIA B200 16~32장 | 기간: 2027~2028

> "국민을 위한, 국민에 의한, 국민에게 혜택이 돌아가는" AI 기록물 관리 시스템

## 빠른 시작 (Quick Start)

### Windows
```
setup.bat                                    # 1. 초기 설정
python scripts\data\index_demo_data.py       # 2. 데모 데이터 (30건)
run.bat                                      # 3. 서버 시작 (GPU)
run_cpu.bat                                  # 3. 서버 시작 (CPU)
```

### Linux / macOS
```bash
bash scripts/linux/setup.sh                  # 1. 초기 설정
python3 scripts/data/index_demo_data.py      # 2. 데모 데이터
bash run.sh                                  # 3. GPU 모드
bash run.sh --cpu                            # 3. CPU 모드
```

### 브라우저 접속
```
http://localhost:8080       웹 UI (검색 / PII 탐지 / OCR 교정)
http://localhost:8080/docs  API 문서 (Swagger)
```

## 주요 기능

| 기능 | 설명 | 성능 목표 |
|------|------|----------|
| 자연어 검색 | 국가기록물 시맨틱 검색 (TF-IDF + BM25 + Dense + Graph) | Recall@10 >= 0.90 |
| 기록물 분류 | BRM 업무기능 자동 매핑 | F1 >= 0.92 |
| 메타데이터 생성 | 제목/요약/키워드/NER 자동 추출 | ROUGE-1 >= 0.85 |
| OCR 디지털화 | 3모델 앙상블 (Qwen3-VL + PaddleOCR + TrOCR) | CER <= 3%/7%/10% |
| 비밀해제 심사 | PII 탐지 + 공개 적합성 평가 (HITL 필수) | Precision >= 0.95 |
| OCR 후처리 | 도메인 교정, 한자 병기, 날짜 정규화 | - |

## 하드웨어 자동 감지

```bash
python run.py --check
```

| GPU | VRAM | 추천 모델 | 양자화 |
|-----|------|---------|--------|
| B200 | 192GB | 8B | none |
| H100 | 80GB | 8B | none |
| RTX 5090 | 32GB | 8B | none |
| RTX 4060 | 8GB | 3B | int8 |
| RTX 3060 | 12GB | 3B | int8 |
| CPU only | - | TF-IDF+BM25 | - |

AMD ROCm, Intel oneAPI, Apple Silicon도 자동 감지됩니다.

## 기술 스택

- **LLM**: EXAONE 3.5 8B (QLoRA+DoRA SFT/DPO)
- **OCR**: Qwen3-VL 8B + PaddleOCR-VL + TrOCR 앙상블
- **검색**: Milvus 2.6 (BGE-M3-Korean 1024d) / CPU: TF-IDF + BM25
- **그래프**: Cloud Spanner Property Graph (RiC-CM 1.0)
- **에이전트**: LangGraph 오케스트레이터 + 5개 MCP 서버 (47 도구)
- **서빙**: vLLM + FastAPI
- **인프라**: Docker + Kubernetes + Prometheus + Grafana

## 프로젝트 구조

```
nara-ai-project/
├── .claude/           하네스 (에이전트 5 + 스킬 6)
├── api/               FastAPI 웹 서버 + 내장 UI
├── config/            설정 (hardware_profiles, settings, training)
├── src/
│   ├── agents/        AI 에이전트 6개
│   ├── mcp-servers/   MCP 서버 5개 (47 도구)
│   ├── ocr/           OCR 앙상블 + 후처리
│   ├── search/        Milvus + RAG + 임베딩 + CPU 검색
│   ├── pipeline/      11단계 파이프라인
│   └── standards/     RiC-CM 1.0
├── infra/             Docker + K8s + Prometheus
├── tests/             99 테스트
├── scripts/           Windows bat + Linux sh
└── docs/              TDD + PRD
```

## 법률 준수

- **AI 기본법** (2026.1): HITL 4개, 감사추적, 설명가능성
- **ISMS-P** (2027.7): JWT+RBAC, PII 6종 탐지, 4중 보안스캔
- **N2SF**: 에어갭 네트워크 (Docker internal + K8s NetworkPolicy)
- **공공기록물법**: 제6/33/34/35/38조, 비밀해제 HITL, 폐기 2인 승인

## 명령어

```bash
python run.py --check       환경 점검 (GPU/CPU/OS 자동 감지)
python run.py --demo        전체 데모 (검색 + PII + OCR + 벤치마크)
python run.py --test        테스트 실행 (99개)
python run.py --server      웹 서버 시작
python run.py --cpu         CPU 전용 모드
python run.py --benchmark   벤치마크
```

## 라이선스

이 프로젝트는 대한민국 국가기록원의 AI 기반 국가기록물 관리 시스템입니다.
