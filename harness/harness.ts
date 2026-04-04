#!/usr/bin/env npx tsx
/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║   NARA-AI Project Harness v1.0                                         ║
 * ║   AI 기반 국가기록물 지능형 검색·분류·활용 체계 구축                          ║
 * ║   행정안전부 / 국가기록원 · 국가 AI 프로젝트 GPU 지원 과제                    ║
 * ╠══════════════════════════════════════════════════════════════════════════╣
 * ║   GPU: B200 16~32장 | 기간: 2027~2028 (2개년)                           ║
 * ║   기존 자산: 10개 프로젝트 · 160K+ LOC · 279 API · 61 에이전트             ║
 * ╠══════════════════════════════════════════════════════════════════════════╣
 * ║   Commands:                                                             ║
 * ║     harness init        — 프로젝트 초기화 (의존성·환경·디렉토리)             ║
 * ║     harness check       — 전체 시스템 헬스체크                             ║
 * ║     harness train       — 모델 학습 파이프라인 실행                         ║
 * ║     harness serve       — 추론 서비스 기동 (vLLM + MCP)                   ║
 * ║     harness pipeline    — OCR + 분류 + 메타데이터 전체 파이프라인            ║
 * ║     harness eval        — 모델 평가 및 벤치마크                            ║
 * ║     harness report      — 과제 성과 보고서 생성                            ║
 * ║     harness status      — 전체 시스템 현황 대시보드                         ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import { execSync, spawn, ChildProcess } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

// ═══════════════════════════════════════════════════════════
// §1. 프로젝트 상수 및 설정
// ═══════════════════════════════════════════════════════════

const VERSION = "1.0.0";
const PROJECT_NAME = "NARA-AI";
const PROJECT_ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");

const COLORS = {
  reset: "\x1b[0m", bold: "\x1b[1m", dim: "\x1b[2m",
  red: "\x1b[31m", green: "\x1b[32m", yellow: "\x1b[33m",
  blue: "\x1b[34m", magenta: "\x1b[35m", cyan: "\x1b[36m",
  white: "\x1b[37m", bgBlue: "\x1b[44m", bgGreen: "\x1b[42m",
};

function log(icon: string, msg: string, color = COLORS.white) {
  console.log(`${color}  ${icon}  ${msg}${COLORS.reset}`);
}
function header(title: string) {
  const line = "═".repeat(60);
  console.log(`\n${COLORS.cyan}╔${line}╗`);
  console.log(`║  ${COLORS.bold}${title.padEnd(58)}${COLORS.cyan}║`);
  console.log(`╚${line}╝${COLORS.reset}\n`);
}

// ═══════════════════════════════════════════════════════════
// §2. 기존 자산 레지스트리 (10개 프로젝트)
// ═══════════════════════════════════════════════════════════

interface LegacyAsset {
  id: string;
  name: string;
  nameKr: string;
  version: string;
  lang: string;
  loc: string;       // Lines of Code
  apis: number;
  agents: number;
  tests: number;
  role: string;       // 본 과제에서의 역할
  mcpTools: number;
  integration: string; // 통합 방식
}

const LEGACY_ASSETS: LegacyAsset[] = [
  {
    id: "records-ai-workspace",
    name: "Records AI Agent Workspace",
    nameKr: "기록관리 AI 에이전트 워크스페이스",
    version: "3.5",
    lang: "TypeScript",
    loc: "70,000+",
    apis: 237,
    agents: 0,
    tests: 110,
    mcpTools: 8,
    role: "핵심 API 게이트웨이 · 자기진화 플랫폼 · 19개 스킬 엔진",
    integration: "MCP 서버 래핑 → LangGraph 도구 등록",
  },
  {
    id: "iarna",
    name: "IARNA",
    nameKr: "지능형 아카이브 기록물 관계망 에이전트",
    version: "2.1",
    lang: "TypeScript",
    loc: "5,800+",
    apis: 11,
    agents: 0,
    tests: 48,
    mcpTools: 12,
    role: "Cloud Spanner Property Graph · RiC-CM 구현 · Vibe Query Engine",
    integration: "Spanner DDL → RiC-CM 그래프 · MCP 12도구 직접 활용",
  },
  {
    id: "aram-adk",
    name: "ARAM-ADK",
    nameKr: "아카이브 기록관리 에이전트 개발 키트",
    version: "v15~v40",
    lang: "Go",
    loc: "90,000+",
    apis: 0,
    agents: 42,
    tests: 1139,
    mcpTools: 0,
    role: "42개 전문 에이전트 · 120개 엔진 · 순수 Go 런타임",
    integration: "Go 바이너리 → gRPC 서비스 → MCP 브릿지",
  },
  {
    id: "nara-claw",
    name: "NARA-CLAW",
    nameKr: "NARA 기록물 수집·분석 시스템",
    version: "1.0",
    lang: "Node.js",
    loc: "5,100+",
    apis: 17,
    agents: 3,
    tests: 52,
    mcpTools: 60,
    role: "NARA/TNA/DPLA 연동 · RG331/554/338 발굴 · Vision OCR",
    integration: "5개 MCP 서버 직접 등록 · 해외기록물 연동 계층",
  },
  {
    id: "nextsast",
    name: "NextSAST",
    nameKr: "옴니SAST 양자방어 플랫폼",
    version: "7.1",
    lang: "Python",
    loc: "72,700+",
    apis: 207,
    agents: 21,
    tests: 520,
    mcpTools: 0,
    role: "코드 보안 점검 · ISMS-P 준수 검증 · AI 모델 보안 감사",
    integration: "보안 게이트 모듈로 CI/CD 파이프라인에 통합",
  },
  {
    id: "girok-ai-agent",
    name: "기록이 AI Agent",
    nameKr: "한국 공공기록물법 AI 자문 시스템",
    version: "v11 PLATINUM",
    lang: "Python",
    loc: "8,000+",
    apis: 5,
    agents: 4,
    tests: 0,
    mcpTools: 0,
    role: "공공기록물법 해석 · 보존기간 산정 · 법적 근거 자동 매핑",
    integration: "법령 지식베이스 → RAG 검색 소스 · 분류 에이전트 법적 검증 계층",
  },
  {
    id: "council-hub",
    name: "Council Hub",
    nameKr: "멀티에이전트 토론 플랫폼",
    version: "9.5",
    lang: "React/TypeScript",
    loc: "12,000+",
    apis: 0,
    agents: 41,
    tests: 0,
    mcpTools: 0,
    role: "공개재분류 심의 보조 · 41 AI 에이전트 토론 기반 의사결정",
    integration: "공개재분류 워크플로우의 HITL(Human-in-the-Loop) 심의 UI",
  },
  {
    id: "kamp",
    name: "KAMP",
    nameKr: "한국 기록관리 플랫폼",
    version: "3.0",
    lang: "React",
    loc: "8,400+",
    apis: 0,
    agents: 27,
    tests: 0,
    mcpTools: 0,
    role: "전국 30개 기관 기록관리 대시보드 · 27개 수집 에이전트",
    integration: "전국 기록관 AI 모니터링 포털로 확장",
  },
  {
    id: "gamp",
    name: "GAMP",
    nameKr: "전세계 기록관리 협력 플랫폼",
    version: "1.0",
    lang: "React",
    loc: "8,400+",
    apis: 0,
    agents: 27,
    tests: 0,
    mcpTools: 0,
    role: "글로벌 벤치마킹 · 12개국 기록관 비교분석",
    integration: "해외 사례 비교 대시보드 · 국제 협력 인터페이스",
  },
  {
    id: "tna-korea",
    name: "TNA Korea Research Tool",
    nameKr: "영국 국립기록보관소 한국 기록 연구 도구",
    version: "19.1",
    lang: "TypeScript/Python",
    loc: "3,000+",
    apis: 5,
    agents: 0,
    tests: 0,
    mcpTools: 5,
    role: "TNA Discovery API 연동 · 한국 관련 기록 크로스레퍼런스",
    integration: "NARA-CLAW과 병합 → 국제 기록물 통합 검색 계층",
  },
];

