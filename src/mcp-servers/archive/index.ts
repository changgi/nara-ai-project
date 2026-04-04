/**
 * MCP Archive Server (포트 3001)
 *
 * ARAM-ADK 42개 Go 에이전트를 MCP 프로토콜로 래핑.
 * 기록물 분류, 메타데이터 생성, 비밀해제 심사, 보존기간 산정, 유사 검색 도구 제공.
 */

import { z } from "zod";
import { MCPServerBase, type MCPTool, type MCPToolResult, withRetry } from "../common/server-base.js";

// ─── Zod 스키마 ───

const ClassifyRecordInput = z.object({
  title: z.string().min(1).describe("기록물 제목"),
  content: z.string().min(1).describe("기록물 본문"),
  agency: z.string().optional().describe("생산기관"),
});

const GenerateMetadataInput = z.object({
  content: z.string().min(1).describe("기록물 본문"),
  existingMetadata: z.record(z.unknown()).optional().describe("기존 메타데이터"),
});

const ReviewRedactionInput = z.object({
  title: z.string().min(1).describe("기록물 제목"),
  content: z.string().min(1).describe("기록물 본문"),
  currentLevel: z.enum(["public", "restricted", "secret", "top_secret"]).default("secret"),
  yearsSinceCreation: z.number().int().min(0).default(0),
});

const CalculateRetentionInput = z.object({
  brmCode: z.string().describe("BRM 업무기능 코드"),
  recordType: z.string().describe("기록물 유형"),
  agency: z.string().describe("생산기관"),
});

const SearchSimilarInput = z.object({
  query: z.string().min(1).describe("검색 쿼리"),
  topK: z.number().int().min(1).max(100).default(10),
  filters: z.record(z.unknown()).optional().describe("필터 조건"),
});

// ─── 서버 초기화 ───

const server = new MCPServerBase({
  name: "mcp-archive",
  version: "1.0.0",
  port: 3001,
  description: "ARAM-ADK 기반 기록물 관리 MCP 서버 (10 tools)",
});

// ─── 도구 등록 ───

