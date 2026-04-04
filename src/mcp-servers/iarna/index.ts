/**
 * MCP IARNA Server (포트 3002)
 *
 * Cloud Spanner Property Graph + RiC-CM 1.0 지식그래프
 * Vibe Query Engine: 자연어 → Spanner Graph 쿼리 변환
 * 12개 도구 제공
 */

import { z } from "zod";
import { MCPServerBase, type MCPToolResult, withRetry } from "../common/server-base.js";

const server = new MCPServerBase({
  name: "mcp-iarna",
  version: "2.1.0",
  port: 3002,
  description: "IARNA 지식그래프 MCP 서버 (12 tools) - RiC-CM 1.0 on Cloud Spanner",
});

// ─── 핵심 도구 ───

server.registerTool({
  name: "vibe_query",
  description: "자연어 질의를 Spanner Graph 쿼리로 변환하여 실행한다. '김구 관련 기록물', '1950년대 외교 문서' 등 자연어로 지식그래프를 탐색한다.",
  inputSchema: z.object({
    query: z.string().min(1).describe("자연어 질의"),
    maxResults: z.number().int().min(1).max(100).default(20),
    includeGraph: z.boolean().default(true),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { query: string; maxResults: number; includeGraph: boolean };
    const result = await withRetry(async () => {
      // Spanner Graph 쿼리 생성 및 실행
      const spannerQuery = buildGraphQuery(input.query);
      return { query: spannerQuery, results: [], totalCount: 0 };
    }, "vibe_query");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "graph_neighbors",
  description: "지식그래프에서 특정 노드의 N-홉 이웃을 탐색한다. 인물, 기관, 사건 간의 관계를 추적한다.",
  inputSchema: z.object({
    nodeId: z.string().describe("시작 노드 ID 또는 이름"),
    depth: z.number().int().min(1).max(5).default(2),
    relationType: z.enum(["exchanges_with", "part_of", "created_by", "related_to", "located_in", "references", "all"]).default("all"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { nodeId: string; depth: number; relationType: string };
    const result = await withRetry(async () => {
      return { nodeId: input.nodeId, neighbors: [], depth: input.depth };
    }, "graph_neighbors");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
});

server.registerTool({
  name: "graph_path",
  description: "두 엔티티 간의 최단 관계 경로를 탐색한다.",
  inputSchema: z.object({
    from: z.string().describe("시작 엔티티"),
    to: z.string().describe("도착 엔티티"),
    maxDepth: z.number().int().min(1).max(6).default(4),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { from: string; to: string; maxDepth: number };
    return { content: [{ type: "text", text: JSON.stringify({ from: input.from, to: input.to, path: [] }) }] };
  },
});

server.registerTool({
  name: "thesaurus_lookup",
  description: "시소러스에서 용어를 조회한다. 동의어, 이형표기, 한자, 로마자 표기를 반환한다.",
  inputSchema: z.object({
    term: z.string().min(1).describe("조회할 용어"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { term: string };
    return { content: [{ type: "text", text: JSON.stringify({ term: input.term, synonyms: [], variants: [] }) }] };
  },
});

server.registerTool({
  name: "thesaurus_expand",
  description: "용어의 모든 이형 표기를 확장한다. 검색 쿼리 확장에 활용한다.",
  inputSchema: z.object({
    term: z.string().min(1),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { term: string };
    return { content: [{ type: "text", text: JSON.stringify({ term: input.term, expanded: [input.term] }) }] };
  },
});

server.registerTool({
  name: "timeline_query",
  description: "시간축 기반으로 사건, 인물, 기관의 연대기를 조회한다.",
  inputSchema: z.object({
    startYear: z.number().int(),
    endYear: z.number().int(),
    category: z.enum(["event", "person", "organization", "record", "all"]).default("all"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { startYear: number; endYear: number; category: string };
    return { content: [{ type: "text", text: JSON.stringify({ range: `${input.startYear}-${input.endYear}`, events: [] }) }] };
  },
});

server.registerTool({
  name: "ontology_map",
  description: "엔티티를 RiC-O 온톨로지 클래스에 매핑한다. Spanner 테이블/컬럼, ISAD(G) 기술 영역, NAK 메타데이터 요소를 반환한다.",
  inputSchema: z.object({
    entityType: z.enum(["person", "place", "organization", "event", "record_group", "topic", "record_type"]),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { entityType: string };
    return { content: [{ type: "text", text: JSON.stringify({ entityType: input.entityType, ricClass: "", spannerTable: "" }) }] };
  },
});

server.registerTool({
  name: "record_search",
  description: "기록물을 검색한다. Record Group, 시기, 키워드, 생산 기관으로 필터링한다.",
  inputSchema: z.object({
    keyword: z.string().min(1),
    recordGroup: z.string().optional(),
    creator: z.string().optional(),
    dateAfter: z.string().optional(),
    dateBefore: z.string().optional(),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    return { content: [{ type: "text", text: JSON.stringify({ results: [], totalCount: 0 }) }] };
  },
});

server.registerTool({
  name: "facility_search",
  description: "기록관리 시설/기관을 검색한다.",
  inputSchema: z.object({
    name: z.string().optional(),
    region: z.string().optional(),
    type: z.enum(["archives", "museum", "library", "records_center", "education", "all"]).default("all"),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    return { content: [{ type: "text", text: JSON.stringify({ facilities: [] }) }] };
  },
});

server.registerTool({
  name: "vault_stats",
  description: "IARNA Vault의 온톨로지 통계를 반환한다.",
  inputSchema: z.object({}),
  handler: async (): Promise<MCPToolResult> => {
    return { content: [{ type: "text", text: JSON.stringify({ nodes: 0, edges: 0, classes: 19, relationTypes: 142 }) }] };
  },
});

server.registerTool({
  name: "archival_standard",
  description: "기록관리 표준(ISAD(G), RiC-CM, NAK 등)의 주요 내용을 참조한다.",
  inputSchema: z.object({
    standard: z.enum(["ISAD(G)", "RiC-CM", "RiC-O", "NAK", "OAIS", "PREMIS", "EAD", "DACS"]),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { standard: string };
    return { content: [{ type: "text", text: JSON.stringify({ standard: input.standard, description: "" }) }] };
  },
});

server.registerTool({
  name: "explain_query",
  description: "Vibe Query의 실행 계획을 상세히 설명한다.",
  inputSchema: z.object({
    query: z.string().min(1),
  }),
  handler: async (args): Promise<MCPToolResult> => {
    const input = args as { query: string };
    return { content: [{ type: "text", text: JSON.stringify({ query: input.query, plan: [] }) }] };
  },
});

function buildGraphQuery(naturalLanguage: string): string {
  // 자연어 → Spanner Graph 쿼리 변환 (LLM 기반)
  return `GRAPH nara_knowledge MATCH (n) WHERE n.name CONTAINS '${naturalLanguage}' RETURN n LIMIT 20`;
}

export default server;