// ═══════════════════════════════════════════════════════════
// §3. 시스템 요구사항 검증
// ═══════════════════════════════════════════════════════════

interface CheckResult {
  name: string;
  status: "pass" | "warn" | "fail";
  message: string;
  required: boolean;
}

function checkSystem(): CheckResult[] {
  const results: CheckResult[] = [];

  // Node.js
  try {
    const nodeVer = execSync("node --version", { encoding: "utf8" }).trim();
    const major = parseInt(nodeVer.replace("v", "").split(".")[0]);
    results.push({
      name: "Node.js",
      status: major >= 20 ? "pass" : major >= 18 ? "warn" : "fail",
      message: `${nodeVer} (>= v20 권장)`,
      required: true,
    });
  } catch {
    results.push({ name: "Node.js", status: "fail", message: "미설치", required: true });
  }

  // Python
  try {
    const pyVer = execSync("python3 --version 2>/dev/null || python --version", { encoding: "utf8" }).trim();
    results.push({ name: "Python", status: "pass", message: pyVer, required: true });
  } catch {
    results.push({ name: "Python", status: "fail", message: "미설치", required: true });
  }

  // Go
  try {
    const goVer = execSync("go version", { encoding: "utf8" }).trim();
    results.push({ name: "Go", status: "pass", message: goVer, required: false });
  } catch {
    results.push({ name: "Go", status: "warn", message: "미설치 (ARAM-ADK 빌드 시 필요)", required: false });
  }

  // Docker
  try {
    const dockerVer = execSync("docker --version", { encoding: "utf8" }).trim();
    results.push({ name: "Docker", status: "pass", message: dockerVer, required: false });
  } catch {
    results.push({ name: "Docker", status: "warn", message: "미설치 (컨테이너 배포 시 필요)", required: false });
  }

  // GPU (nvidia-smi)
  try {
    const gpuInfo = execSync("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null", { encoding: "utf8" }).trim();
    const gpuCount = gpuInfo.split("\n").length;
    results.push({ name: "NVIDIA GPU", status: "pass", message: `${gpuCount}장 — ${gpuInfo.split("\n")[0]}`, required: false });
  } catch {
    results.push({ name: "NVIDIA GPU", status: "warn", message: "미감지 (개발 환경에서는 CPU 모드 사용)", required: false });
  }

  // Git
  try {
    execSync("git --version", { encoding: "utf8" });
    results.push({ name: "Git", status: "pass", message: "설치됨", required: true });
  } catch {
    results.push({ name: "Git", status: "fail", message: "미설치", required: true });
  }

  // 디스크 여유 공간
  const freeGB = Math.round(os.freemem() / (1024 ** 3));
  results.push({
    name: "메모리",
    status: freeGB >= 8 ? "pass" : freeGB >= 4 ? "warn" : "fail",
    message: `${freeGB}GB 가용 / ${Math.round(os.totalmem() / (1024 ** 3))}GB 전체`,
    required: true,
  });

  return results;
}

// ═══════════════════════════════════════════════════════════
// §4. 프로젝트 초기화
// ═══════════════════════════════════════════════════════════

