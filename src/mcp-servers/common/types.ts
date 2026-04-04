/**
 * NARA-AI MCP 서버 공통 타입 정의
 */

import { z } from "zod";

// ─── 기록물 관련 타입 ───

export const RecordTypeSchema = z.enum([
  "electronic",
  "paper",
  "photo",
  "microfilm",
  "audio_video",
  "architectural",
  "map",
]);
export type RecordType = z.infer<typeof RecordTypeSchema>;

export const SecurityLevelSchema = z.enum([
  "public",
  "restricted",
  "secret",
  "top_secret",
]);
export type SecurityLevel = z.infer<typeof SecurityLevelSchema>;

// ─── BRM 업무기능 분류 ───

export const BRM_TOP_LEVEL: Record<string, string> = {
  A: "일반공공행정",
  B: "공공질서및안전",
  C: "통일외교",
  D: "국방",
  E: "교육",
  F: "문화및관광",
  G: "환경",
  H: "사회복지",
  I: "보건",
  J: "농림해양수산",
  K: "산업중소기업에너지",
  L: "교통및물류",
  M: "통신",
  N: "국토및지역개발",
  O: "과학기술",
  P: "재정금융",
};

// ─── 보존기간 ───

export const RetentionPeriods = z.enum([
  "1년", "3년", "5년", "10년", "30년", "영구",
]);
export type RetentionPeriod = z.infer<typeof RetentionPeriods>;

// ─── MCP 도구 응답 ───

export interface ToolResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
  durationMs: number;
}

// ─── 검색 결과 ───

export const SearchResultSchema = z.object({
  id: z.string(),
  title: z.string(),
  contentPreview: z.string(),
  score: z.number(),
  recordGroup: z.string().optional(),
  agency: z.string().optional(),
  securityLevel: SecurityLevelSchema.optional(),
  dateCreated: z.string().optional(),
});
export type SearchResult = z.infer<typeof SearchResultSchema>;

// ─── 감사추적 ───

export const AuditEntrySchema = z.object({
  decisionId: z.string(),
  timestamp: z.string(),
  userId: z.string(),
  agentName: z.string(),
  action: z.string(),
  inputHash: z.string(),
  outputSummary: z.string(),
  confidence: z.number(),
  reasoning: z.string(),
  hitlRequired: z.boolean(),
  hitlDecision: z.string().nullable(),
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

// ─── 서비스 포트 매핑 ───

export const SERVICE_PORTS = {
  VLLM_LLM: 8000,
  VLLM_OCR: 8001,
  EMBEDDING: 8002,
  MILVUS: 19530,
  MCP_ARCHIVE: 3001,
  MCP_IARNA: 3002,
  MCP_NARA: 3003,
  MCP_LAW: 3004,
  MCP_RAMP: 3005,
  ORCHESTRATOR: 8080,
  PROMETHEUS: 9090,
  GRAFANA: 3000,
} as const;