server.registerTool({
  name: "classify_record",
  description: "기록물을 BRM 업무기능으로 분류한다. 제목과 본문을 분석하여 대/중/소분류 코드를 반환한다.",
  inputSchema: ClassifyRecordInput,
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as z.infer<typeof ClassifyRecordInput>;
    // ARAM-ADK 분류 에이전트 호출 (Go HTTP API)
    const result = await withRetry(
      async () => {
        const response = await fetch("http://localhost:9001/api/classify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: input.title,
            content: input.content.slice(0, 4000),
            agency: input.agency || "",
          }),
        });
        if (!response.ok) throw new Error(`ARAM-ADK 분류 실패: ${response.status}`);
        return response.json();
      },
      "classify_record",
    );
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "generate_metadata",
  description: "기록물 본문에서 메타데이터(제목, 요약, 키워드, 개체명)를 자동 생성한다.",
  inputSchema: GenerateMetadataInput,
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as z.infer<typeof GenerateMetadataInput>;
    const result = await withRetry(
      async () => {
        const response = await fetch("http://localhost:9001/api/metadata", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: input.content.slice(0, 6000), existing: input.existingMetadata }),
        });
        if (!response.ok) throw new Error(`메타데이터 생성 실패: ${response.status}`);
        return response.json();
      },
      "generate_metadata",
    );
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "review_redaction",
  description: "비공개 기록물의 공개 전환 적합성을 심사한다. PII 탐지, 보안 검토, 법적 근거를 제공한다. 최종 결정은 인간이 수행한다(HITL).",
  inputSchema: ReviewRedactionInput,
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as z.infer<typeof ReviewRedactionInput>;
    const result = await withRetry(
      async () => {
        const response = await fetch("http://localhost:9001/api/redaction", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        });
        if (!response.ok) throw new Error(`비밀해제 심사 실패: ${response.status}`);
        return response.json();
      },
      "review_redaction",
    );
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "calculate_retention",
  description: "기록물의 보존기간을 산정한다. BRM 코드, 기록물 유형, 생산기관을 기반으로 법정 보존기간을 계산한다.",
  inputSchema: CalculateRetentionInput,
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as z.infer<typeof CalculateRetentionInput>;
    const result = await withRetry(
      async () => {
        const response = await fetch("http://localhost:9001/api/retention", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        });
        if (!response.ok) throw new Error(`보존기간 산정 실패: ${response.status}`);
        return response.json();
      },
      "calculate_retention",
    );
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "search_similar",
  description: "유사 기록물을 검색한다. 시맨틱 검색과 키워드 검색을 결합한 하이브리드 검색을 수행한다.",
  inputSchema: SearchSimilarInput,
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as z.infer<typeof SearchSimilarInput>;
    const result = await withRetry(
      async () => {
        const response = await fetch("http://localhost:9001/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        });
        if (!response.ok) throw new Error(`검색 실패: ${response.status}`);
        return response.json();
      },
      "search_similar",
    );
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

// ─── 추가 도구 5개 (QA-M03 수정: 5→10 tools) ───

server.registerTool({
  name: "extract_entities",
  description: "기록물에서 개체명(인물, 기관, 장소, 날짜, 사건)을 추출한다.",
  inputSchema: z.object({
    content: z.string().min(1).describe("기록물 본문"),
    entityTypes: z.array(z.enum(["person", "organization", "location", "date", "event"])).default(["person", "organization", "location"]),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { content: string; entityTypes: string[] };
    const result = await withRetry(async () => {
      const response = await fetch("http://localhost:9001/api/entities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: input.content.slice(0, 4000), types: input.entityTypes }),
      });
      if (!response.ok) throw new Error(`개체명 추출 실패: ${response.status}`);
      return response.json();
    }, "extract_entities");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "summarize_record",
  description: "기록물을 200자 이내로 요약한다.",
  inputSchema: z.object({
    content: z.string().min(1),
    maxLength: z.number().int().min(50).max(500).default(200),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { content: string; maxLength: number };
    const result = await withRetry(async () => {
      const response = await fetch("http://localhost:9001/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: input.content.slice(0, 6000), maxLength: input.maxLength }),
      });
      if (!response.ok) throw new Error(`요약 실패: ${response.status}`);
      return response.json();
    }, "summarize_record");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "detect_pii",
  description: "기록물에서 PII(개인식별정보)를 탐지한다. 주민번호, 전화, 이메일, 여권, 계좌 등.",
  inputSchema: z.object({
    content: z.string().min(1),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { content: string };
    const result = await withRetry(async () => {
      const response = await fetch("http://localhost:9001/api/pii", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: input.content }),
      });
      if (!response.ok) throw new Error(`PII 탐지 실패: ${response.status}`);
      return response.json();
    }, "detect_pii");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "suggest_keywords",
  description: "기록물에 적합한 키워드를 5~10개 제안한다.",
  inputSchema: z.object({
    title: z.string(),
    content: z.string(),
    count: z.number().int().min(3).max(15).default(7),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { title: string; content: string; count: number };
    const result = await withRetry(async () => {
      const response = await fetch("http://localhost:9001/api/keywords", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: input.title, content: input.content.slice(0, 4000), count: input.count }),
      });
      if (!response.ok) throw new Error(`키워드 추천 실패: ${response.status}`);
      return response.json();
    }, "suggest_keywords");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "check_duplicates",
  description: "기록물의 중복 여부를 확인한다. 유사도 기반 중복 탐지.",
  inputSchema: z.object({
    title: z.string(),
    content: z.string(),
    threshold: z.number().min(0.5).max(1.0).default(0.85),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { title: string; content: string; threshold: number };
    const result = await withRetry(async () => {
      const response = await fetch("http://localhost:9001/api/duplicates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: input.title, content: input.content.slice(0, 2000), threshold: input.threshold }),
      });
      if (!response.ok) throw new Error(`중복 확인 실패: ${response.status}`);
      return response.json();
    }, "check_duplicates");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

export default server;