function initProject() {
  header("NARA-AI 프로젝트 초기화");

  // 디렉토리 구조 생성
  const dirs = [
    "src/models/base",          // 베이스 모델 (Solar, EXAONE, Qwen)
    "src/models/finetuned",     // 파인튜닝 모델 산출물
    "src/models/configs",       // 학습 설정 (YAML)
    "src/agents/classifier",    // 기록물 분류 에이전트
    "src/agents/metadata",      // 메타데이터 생성 에이전트
    "src/agents/redaction",     // 공개재분류 에이전트
    "src/agents/search",        // 검색 에이전트
    "src/agents/quality",       // 품질 검증 에이전트
    "src/agents/orchestrator",  // LangGraph 오케스트레이터
    "src/ocr/pipeline",         // OCR 파이프라인
    "src/ocr/models",           // OCR 모델 (Qwen3-VL, TrOCR, PaddleOCR)
    "src/ocr/postprocess",      // OCR 후처리
    "src/search/milvus",        // Milvus 벡터 DB 연동
    "src/search/embedding",     // 임베딩 모델 (BGE-M3-Korean)
    "src/search/rag",           // RAG 파이프라인
    "src/pipeline/ingest",      // 데이터 수집
    "src/pipeline/preprocess",  // 전처리
    "src/pipeline/train",       // 학습 파이프라인
    "src/pipeline/eval",        // 평가 파이프라인
    "src/pipeline/serve",       // 서빙 (vLLM)
    "src/mcp-servers/ramp",     // RAMP 연동 MCP
    "src/mcp-servers/archive",  // 기록관리 MCP (ARAM-ADK 래핑)
    "src/mcp-servers/iarna",    // IARNA Property Graph MCP
    "src/mcp-servers/nara",     // NARA-CLAW MCP (5개 통합)
    "src/mcp-servers/law",      // 법령 검색 MCP (기록이 AI 래핑)
    "src/standards/ric-cm",     // RiC-CM 1.0 매핑
    "src/standards/isadg",      // ISAD(G) 기술 요소
    "src/standards/iso15489",   // ISO 15489 준수 검증
    "data/raw/electronic",      // 전자기록물 원본
    "data/raw/non-electronic",  // 비전자기록물 스캔 이미지
    "data/raw/ocr-gt",          // OCR Ground Truth
    "data/processed/tokens",    // 토큰화 데이터
    "data/processed/sft",       // SFT 학습 데이터
    "data/processed/dpo",       // DPO 정렬 데이터
    "data/embeddings",          // 벡터 임베딩
    "tests/unit",
    "tests/integration",
    "tests/benchmark",
    "tests/security",           // NextSAST 연동 보안 테스트
    "infra/docker",
    "infra/k8s",
    "infra/monitoring",         // Prometheus + Grafana
    "docs/tdd",                 // Technical Design Document
    "docs/prd",                 // Product Requirements Document
    "docs/api",                 // API 문서
    "docs/reports",             // 성과 보고서
    "logs",
    "checkpoints",              // 학습 체크포인트
  ];

  dirs.forEach(d => {
    const fullPath = path.join(PROJECT_ROOT, d);
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true });
      log("📁", `${d}/`, COLORS.dim);
    }
  });
  log("✅", `${dirs.length}개 디렉토리 생성 완료`, COLORS.green);

  // 시스템 점검
  header("시스템 요구사항 검증");
  const checks = checkSystem();
  let failCount = 0;
  checks.forEach(c => {
    const icon = c.status === "pass" ? "✅" : c.status === "warn" ? "⚠️" : "❌";
    const color = c.status === "pass" ? COLORS.green : c.status === "warn" ? COLORS.yellow : COLORS.red;
    log(icon, `${c.name}: ${c.message}`, color);
    if (c.status === "fail" && c.required) failCount++;
  });

  if (failCount > 0) {
    log("❌", `필수 요구사항 ${failCount}개 미충족 — 설치 후 재시도하세요`, COLORS.red);
  } else {
    log("✅", "모든 필수 요구사항 충족", COLORS.green);
  }

  // 기존 자산 현황
  header("기존 자산 레지스트리 (10개 프로젝트)");
  let totalLoc = 0, totalApis = 0, totalAgents = 0, totalTests = 0, totalMcp = 0;
  LEGACY_ASSETS.forEach((a, i) => {
    const locNum = parseInt(a.loc.replace(/[^0-9]/g, ""));
    totalLoc += locNum;
    totalApis += a.apis;
    totalAgents += a.agents;
    totalTests += a.tests;
    totalMcp += a.mcpTools;

    console.log(`${COLORS.cyan}  ${String(i + 1).padStart(2)}. ${COLORS.bold}${a.name}${COLORS.reset} ${COLORS.dim}v${a.version} [${a.lang}]${COLORS.reset}`);
    console.log(`      ${COLORS.dim}${a.loc} LOC · ${a.apis || "-"} API · ${a.agents || "-"} Agents · ${a.tests || "-"} Tests · ${a.mcpTools || "-"} MCP${COLORS.reset}`);
    console.log(`      ${COLORS.yellow}역할: ${a.role}${COLORS.reset}`);
    console.log(`      ${COLORS.magenta}통합: ${a.integration}${COLORS.reset}\n`);
  });

  console.log(`${COLORS.bgGreen}${COLORS.white}${COLORS.bold}`);
  console.log(`  ═══════════════════════════════════════════════════════`);
  console.log(`   총계: ${totalLoc.toLocaleString()}+ LOC · ${totalApis} API · ${totalAgents} Agents`);
  console.log(`          ${totalTests} Tests · ${totalMcp} MCP Tools`);
  console.log(`  ═══════════════════════════════════════════════════════`);
  console.log(`${COLORS.reset}\n`);
}

