---
name: mcp-server-dev
description: "MCP(Model Context Protocol) 서버 개발 스킬. 5개 MCP 서버(mcp-archive, mcp-iarna, mcp-nara, mcp-law, mcp-ramp) 구현, OAuth 2.1 인증, Zod 스키마 검증, ARAM-ADK Go 에이전트 래핑, Cloud Spanner 지식그래프 연동, RAMP 플랫폼 통합, LangGraph 오케스트레이터 구현을 수행한다. 'MCP 서버', 'MCP 도구', 'Model Context Protocol', 'ARAM-ADK 연동', 'RAMP 연동', 'IARNA', '에이전트 오케스트레이션', 'LangGraph' 관련 작업 시 반드시 이 스킬을 사용할 것."
---

# MCP 서버 개발

국가기록원의 기존 자산(160K+ LOC, 279 API, 165 에이전트)을 MCP 프로토콜로 통합하는 5개 서버를 개발한다.

## 5개 MCP 서버 구조

| 서버 | 포트 | 도구 수 | 핵심 기능 |
|------|------|---------|----------|
| mcp-archive | 3001 | 10 | ARAM-ADK 42개 Go 에이전트 래핑 |
| mcp-iarna | 3002 | 12 | Cloud Spanner 지식그래프 + Vibe Query |
| mcp-nara | 3003 | 12 | 국제 아카이브(US NARA, UK TNA, DPLA) + Vision OCR |
| mcp-law | 3004 | 6 | 공공기록물법 법률 자문 |
| mcp-ramp | 3005 | 7 | RAMP 플랫폼 (48개 중앙부처) 연동 |

## MCP 서버 공통 구조

```typescript
// src/mcp-servers/{name}/index.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import express from "express";

const app = express();
const server = new Server({ name: "mcp-{name}", version: "1.0.0" }, {
  capabilities: { tools: {} }
});

// 헬스체크 엔드포인트 (필수)
app.get("/health", (req, res) => {
  res.json({ status: "ok", server: "mcp-{name}", version: "1.0.0" });
});

// 도구 등록
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [/* ... */]
}));

// 도구 실행
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  // Zod 검증 후 실행
});

// 전송 연결 (stdio)
const transport = new StdioServerTransport();
await server.connect(transport);
```

## 서버별 핵심 도구

### mcp-archive (ARAM-ADK 래핑)
- `classify_record`: BRM 업무기능 분류
- `generate_metadata`: 제목/키워드/요약 자동 생성
- `review_redaction`: 비밀해제 심사 지원
- `calculate_retention`: 보존기간 산정
- `search_similar`: 유사 기록물 검색

### mcp-iarna (지식그래프)
- `vibe_query`: 자연어 → Spanner Graph 쿼리 변환
- `graph_neighbors`: N-홉 이웃 탐색
- `graph_path`: 두 엔티티 간 최단 경로
- `thesaurus_lookup`: 시소러스 용어 조회
- `timeline_query`: 시간축 기반 사건 조회

### mcp-ramp (RAMP 연동)
- `ingest_metadata`: 48개 부처 실시간 메타데이터 수집
- `sync_classification`: 기록물 분류 동기화
- `validate_retention`: 보존기간 정합성 검증
- `report_statistics`: 기록물 통계 리포트

## LangGraph 오케스트레이터

```python
# src/agents/orchestrator/graph.py
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

# 6개 특화 AI 에이전트 노드
graph = StateGraph(RecordProcessingState)
graph.add_node("classifier", ClassifierAgent())
graph.add_node("metadata_gen", MetadataAgent())
graph.add_node("redaction_reviewer", RedactionAgent())
graph.add_node("ocr_processor", OCRAgent())
graph.add_node("search_agent", SearchAgent())
graph.add_node("quality_checker", QualityAgent())

# HITL 게이트 (인간 개입 필수 지점)
graph.add_node("hitl_redaction", HITLGate(action="redaction_decision"))
graph.add_node("hitl_retention", HITLGate(action="retention_override"))
graph.add_node("hitl_classification", HITLGate(action="classification_dispute"))

# 감사추적: 모든 노드 전환에 타임스탬프 + 근거 기록
checkpointer = SqliteSaver(conn_string="checkpoints/langgraph.db")
# 보존기간: 10년 (3,650일)
```

## OAuth 2.1 인증

모든 MCP 서버는 OAuth 2.1 인증을 적용한다:
- JWT 토큰 기반 인증
- Role-based Access Control (RBAC): admin, archivist, researcher, public
- 토큰 만료: access 1시간, refresh 7일
- 감사추적: 모든 API 호출에 사용자 ID + 타임스탬프 기록

## 에러 처리 패턴

```typescript
// 공통 에러 핸들링
class MCPToolError extends Error {
  constructor(
    public code: string,        // "VALIDATION_ERROR" | "AUTH_ERROR" | "TIMEOUT"
    public message: string,
    public retryable: boolean,
    public context?: Record<string, unknown>
  ) { super(message); }
}

// 1회 재시도 후 실패 시 빈 결과 + 에러 보고
async function withRetry<T>(fn: () => Promise<T>): Promise<T | null> {
  try { return await fn(); }
  catch (e) {
    try { return await fn(); }
    catch (e2) { logger.error(e2); return null; }
  }
}
```
