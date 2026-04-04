# NARA-AI 프로젝트 최종 통합 보고서

**작성일**: 2026-04-04
**버전**: v1.0.0 Final
**프로젝트**: AI 기반 국가기록물 지능형 검색/분류/활용 체계 구축

---

## 1. 최종 통계

| 항목 | 수치 |
|------|------|
| 총 파일 | 140개 |
| 코드 라인 | 10,961줄 |
| 테스트 | 99 passed, 0 failed |
| GPU 지원 | 12종 (NVIDIA 9 + AMD 2 + Intel 1) |
| CPU 지원 | 4종 (x86 Intel/AMD + ARM64 + Apple Silicon) |
| OS 지원 | 3종 (Windows + Linux + macOS) |
| Docker 이미지 | 3종 (NVIDIA CUDA + AMD ROCm + CPU) |
| MCP 도구 | 47개 (5서버) |
| AI 에이전트 | 6개 |
| 웹 API | 6 엔드포인트 + 내장 웹 UI |

## 2. 시스템 아키텍처

```
[웹 UI / API] ← FastAPI :8080
    ↓
[LangGraph 오케스트레이터] ← HITL 4개 + 감사추적 10년
    ├── ClassifierAgent (BRM F1≥0.92)
    ├── MetadataAgent (ROUGE-1≥0.85)
    ├── RedactionAgent (PII Precision≥0.95, HITL 필수)
    ├── SearchAgent (Recall@10≥0.90)
    ├── QualityAgent (6항목 검증)
    └── OCR 앙상블 (Qwen3-VL + PaddleOCR + TrOCR)
    ↓
[47 MCP 도구] (5서버: archive + iarna + nara + law + ramp)
    ↓
[Milvus 2.6] + [Cloud Spanner RiC-CM] + [BGE-M3-Korean 1024d]
    ↓
[GPU/CPU 적응형 서빙] ← hardware_profiles 자동 감지
```

## 3. 하드웨어 자동 적응

| 하드웨어 | 등급 | VRAM | 모델 | 양자화 | TP |
|---------|------|------|------|--------|-----|
| B200 x16 | datacenter | 192GB | 8B | none | 4 |
| H100 x8 | datacenter | 80GB | 8B | none | 4 |
| A100 x8 | datacenter | 80GB | 8B | none | 4 |
| RTX 5090 | workstation | 32GB | 8B | none | 1-2 |
| RTX 4090 | workstation | 24GB | 8B | none | 1 |
| RTX 4060 | consumer | 8GB | 3B | int8 | 1 |
| RTX 3060 | consumer | 12GB | 3B | int8 | 1 |
| AMD MI300X | datacenter | 192GB | 8B | none | 8 |
| Intel Arc A770 | consumer | 16GB | 3B | int8 | 1 |
| CPU only | - | - | TF-IDF+BM25 | - | - |

## 4. 파일 구조

```
nara-ai-project/ (140 파일)
├── .claude/agents/         (5)  에이전트 정의
├── .claude/skills/         (6)  스킬 정의
├── api/                    (2)  FastAPI 웹 서버 + 내장 UI
├── config/                 (7)  설정 (hardware_profiles, settings, training configs)
├── src/
│   ├── agents/            (14)  6개 AI 에이전트 (classifier/metadata/redaction/search/quality/orchestrator)
│   ├── mcp-servers/        (8)  5개 MCP 서버 + 공통 (auth/types/server-base)
│   ├── ocr/                (6)  OCR 앙상블 + 레이아웃 + 후처리
│   ├── search/             (7)  Milvus + RAG + 임베딩 + CPU 검색
│   ├── pipeline/           (9)  11단계 파이프라인 + 학습 + 추론 + 평가
│   └── standards/          (3)  RiC-CM 1.0
├── infra/                 (15)  Docker 7 + K8s 4 + Monitoring 3 + Security 1
├── tests/                  (9)  unit 7 + integration 1 + conftest
├── scripts/               (15)  windows 7 + linux 4 + deploy 3 + data 1
├── docs/                   (2)  TDD + PRD
├── data/                   (3)  테스트 + DPO 샘플
├── .github/                (1)  CI/CD
└── root                    (8)  run.py/bat/sh, CLAUDE.md, package.json, etc.
```

## 5. 실행 방법 요약

### Windows
```
setup.bat           초기 설정 (더블클릭)
run.bat             GPU 자동 모드 (더블클릭)
run_cpu.bat         CPU 전용 모드 (더블클릭)
python run.py --check     환경 점검
python run.py --demo      전체 데모
python run.py --test      테스트 실행
```

### Linux / macOS
```
bash scripts/linux/setup.sh      초기 설정
bash run.sh                      GPU 자동 모드
bash run.sh --cpu                CPU 전용 모드
python3 run.py --check           환경 점검
```

### Docker
```
# NVIDIA GPU
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.gpu.yml up

# AMD ROCm
docker build -f infra/docker/Dockerfile.rocm -t nara-ai:rocm .

# CPU 전용
docker build -f infra/docker/Dockerfile.cpu -t nara-ai:cpu .
docker run -p 8080:8080 nara-ai:cpu
```

## 6. 법률 준수

| 법률 | 구현 |
|------|------|
| AI 기본법 (2026.1) | HITL 4개, 감사추적 필수 필드, 설명가능성 |
| ISMS-P (2027.7) | JWT+RBAC, PII 6종 탐지+가명처리, 4중 보안스캔 |
| N2SF "민감" | 에어갭 네트워크 (Docker internal + K8s NetworkPolicy) |
| 공공기록물법 | 제6/33/34/35/38조, 비밀해제 HITL, 폐기 2인 승인 |

## 7. QA 검증 결과

| 검증 영역 | 결과 |
|----------|------|
| 구조 검증 | 12/12 Pass |
| 경계면 교차 비교 | 수정 후 Pass |
| PII/HITL/감사추적 | Pass |
| 성능 목표 매핑 | 8/8 일치 |
| 벤치마크 | F1=1.0, CER=0.0 (샘플 데이터) |
| 테스트 | 99 passed, 0 failed |
| 하드웨어 감지 | 12종 GPU + 4종 CPU 모두 통과 |

## 8. 국민 혜택

1. **접근성**: 자연어 검색으로 290만 국가기록 접근 (P99 ≤ 2초)
2. **투명성**: 비공개 기록물 체계적 공개 전환 (AI 추천 + 인간 결정)
3. **효율성**: 기록물 분류/메타데이터/OCR 자동화 (10배 효율화)
4. **보존**: 100만 페이지 비전자기록물 디지털화 (식민지기/근현대사)
5. **공정성**: AI 편향 방지 + HITL 인간 최종 결정 보장