// ═══════════════════════════════════════════════════════════
// §5. 모델 학습 파이프라인
// ═══════════════════════════════════════════════════════════

interface TrainConfig {
  phase: "cpt" | "sft" | "dpo";
  baseModel: string;
  dataPath: string;
  outputDir: string;
  gpuCount: number;
  framework: "deepspeed" | "fsdp2" | "qlora";
  batchSize: number;
  epochs: number;
  lr: number;
  maxSeqLen: number;
}

const TRAIN_PRESETS: Record<string, TrainConfig> = {
  "cpt-exaone-8b": {
    phase: "cpt",
    baseModel: "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
    dataPath: "data/processed/tokens/gov-corpus-100B",
    outputDir: "checkpoints/cpt-exaone-8b",
    gpuCount: 16,
    framework: "fsdp2",
    batchSize: 32,
    epochs: 1,
    lr: 2e-5,
    maxSeqLen: 8192,
  },
  "sft-classifier": {
    phase: "sft",
    baseModel: "checkpoints/cpt-exaone-8b/final",
    dataPath: "data/processed/sft/classification-50k.jsonl",
    outputDir: "checkpoints/sft-classifier",
    gpuCount: 8,
    framework: "qlora",
    batchSize: 16,
    epochs: 3,
    lr: 1e-4,
    maxSeqLen: 4096,
  },
  "sft-metadata": {
    phase: "sft",
    baseModel: "checkpoints/cpt-exaone-8b/final",
    dataPath: "data/processed/sft/metadata-gen-30k.jsonl",
    outputDir: "checkpoints/sft-metadata",
    gpuCount: 8,
    framework: "qlora",
    batchSize: 16,
    epochs: 3,
    lr: 1e-4,
    maxSeqLen: 4096,
  },
  "sft-redaction": {
    phase: "sft",
    baseModel: "checkpoints/cpt-exaone-8b/final",
    dataPath: "data/processed/sft/redaction-20k.jsonl",
    outputDir: "checkpoints/sft-redaction",
    gpuCount: 8,
    framework: "qlora",
    batchSize: 8,
    epochs: 5,
    lr: 5e-5,
    maxSeqLen: 8192,
  },
  "dpo-alignment": {
    phase: "dpo",
    baseModel: "checkpoints/sft-classifier/final",
    dataPath: "data/processed/dpo/expert-feedback-5k.jsonl",
    outputDir: "checkpoints/dpo-aligned",
    gpuCount: 8,
    framework: "deepspeed",
    batchSize: 4,
    epochs: 1,
    lr: 5e-7,
    maxSeqLen: 4096,
  },
  "ocr-qwen3vl": {
    phase: "sft",
    baseModel: "Qwen/Qwen3-VL-8B",
    dataPath: "data/processed/sft/ocr-korean-archive-100k.jsonl",
    outputDir: "checkpoints/ocr-qwen3vl",
    gpuCount: 4,
    framework: "qlora",
    batchSize: 4,
    epochs: 3,
    lr: 2e-5,
    maxSeqLen: 4096,
  },
};

function generateTrainScript(preset: string): string {
  const cfg = TRAIN_PRESETS[preset];
  if (!cfg) return `❌ 프리셋 "${preset}" 없음. 가능: ${Object.keys(TRAIN_PRESETS).join(", ")}`;

  if (cfg.framework === "qlora") {
    return `#!/bin/bash
# NARA-AI Training: ${preset}
# Phase: ${cfg.phase.toUpperCase()} | GPU: ${cfg.gpuCount}x B200 | Framework: QLoRA+DoRA

export CUDA_VISIBLE_DEVICES=$(seq -s, 0 $((${cfg.gpuCount}-1)))

python3 -m torch.distributed.launch \\
  --nproc_per_node=${cfg.gpuCount} \\
  src/pipeline/train/qlora_trainer.py \\
  --model_name_or_path ${cfg.baseModel} \\
  --data_path ${cfg.dataPath} \\
  --output_dir ${cfg.outputDir} \\
  --load_in_4bit True \\
  --use_dora True \\
  --lora_r 16 \\
  --lora_alpha 32 \\
  --lora_target_modules "all-linear" \\
  --per_device_train_batch_size ${cfg.batchSize} \\
  --num_train_epochs ${cfg.epochs} \\
  --learning_rate ${cfg.lr} \\
  --max_seq_length ${cfg.maxSeqLen} \\
  --bf16 True \\
  --gradient_checkpointing True \\
  --logging_steps 10 \\
  --save_strategy epoch \\
  --evaluation_strategy epoch \\
  --report_to wandb \\
  --run_name "nara-ai-${preset}" \\
  --seed 42

echo "✅ ${preset} 학습 완료 → ${cfg.outputDir}"
`;
  }

  if (cfg.framework === "fsdp2") {
    return `#!/bin/bash
# NARA-AI Training: ${preset}
# Phase: ${cfg.phase.toUpperCase()} | GPU: ${cfg.gpuCount}x B200 | Framework: FSDP2 (TorchTitan)

torchrun --nproc_per_node=${cfg.gpuCount} \\
  --nnodes=\${NUM_NODES:-1} \\
  --rdzv_backend=c10d \\
  --rdzv_endpoint=\${MASTER_ADDR:-localhost}:\${MASTER_PORT:-29500} \\
  src/pipeline/train/fsdp2_trainer.py \\
  --model_name_or_path ${cfg.baseModel} \\
  --data_path ${cfg.dataPath} \\
  --output_dir ${cfg.outputDir} \\
  --fsdp_strategy "FULL_SHARD" \\
  --fsdp_cpu_offload False \\
  --per_device_train_batch_size ${cfg.batchSize} \\
  --num_train_epochs ${cfg.epochs} \\
  --learning_rate ${cfg.lr} \\
  --max_seq_length ${cfg.maxSeqLen} \\
  --bf16 True \\
  --gradient_checkpointing True \\
  --async_checkpoint True \\
  --logging_steps 10 \\
  --save_strategy epoch \\
  --report_to wandb \\
  --run_name "nara-ai-${preset}" \\
  --seed 42

echo "✅ ${preset} 학습 완료 → ${cfg.outputDir}"
`;
  }

  // DeepSpeed
  return `#!/bin/bash
# NARA-AI Training: ${preset}
# Phase: ${cfg.phase.toUpperCase()} | GPU: ${cfg.gpuCount}x B200 | Framework: DeepSpeed ZeRO-3

deepspeed --num_gpus=${cfg.gpuCount} \\
  src/pipeline/train/ds_trainer.py \\
  --deepspeed config/ds_zero3.json \\
  --model_name_or_path ${cfg.baseModel} \\
  --data_path ${cfg.dataPath} \\
  --output_dir ${cfg.outputDir} \\
  --per_device_train_batch_size ${cfg.batchSize} \\
  --num_train_epochs ${cfg.epochs} \\
  --learning_rate ${cfg.lr} \\
  --max_seq_length ${cfg.maxSeqLen} \\
  --bf16 True \\
  --gradient_checkpointing True \\
  --logging_steps 10 \\
  --save_strategy epoch \\
  --report_to wandb \\
  --run_name "nara-ai-${preset}" \\
  --seed 42

echo "✅ ${preset} 학습 완료 → ${cfg.outputDir}"
`;
}

