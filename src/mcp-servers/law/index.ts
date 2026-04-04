/**
 * MCP Law Server (포트 3004)
 *
 * 공공기록물법 법률 자문 MCP 서버
 * 기록물 관리 관련 법률 해석, 보존기간 산정, 비밀해제 근거 제공
 * 6개 도구
 */

import { z } from "zod";
import { MCPServerBase, type MCPToolResult } from "../common/server-base.js";

const server = new MCPServerBase({
  name: "mcp-law",
  version: "1.0.0",
  port: 3004,
  description: "공공기록물법 법률 자문 MCP 서버 (6 tools)",
});

// 공공기록물법 핵심 조항
const RECORDS_ACT_ARTICLES: Record<string, string> = {
  "제6조": "기록물관리의 원칙 - 기록물의 진정성·무결성·신뢰성·이용가능성 보장",
  "제19조": "기록물의 생산의무 - 업무수행 과정에서 기록물 생산 의무",
  "제20조": "기록물의 등록·분류 - 생산 즉시 등록, 분류기준표에 따라 분류",
  "제21조": "기록물 이관 - 처리과에서 기록물관리기관으로 이관",
  "제26조": "기록물의 폐기 - 보존기간 경과 후 폐기 절차",
  "제33조": "비밀기록물의 관리 - 비밀 등급 부여 및 관리",
  "제34조": "비공개 기록물의 공개 - 30년 경과 시 원칙적 공개",
  "제35조": "기록물의 열람 - 국민의 기록물 열람권 보장",
  "제38조": "보존기간의 책정 - BRM 기반 보존기간 산정 기준",
};

server.registerTool({
  name: "lookup_article",
  description: "공공기록물법 특정 조항을 조회한다. 조항 번호와 해설을 반환한다.",
  inputSchema: z.object({
    article: z.string().describe("조항 번호 (예: '제34조')"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { article: string };
    const content = RECORDS_ACT_ARTICLES[input.article] || "해당 조항을 찾을 수 없습니다.";
    return { content: [{ type: "text", text: JSON.stringify({ article: input.article, content, law: "공공기록물 관리에 관한 법률" }) }] };
  },
});

server.registerTool({
  name: "calculate_retention_period",
  description: "기록물의 법정 보존기간을 산정한다. BRM 코드와 기록물 유형에 따라 1년/3년/5년/10년/30년/영구를 판단한다.",
  inputSchema: z.object({
    brmCode: z.string().describe("BRM 업무기능 코드"),
    recordType: z.string().describe("기록물 유형"),
    hasHistoricalValue: z.boolean().default(false).describe("역사적 가치 여부"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { brmCode: string; recordType: string; hasHistoricalValue: boolean };
    // 보존기간 산정 로직
    let period = "5년";
    if (input.hasHistoricalValue) period = "영구";
    else if (input.brmCode.startsWith("D")) period = "30년"; // 국방
    else if (input.brmCode.startsWith("C")) period = "30년"; // 통일외교

    return { content: [{ type: "text", text: JSON.stringify({
      brmCode: input.brmCode,
      retentionPeriod: period,
      legalBasis: "공공기록물법 제38조, 기록물관리기관 보존기간 책정기준",
    }) }] };
  },
});

server.registerTool({
  name: "check_redaction_eligibility",
  description: "비공개 기록물의 공개 전환 적격 여부를 법적 관점에서 검토한다.",
  inputSchema: z.object({
    yearsSinceCreation: z.number().int().min(0),
    securityLevel: z.enum(["restricted", "secret", "top_secret"]),
    containsPII: z.boolean(),
    involvesNationalSecurity: z.boolean(),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { yearsSinceCreation: number; securityLevel: string; containsPII: boolean; involvesNationalSecurity: boolean };

    let eligibility = "공개 가능";
    const reasons: string[] = [];

    if (input.yearsSinceCreation >= 30) {
      reasons.push("공공기록물법 제34조: 30년 경과 기록물 원칙적 공개");
    }
    if (input.containsPII) {
      eligibility = "부분공개 (PII 마스킹 후)";
      reasons.push("개인정보보호법 적용: PII 가명처리 필요");
    }
    if (input.involvesNationalSecurity) {
      eligibility = "비공개 유지";
      reasons.push("국가안보 관련 정보 포함");
    }

    return { content: [{ type: "text", text: JSON.stringify({ eligibility, reasons, legalBasis: reasons }) }] };
  },
});

server.registerTool({
  name: "ai_compliance_check",
  description: "AI 시스템의 한국 AI 기본법 준수 여부를 검토한다.",
  inputSchema: z.object({
    aiAction: z.string().describe("AI가 수행한 작업"),
    hasHITL: z.boolean().describe("인간 개입 게이트 존재 여부"),
    hasAuditTrail: z.boolean().describe("감사추적 기록 여부"),
    hasExplanation: z.boolean().describe("결정 근거 설명 제공 여부"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { aiAction: string; hasHITL: boolean; hasAuditTrail: boolean; hasExplanation: boolean };
    const violations: string[] = [];

    if (!input.hasHITL) violations.push("AI 기본법: 고위험 AI 시스템에 인간 개입 메커니즘 필수");
    if (!input.hasAuditTrail) violations.push("AI 기본법: AI 의사결정 감사추적 의무");
    if (!input.hasExplanation) violations.push("AI 기본법: 설명가능성 요구사항 위반");

    return { content: [{ type: "text", text: JSON.stringify({
      compliant: violations.length === 0,
      violations,
      recommendation: violations.length > 0 ? "시정 필요" : "준수",
    }) }] };
  },
});

server.registerTool({
  name: "disposal_approval_check",
  description: "기록물 폐기 절차의 법적 요건 충족 여부를 확인한다.",
  inputSchema: z.object({
    retentionExpired: z.boolean(),
    approverCount: z.number().int(),
    hasPreservationReview: z.boolean(),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { retentionExpired: boolean; approverCount: number; hasPreservationReview: boolean };
    const issues: string[] = [];

    if (!input.retentionExpired) issues.push("보존기간 미경과: 폐기 불가");
    if (input.approverCount < 2) issues.push("공공기록물법 제26조: 2인 이상 승인 필요");
    if (!input.hasPreservationReview) issues.push("영구보존 재검토 미실시");

    return { content: [{ type: "text", text: JSON.stringify({
      canDispose: issues.length === 0,
      issues,
      legalBasis: "공공기록물법 제26조",
    }) }] };
  },
});

server.registerTool({
  name: "legal_advisory",
  description: "기록물 관리 관련 법률 질의에 대해 자문한다.",
  inputSchema: z.object({
    question: z.string().min(1).describe("법률 질의 내용"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { question: string };
    // LLM 기반 법률 자문 (기록이 AI Agent 연동)
    return { content: [{ type: "text", text: JSON.stringify({
      question: input.question,
      advisory: "법률 자문 결과를 생성 중입니다...",
      disclaimer: "이 자문은 AI 참고 의견이며, 법적 효력이 없습니다. 전문 법률가 자문을 권장합니다.",
      relevantArticles: Object.keys(RECORDS_ACT_ARTICLES),
    }) }] };
  },
});

export default server;
