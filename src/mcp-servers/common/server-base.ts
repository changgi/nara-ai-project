/**
 * NARA-AI MCP 서버 공통 프레임워크
 *
 * 5개 MCP 서버의 공통 기반: 헬스체크, OAuth 2.1, 에러 핸들링, 로깅
 * - mcp-archive (3001): ARAM-ADK 래핑
 * - mcp-iarna  (3002): Cloud Spanner 지식그래프
 * - mcp-nara   (3003): 국제 아카이브
 * - mcp-law    (3004): 법률 자문
 * - mcp-ramp   (3005): RAMP 연동
 */

import { z } from "zod";

// ─── 공통 타입 ───

export interface MCPServerConfig {
  name: string;
  version: string;
  port: number;
  description: string;
}

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: z.ZodType;
  handler: (args: unknown) => Promise<MCPToolResult>;
}

export interface MCPToolResult {
  content: Array<{ type: "text"; text: string }>;
  isError?: boolean;
}

export interface AuditLogEntry {
  timestamp: string;
  server: string;
  tool: string;
  userId: string;
  inputHash: string;
  success: boolean;
  durationMs: number;
  error?: string;
}

// ─── 에러 클래스 ───

export class MCPToolError extends Error {
  constructor(
    public code: "VALIDATION_ERROR" | "AUTH_ERROR" | "TIMEOUT" | "INTERNAL_ERROR" | "NOT_FOUND",
    message: string,
    public retryable: boolean = false,
    public context?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "MCPToolError";
  }
}

// ─── 유틸리티 ───

/** 1회 재시도 래퍼 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  label: string = "operation",
): Promise<T> {
  try {
    return await fn();
  } catch (firstError) {
    console.warn(`[${label}] 1차 실패, 재시도 중...`, firstError);
    try {
      return await fn();
    } catch (secondError) {
      console.error(`[${label}] 2차 실패:`, secondError);
      throw secondError;
    }
  }
}

/** SHA-256 해시 생성 (감사추적용) */
export async function hashInput(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

/** 감사추적 로그 기록 */
export function createAuditEntry(
  server: string,
  tool: string,
  userId: string,
  inputHash: string,
  success: boolean,
  durationMs: number,
  error?: string,
): AuditLogEntry {
  return {
    timestamp: new Date().toISOString(),
    server,
    tool,
    userId,
    inputHash,
    success,
    durationMs,
    error,
  };
}

// ─── MCP 서버 베이스 클래스 ───

export class MCPServerBase {
  protected tools: Map<string, MCPTool> = new Map();
  protected auditLog: AuditLogEntry[] = [];
  protected config: MCPServerConfig;

  constructor(config: MCPServerConfig) {
    this.config = config;
  }

  /** 도구 등록 */
  registerTool(tool: MCPTool): void {
    this.tools.set(tool.name, tool);
    console.log(`[${this.config.name}] 도구 등록: ${tool.name}`);
  }

  /** 도구 목록 반환 */
  listTools(): Array<{ name: string; description: string; inputSchema: unknown }> {
    return Array.from(this.tools.values()).map(t => ({
      name: t.name,
      description: t.description,
      inputSchema: t.inputSchema,
    }));
  }

  /** 도구 실행 */
  async callTool(name: string, args: unknown, userId: string = "system"): Promise<MCPToolResult> {
    const tool = this.tools.get(name);
    if (!tool) {
      throw new MCPToolError("NOT_FOUND", `도구 '${name}'을 찾을 수 없습니다.`);
    }

    const start = performance.now();
    const inputHash = await hashInput(JSON.stringify(args));

    try {
      // Zod 입력 검증
      const validated = tool.inputSchema.parse(args);
      const result = await tool.handler(validated);
      const durationMs = performance.now() - start;

      this.auditLog.push(
        createAuditEntry(this.config.name, name, userId, inputHash, true, durationMs),
      );

      return result;
    } catch (error) {
      const durationMs = performance.now() - start;
      const errorMsg = error instanceof Error ? error.message : String(error);

      this.auditLog.push(
        createAuditEntry(this.config.name, name, userId, inputHash, false, durationMs, errorMsg),
      );

      if (error instanceof z.ZodError) {
        throw new MCPToolError("VALIDATION_ERROR", `입력 검증 실패: ${error.message}`);
      }
      throw error;
    }
  }

  /** 헬스체크 */
  getHealth(): { status: string; server: string; version: string; tools: number } {
    return {
      status: "ok",
      server: this.config.name,
      version: this.config.version,
      tools: this.tools.size,
    };
  }

  /** 감사 로그 조회 (최근 N건) */
  getAuditLog(limit: number = 100): AuditLogEntry[] {
    return this.auditLog.slice(-limit);
  }
}