// ═══════════════════════════════════════════════════════════
// §6. 서빙 (vLLM + MCP 서버)
// ═══════════════════════════════════════════════════════════

interface ServeConfig {
  name: string;
  type: "vllm" | "mcp" | "embedding" | "vector-db";
  port: number;
  model?: string;
  gpuMemoryUtilization?: number;
  command: string;
}

const SERVE_CONFIGS: ServeConfig[] = [
  {
    name: "nara-llm",
    type: "vllm",
    port: 8000,
    model: "checkpoints/sft-classifier/final",
    gpuMemoryUtilization: 0.9,
    command: `vllm serve checkpoints/sft-classifier/final \\
  --port 8000 --host 0.0.0.0 \\
  --tensor-parallel-size 2 \\
  --gpu-memory-utilization 0.9 \\
  --max-model-len 8192 \\
  --enable-auto-tool-choice \\
  --served-model-name nara-classifier`,
  },
  {
    name: "nara-ocr",
    type: "vllm",
    port: 8001,
    model: "checkpoints/ocr-qwen3vl/final",
    command: `vllm serve checkpoints/ocr-qwen3vl/final \\
  --port 8001 --host 0.0.0.0 \\
  --max-model-len 4096 \\
  --served-model-name nara-ocr`,
  },
  {
    name: "embedding",
    type: "embedding",
    port: 8002,
    model: "upskyy/bge-m3-korean",
    command: `python3 src/search/embedding/server.py \\
  --model upskyy/bge-m3-korean \\
  --port 8002 --batch-size 64`,
  },
  {
    name: "milvus",
    type: "vector-db",
    port: 19530,
    command: `docker compose -f infra/docker/milvus.yml up -d`,
  },
  {
    name: "mcp-archive",
    type: "mcp",
    port: 3001,
    command: `npx tsx src/mcp-servers/archive/index.ts`,
  },
  {
    name: "mcp-iarna",
    type: "mcp",
    port: 3002,
    command: `npx tsx src/mcp-servers/iarna/index.ts`,
  },
  {
    name: "mcp-nara",
    type: "mcp",
    port: 3003,
    command: `npx tsx src/mcp-servers/nara/index.ts`,
  },
  {
    name: "mcp-law",
    type: "mcp",
    port: 3004,
    command: `npx tsx src/mcp-servers/law/index.ts`,
  },
  {
    name: "mcp-ramp",
    type: "mcp",
    port: 3005,
    command: `npx tsx src/mcp-servers/ramp/index.ts`,
  },
  {
    name: "orchestrator",
    type: "mcp",
    port: 8080,
    command: `python3 src/agents/orchestrator/main.py \\
  --port 8080 --mcp-registry config/mcp-registry.json`,
  },
];

// ═══════════════════════════════════════════════════════════
// §7. OCR + 분류 + 메타데이터 전체 파이프라인
// ═══════════════════════════════════════════════════════════

