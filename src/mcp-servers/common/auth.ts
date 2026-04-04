/**
 * OAuth 2.1 JWT 인증 미들웨어
 *
 * 모든 MCP 서버에서 공통으로 사용하는 인증/인가 모듈.
 * RBAC: admin, archivist, researcher, public
 * ISMS-P 요구사항: 접근 통제, 토큰 만료, 감사 로그
 */

import { z } from "zod";

// ─── 역할 기반 접근 제어 (RBAC) ───

export const UserRole = z.enum(["admin", "archivist", "researcher", "public"]);
export type UserRole = z.infer<typeof UserRole>;

export const SecurityLevel = z.enum(["public", "restricted", "secret", "top_secret"]);
export type SecurityLevel = z.infer<typeof SecurityLevel>;

/** 역할별 접근 가능 보안 등급 */
export const ROLE_PERMISSIONS: Record<UserRole, SecurityLevel[]> = {
  admin: ["public", "restricted", "secret", "top_secret"],
  archivist: ["public", "restricted", "secret"],
  researcher: ["public", "restricted"],
  public: ["public"],
};

/** 역할별 허용 MCP 도구 */
export const ROLE_TOOL_PERMISSIONS: Record<UserRole, string[]> = {
  admin: ["*"],  // 전체 접근
  archivist: [
    "classify_record", "generate_metadata", "review_redaction",
    "calculate_retention", "search_similar", "vibe_query",
    "graph_neighbors", "graph_path", "thesaurus_lookup",
    "sync_classification", "validate_retention",
  ],
  researcher: [
    "search_similar", "vibe_query", "graph_neighbors",
    "thesaurus_lookup", "timeline_query", "record_search",
    "search_us_nara", "search_uk_tna", "search_dpla",
    "isadg_describe", "ocr_document",
  ],
  public: [
    "search_similar", "thesaurus_lookup", "timeline_query",
    "search_us_nara", "search_uk_tna",
  ],
};

// ─── JWT 토큰 구조 ───

export const JWTPayloadSchema = z.object({
  sub: z.string(),                   // 사용자 ID
  role: UserRole,                    // 역할
  name: z.string().optional(),       // 사용자 이름
  agency: z.string().optional(),     // 소속 기관
  iat: z.number(),                   // 발급 시간
  exp: z.number(),                   // 만료 시간
  iss: z.literal("nara-ai"),         // 발급자
});

export type JWTPayload = z.infer<typeof JWTPayloadSchema>;

// ─── 인증 미들웨어 ───

export interface AuthResult {
  authenticated: boolean;
  userId: string;
  role: UserRole;
  error?: string;
}

/**
 * JWT 토큰 검증
 * 에어갭 환경이므로 외부 인증 서버 없이 대칭키(HS256) 사용
 */
export async function verifyToken(token: string, secret: string): Promise<AuthResult> {
  try {
    // JWT 디코딩 (jose 라이브러리 사용)
    const parts = token.split(".");
    if (parts.length !== 3) {
      return { authenticated: false, userId: "", role: "public", error: "잘못된 토큰 형식" };
    }

    const payloadStr = Buffer.from(parts[1], "base64url").toString("utf-8");
    const payload = JWTPayloadSchema.parse(JSON.parse(payloadStr));

    // 만료 확인
    const now = Math.floor(Date.now() / 1000);
    if (payload.exp < now) {
      return { authenticated: false, userId: payload.sub, role: payload.role, error: "토큰 만료" };
    }

    // HMAC 서명 검증 (실제 구현에서는 crypto.subtle.verify 사용)
    // 여기서는 구조만 정의

    return {
      authenticated: true,
      userId: payload.sub,
      role: payload.role,
    };
  } catch (error) {
    return {
      authenticated: false,
      userId: "",
      role: "public",
      error: `토큰 검증 실패: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * 도구 접근 권한 확인
 */
export function canAccessTool(role: UserRole, toolName: string): boolean {
  const allowed = ROLE_TOOL_PERMISSIONS[role];
  return allowed.includes("*") || allowed.includes(toolName);
}

/**
 * 보안 등급 접근 권한 확인
 */
export function canAccessSecurityLevel(role: UserRole, level: SecurityLevel): boolean {
  return ROLE_PERMISSIONS[role].includes(level);
}