interface PipelineStep {
  name: string;
  description: string;
  command: string;
  dependsOn: string[];
  estimatedTime: string;
  gpuRequired: boolean;
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    name: "ingest",
    description: "원본 기록물 수집 및 포맷 정규화",
    command: "python3 src/pipeline/ingest/collector.py --source /data/archive --output data/raw/",
    dependsOn: [],
    estimatedTime: "입력 규모에 비례",
    gpuRequired: false,
  },
  {
    name: "layout-analysis",
    description: "문서 레이아웃 분석 (YOLO-DocLayout)",
    command: "python3 src/ocr/pipeline/layout_analyzer.py --input data/raw/ --output data/processed/layouts/",
    dependsOn: ["ingest"],
    estimatedTime: "~500 pages/min (1 GPU)",
    gpuRequired: true,
  },
  {
    name: "ocr-extraction",
    description: "문자 인식 (Qwen3-VL + PaddleOCR + TrOCR 앙상블)",
    command: "python3 src/ocr/pipeline/ocr_ensemble.py --layouts data/processed/layouts/ --output data/processed/ocr/",
    dependsOn: ["layout-analysis"],
    estimatedTime: "~1,500 pages/hr (8 GPU)",
    gpuRequired: true,
  },
  {
    name: "ocr-postprocess",
    description: "OCR 결과 후처리 (맞춤법, 한자 변환, 신뢰도 필터링)",
    command: "python3 src/ocr/postprocess/corrector.py --input data/processed/ocr/ --output data/processed/ocr-clean/",
    dependsOn: ["ocr-extraction"],
    estimatedTime: "~5min/10K pages",
    gpuRequired: false,
  },
  {
    name: "classify",
    description: "기록물 자동 분류 (BRM 단위과제 매핑)",
    command: "python3 src/agents/classifier/batch_classify.py --input data/processed/ocr-clean/ --model nara-classifier",
    dependsOn: ["ocr-postprocess"],
    estimatedTime: "~10K records/min",
    gpuRequired: true,
  },
  {
    name: "metadata-gen",
    description: "메타데이터 자동 생성 (제목, 요약, 키워드, NER)",
    command: "python3 src/agents/metadata/batch_generate.py --input data/processed/ocr-clean/ --model nara-metadata",
    dependsOn: ["classify"],
    estimatedTime: "~5K records/min",
    gpuRequired: true,
  },
  {
    name: "redaction-check",
    description: "공개재분류 AI 심사 (개인정보·비공개정보 탐지)",
    command: "python3 src/agents/redaction/batch_review.py --input data/processed/ocr-clean/ --model nara-redaction",
    dependsOn: ["metadata-gen"],
    estimatedTime: "~3K records/min",
    gpuRequired: true,
  },
  {
    name: "embed",
    description: "벡터 임베딩 생성 (BGE-M3-Korean) → Milvus 적재",
    command: "python3 src/search/embedding/batch_embed.py --input data/processed/ocr-clean/ --milvus localhost:19530",
    dependsOn: ["metadata-gen"],
    estimatedTime: "~50K records/hr",
    gpuRequired: true,
  },
  {
    name: "graph-build",
    description: "지식그래프 구축 (RiC-CM Property Graph → Cloud Spanner)",
    command: "npx tsx src/standards/ric-cm/graph_builder.ts --input data/processed/metadata/ --spanner iarna-db",
    dependsOn: ["metadata-gen"],
    estimatedTime: "~20K records/hr",
    gpuRequired: false,
  },
  {
    name: "quality-gate",
    description: "품질 검증 (메타데이터 완전성, 분류 적정성, OCR 정확도)",
    command: "python3 src/agents/quality/batch_verify.py --input data/processed/ --threshold 0.85",
    dependsOn: ["classify", "metadata-gen", "redaction-check"],
    estimatedTime: "~10min",
    gpuRequired: false,
  },
  {
    name: "security-scan",
    description: "보안 점검 (NextSAST 연동 — PII 탐지, 모델 보안 감사)",
    command: "python3 src/pipeline/eval/security_scan.py --target data/processed/ --nextsast-api http://localhost:8080",
    dependsOn: ["quality-gate"],
    estimatedTime: "~5min",
    gpuRequired: false,
  },
];

// ═══════════════════════════════════════════════════════════
// §8. 벤치마크 및 평가
// ═══════════════════════════════════════════════════════════

interface BenchmarkTask {
  name: string;
  nameKr: string;
  metric: string;
  target: string;
  dataset: string;
  command: string;
}

const BENCHMARKS: BenchmarkTask[] = [
  {
    name: "classification-accuracy",
    nameKr: "기록물 분류 정확도",
    metric: "F1 Score (macro)",
    target: ">= 0.92",
    dataset: "data/processed/eval/classify-test-5k.jsonl",
    command: "python3 src/pipeline/eval/eval_classifier.py",
  },
  {
    name: "metadata-quality",
    nameKr: "메타데이터 생성 품질",
    metric: "ROUGE-1 F1",
    target: ">= 0.85",
    dataset: "data/processed/eval/metadata-test-2k.jsonl",
    command: "python3 src/pipeline/eval/eval_metadata.py",
  },
  {
    name: "ocr-cer",
    nameKr: "OCR 문자오류율 (인쇄체)",
    metric: "CER",
    target: "<= 0.03 (3%)",
    dataset: "data/raw/ocr-gt/printed-1k/",
    command: "python3 src/pipeline/eval/eval_ocr.py --type printed",
  },
  {
    name: "ocr-cer-handwritten",
    nameKr: "OCR 문자오류율 (필기체)",
    metric: "CER",
    target: "<= 0.10 (10%)",
    dataset: "data/raw/ocr-gt/handwritten-500/",
    command: "python3 src/pipeline/eval/eval_ocr.py --type handwritten",
  },
  {
    name: "ocr-cer-hanja",
    nameKr: "OCR 문자오류율 (한자 혼용)",
    metric: "CER",
    target: "<= 0.07 (7%)",
    dataset: "data/raw/ocr-gt/hanja-500/",
    command: "python3 src/pipeline/eval/eval_ocr.py --type hanja",
  },
  {
    name: "redaction-precision",
    nameKr: "공개재분류 정밀도",
    metric: "Precision (비공개 판별)",
    target: ">= 0.95",
    dataset: "data/processed/eval/redaction-test-3k.jsonl",
    command: "python3 src/pipeline/eval/eval_redaction.py",
  },
  {
    name: "search-recall",
    nameKr: "검색 재현율",
    metric: "Recall@10",
    target: ">= 0.90",
    dataset: "data/processed/eval/search-queries-500.jsonl",
    command: "python3 src/pipeline/eval/eval_search.py",
  },
  {
    name: "retention-accuracy",
    nameKr: "보존기간 산정 정확도",
    metric: "Exact Match",
    target: ">= 0.88",
    dataset: "data/processed/eval/retention-test-1k.jsonl",
    command: "python3 src/pipeline/eval/eval_retention.py",
  },
  {
    name: "throughput",
    nameKr: "전체 파이프라인 처리량",
    metric: "pages/hour",
    target: ">= 1,500 (16 GPU)",
    dataset: "data/raw/benchmark-batch-10k/",
    command: "python3 src/pipeline/eval/benchmark_throughput.py",
  },
  {
    name: "latency-p99",
    nameKr: "검색 응답 지연시간",
    metric: "P99 Latency",
    target: "<= 2s",
    dataset: "data/processed/eval/search-queries-500.jsonl",
    command: "python3 src/pipeline/eval/benchmark_latency.py",
  },
];

// ═══════════════════════════════════════════════════════════
// §9. 성과 보고서 생성
// ═══════════════════════════════════════════════════════════

function generateReportTemplate(): string {
  const date = new Date().toISOString().split("T")[0];
  return `# NARA-AI 과제 성과 보고서
## 국가 AI 프로젝트 · AI 기반 국가기록물 지능형 검색·분류·활용 체계 구축

**보고일**: ${date}
**과제 기간**: 2027.01 ~ 2028.12 (2개년)
**주관**: 행정안전부 / 국가기록원
**GPU 배분**: B200 ___장

---

### 1. 핵심 성과 지표 (KPI)

| 지표 | 목표 | 달성 | 상태 |
|------|------|------|------|
${BENCHMARKS.map(b => `| ${b.nameKr} | ${b.target} | ___ | ⬜ |`).join("\n")}

### 2. GPU 활용 현황

| 월 | 학습 시간(hr) | 추론 시간(hr) | 유휴 시간(hr) | 활용률 |
|---|---|---|---|---|
| 1월 | ___ | ___ | ___ | ___% |

### 3. 데이터 처리 현황

| 항목 | 목표 | 처리량 |
|------|------|--------|
| 전자기록물 공개재분류 | 2억 9천만 건 | ___ 건 |
| 비전자기록물 OCR | 100만 페이지 | ___ 페이지 |
| 벡터 임베딩 적재 | 1,000만 건 | ___ 건 |
| 지식그래프 노드 | 500만 | ___ |

### 4. 모델 산출물

| 모델 | 베이스 | 파라미터 | 학습 데이터 | 성능 |
|------|--------|---------|-----------|------|
| NARA-Classifier | EXAONE 3.5 8B | 7.8B + LoRA | 50K 분류 쌍 | F1 ___ |
| NARA-MetaGen | EXAONE 3.5 8B | 7.8B + LoRA | 30K 메타 쌍 | ROUGE ___ |
| NARA-Redaction | EXAONE 3.5 8B | 7.8B + LoRA | 20K 심사 쌍 | Prec ___ |
| NARA-OCR | Qwen3-VL 8B | 8B + LoRA | 100K 이미지-텍스트 | CER ___ |

### 5. 기존 자산 활용 실적

${LEGACY_ASSETS.map(a => `- **${a.name}** v${a.version}: ${a.role}`).join("\n")}

---

*본 보고서는 NARA-AI Harness v${VERSION}에 의해 자동 생성되었습니다.*
`;
}

// ═══════════════════════════════════════════════════════════
// §10. CLI 엔트리포인트
// ═══════════════════════════════════════════════════════════

function showBanner() {
  console.log(`
${COLORS.cyan}${COLORS.bold}
  ███╗   ██╗ █████╗ ██████╗  █████╗        █████╗ ██╗
  ████╗  ██║██╔══██╗██╔══██╗██╔══██╗      ██╔══██╗██║
  ██╔██╗ ██║███████║██████╔╝███████║█████╗███████║██║
  ██║╚██╗██║██╔══██║██╔══██╗██╔══██║╚════╝██╔══██║██║
  ██║ ╚████║██║  ██║██║  ██║██║  ██║      ██║  ██║██║
  ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝      ╚═╝  ╚═╝╚═╝
${COLORS.reset}
${COLORS.dim}  AI 기반 국가기록물 지능형 검색·분류·활용 체계 구축
  행정안전부 / 국가기록원 · 국가 AI 프로젝트 GPU 지원 과제
  Harness v${VERSION}${COLORS.reset}
`);
}

function showHelp() {
  console.log(`
${COLORS.bold}사용법:${COLORS.reset}
  npx tsx harness/harness.ts <command> [options]

${COLORS.bold}명령어:${COLORS.reset}
  ${COLORS.cyan}init${COLORS.reset}              프로젝트 초기화 (디렉토리·의존성·환경 점검)
  ${COLORS.cyan}check${COLORS.reset}             시스템 요구사항 헬스체크
  ${COLORS.cyan}train${COLORS.reset} <preset>    모델 학습 (presets: ${Object.keys(TRAIN_PRESETS).join(", ")})
  ${COLORS.cyan}serve${COLORS.reset}             추론 서비스 전체 기동
  ${COLORS.cyan}pipeline${COLORS.reset}          OCR + 분류 + 메타데이터 전체 파이프라인
  ${COLORS.cyan}eval${COLORS.reset}              모델 평가 및 벤치마크 (${BENCHMARKS.length}개 지표)
  ${COLORS.cyan}report${COLORS.reset}            과제 성과 보고서 생성
  ${COLORS.cyan}status${COLORS.reset}            전체 시스템 현황
  ${COLORS.cyan}assets${COLORS.reset}            기존 자산 레지스트리 조회

${COLORS.bold}학습 프리셋:${COLORS.reset}
${Object.entries(TRAIN_PRESETS).map(([k, v]) =>
  `  ${COLORS.yellow}${k.padEnd(22)}${COLORS.reset} ${v.phase.toUpperCase().padEnd(4)} ${v.baseModel.split("/").pop()} → ${v.framework} (${v.gpuCount} GPU)`
).join("\n")}

${COLORS.bold}서빙 서비스 (${SERVE_CONFIGS.length}개):${COLORS.reset}
${SERVE_CONFIGS.map(s =>
  `  ${COLORS.green}:${String(s.port).padEnd(6)}${COLORS.reset} ${s.name.padEnd(18)} [${s.type}]`
).join("\n")}

${COLORS.bold}벤치마크 (${BENCHMARKS.length}개):${COLORS.reset}
${BENCHMARKS.map(b =>
  `  ${COLORS.magenta}${b.name.padEnd(25)}${COLORS.reset} ${b.nameKr.padEnd(20)} 목표: ${b.target}`
).join("\n")}
`);
}

// ── Main ──
const command = process.argv[2];
const arg = process.argv[3];

showBanner();

switch (command) {
  case "init":
    initProject();
    break;

  case "check":
    header("시스템 헬스체크");
    checkSystem().forEach(c => {
      const icon = c.status === "pass" ? "✅" : c.status === "warn" ? "⚠️" : "❌";
      log(icon, `${c.name}: ${c.message}`);
    });
    break;

  case "train":
    if (!arg) {
      log("❌", `프리셋을 지정하세요: ${Object.keys(TRAIN_PRESETS).join(", ")}`, COLORS.red);
    } else {
      header(`모델 학습: ${arg}`);
      const script = generateTrainScript(arg);
      const scriptPath = path.join(PROJECT_ROOT, `scripts/train-${arg}.sh`);
      fs.writeFileSync(scriptPath, script);
      fs.chmodSync(scriptPath, "755");
      log("📝", `학습 스크립트 생성: ${scriptPath}`, COLORS.green);
      console.log(`\n${COLORS.dim}${script}${COLORS.reset}`);
      log("🚀", `실행: bash ${scriptPath}`, COLORS.cyan);
    }
    break;

  case "serve":
    header("추론 서비스 구성");
    SERVE_CONFIGS.forEach(s => {
      log("🔧", `${s.name} [:${s.port}] — ${s.type}`, COLORS.cyan);
      console.log(`    ${COLORS.dim}${s.command}${COLORS.reset}\n`);
    });
    log("💡", "전체 기동: bash scripts/start-all.sh", COLORS.yellow);
    break;

  case "pipeline":
    header("전체 파이프라인 (11단계)");
    PIPELINE_STEPS.forEach((s, i) => {
      const gpu = s.gpuRequired ? "🔥GPU" : "💻CPU";
      log(`${String(i + 1).padStart(2)}.`, `${s.name} — ${s.description} [${gpu}] ~${s.estimatedTime}`, COLORS.cyan);
      if (s.dependsOn.length > 0) {
        console.log(`      ${COLORS.dim}의존: ${s.dependsOn.join(" → ")}${COLORS.reset}`);
      }
    });
    break;

  case "eval":
    header(`벤치마크 (${BENCHMARKS.length}개 지표)`);
    BENCHMARKS.forEach(b => {
      log("📊", `${b.nameKr} [${b.metric}] 목표: ${b.target}`, COLORS.magenta);
      console.log(`    ${COLORS.dim}$ ${b.command}${COLORS.reset}\n`);
    });
    break;

  case "report":
    header("성과 보고서 생성");
    const reportPath = path.join(PROJECT_ROOT, `docs/reports/report-${new Date().toISOString().split("T")[0]}.md`);
    fs.writeFileSync(reportPath, generateReportTemplate());
    log("📄", `보고서 생성: ${reportPath}`, COLORS.green);
    break;

  case "assets":
    header("기존 자산 레지스트리");
    LEGACY_ASSETS.forEach((a, i) => {
      console.log(`${COLORS.cyan}  ${String(i + 1).padStart(2)}. ${COLORS.bold}${a.name}${COLORS.reset} ${COLORS.dim}v${a.version}${COLORS.reset}`);
      console.log(`      ${a.role}`);
      console.log(`      ${COLORS.magenta}→ ${a.integration}${COLORS.reset}\n`);
    });
    break;

  case "status":
    header("시스템 현황");
    log("📦", `프로젝트: ${PROJECT_NAME} v${VERSION}`, COLORS.white);
    log("📂", `루트: ${PROJECT_ROOT}`, COLORS.white);
    log("💻", `OS: ${os.platform()} ${os.release()} (${os.arch()})`, COLORS.white);
    log("🧠", `RAM: ${Math.round(os.totalmem() / (1024 ** 3))}GB`, COLORS.white);
    log("⏰", `시각: ${new Date().toLocaleString("ko-KR")}`, COLORS.white);
    log("📊", `자산: ${LEGACY_ASSETS.length}개 · ${BENCHMARKS.length}개 벤치마크`, COLORS.white);
    log("🔧", `서비스: ${SERVE_CONFIGS.length}개 구성`, COLORS.white);
    log("🏋️", `학습 프리셋: ${Object.keys(TRAIN_PRESETS).length}개`, COLORS.white);
    log("🔄", `파이프라인: ${PIPELINE_STEPS.length}단계`, COLORS.white);
    break;

  default:
    showHelp();
}
