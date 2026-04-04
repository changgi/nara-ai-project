const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "NARA-AI Project Team";
pres.title = "NARA-AI 과제기획서";

// 색상 팔레트: Midnight Executive
const C = {
  navy: "1A1A2E",
  darkBlue: "16213E",
  accent: "4A6CF7",
  white: "FFFFFF",
  lightGray: "F5F7FA",
  gray: "888888",
  text: "1A1A2E",
  lightText: "CADCFC",
};

// ═══════════════════════════════════════
// Slide 1: 표지
// ═══════════════════════════════════════
let s1 = pres.addSlide();
s1.background = { fill: C.navy };
s1.addText("NARA-AI", { x: 0.8, y: 1.0, w: 8.4, h: 1.2, fontSize: 54, fontFace: "Arial Black", color: C.white, bold: true });
s1.addText("AI 기반 국가기록물 지능형 검색 / 분류 / 활용 체계", { x: 0.8, y: 2.2, w: 8.4, h: 0.8, fontSize: 22, fontFace: "Calibri", color: C.lightText });
s1.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 3.3, w: 2, h: 0.05, fill: { color: C.accent } });
s1.addText([
  { text: "행정안전부 / 국가기록원", options: { breakLine: true, fontSize: 16, color: C.lightText } },
  { text: "GPU: NVIDIA B200 16~32장  |  기간: 2027~2028 (2개년)", options: { fontSize: 14, color: C.gray } },
], { x: 0.8, y: 3.6, w: 8.4, h: 1.0, fontFace: "Calibri" });
s1.addText('"국민을 위한, 국민에 의한, 국민에게 혜택이 돌아가는"', { x: 0.8, y: 4.8, w: 8.4, h: 0.5, fontSize: 14, fontFace: "Calibri", color: C.accent, italic: true });

// ═══════════════════════════════════════
// Slide 2: 프로젝트 개요
// ═══════════════════════════════════════
let s2 = pres.addSlide();
s2.background = { fill: C.lightGray };
s2.addText("프로젝트 개요", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.text, bold: true });

// 왼쪽: 핵심 수치
const stats = [
  { num: "290만", label: "전자기록물" },
  { num: "100만", label: "비전자 페이지 (OCR)" },
  { num: "47", label: "MCP 도구" },
  { num: "6", label: "AI 에이전트" },
];
stats.forEach((s, i) => {
  const y = 1.3 + i * 1.0;
  s2.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: y, w: 4.0, h: 0.85, fill: { color: C.white }, rectRadius: 0.1, shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 135, opacity: 0.08 } });
  s2.addText(s.num, { x: 1.0, y: y + 0.05, w: 1.5, h: 0.75, fontSize: 28, fontFace: "Arial Black", color: C.accent, bold: true, valign: "middle" });
  s2.addText(s.label, { x: 2.6, y: y + 0.05, w: 2.0, h: 0.75, fontSize: 16, fontFace: "Calibri", color: C.text, valign: "middle" });
});

// 오른쪽: 설명
s2.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: 1.3, w: 4.3, h: 3.7, fill: { color: C.navy }, rectRadius: 0.15 });
s2.addText([
  { text: "비전", options: { fontSize: 20, bold: true, color: C.accent, breakLine: true } },
  { text: "", options: { fontSize: 8, breakLine: true } },
  { text: "290만 전자기록물과 100만 페이지 비전자기록물에 AI를 적용하여:", options: { fontSize: 13, color: C.lightText, breakLine: true } },
  { text: "", options: { fontSize: 8, breakLine: true } },
  { text: "  자연어 검색으로 국민 접근성 혁신", options: { fontSize: 14, color: C.white, breakLine: true } },
  { text: "  기록물 전문가 업무 10배 효율화", options: { fontSize: 14, color: C.white, breakLine: true } },
  { text: "  비공개 기록물 체계적 공개 전환", options: { fontSize: 14, color: C.white, breakLine: true } },
  { text: "  100만 페이지 OCR 디지털화", options: { fontSize: 14, color: C.white, breakLine: true } },
], { x: 5.5, y: 1.5, w: 3.7, h: 3.3, fontFace: "Calibri", valign: "top" });

// ═══════════════════════════════════════
// Slide 3: 기술 아키텍처
// ═══════════════════════════════════════
let s3 = pres.addSlide();
s3.background = { fill: C.white };
s3.addText("6계층 시스템 아키텍처", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.text });

const layers = [
  { label: "L6 사용자 인터페이스", detail: "국민 검색 / 전문가 도구 / 관리 대시보드", color: "E8EAF6" },
  { label: "L5 LangGraph 오케스트레이터", detail: "6 AI 에이전트 + HITL 4개 + 감사추적 10년", color: "C5CAE9" },
  { label: "L4 MCP 서버 5개 (47 도구)", detail: "archive + iarna + nara + law + ramp", color: "9FA8DA" },
  { label: "L3 데이터 계층", detail: "Milvus 2.6 벡터DB + Cloud Spanner 지식그래프", color: "7986CB" },
  { label: "L2 AI 추론 (vLLM)", detail: "EXAONE 3.5 SFT + Qwen3-VL OCR + BGE-M3 임베딩", color: "5C6BC0" },
  { label: "L1 GPU 인프라", detail: "DGX B200 x16-32 / NVLink 5.0 / 에어갭", color: C.navy },
];
layers.forEach((l, i) => {
  const y = 1.2 + i * 0.7;
  const textColor = i >= 4 ? C.white : C.text;
  s3.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: y, w: 8.4, h: 0.6, fill: { color: l.color }, rectRadius: 0.08 });
  s3.addText(l.label, { x: 1.0, y: y, w: 3.5, h: 0.6, fontSize: 14, fontFace: "Calibri", color: textColor, bold: true, valign: "middle", margin: 0 });
  s3.addText(l.detail, { x: 4.5, y: y, w: 4.5, h: 0.6, fontSize: 12, fontFace: "Calibri", color: textColor, valign: "middle", margin: 0 });
});

// ═══════════════════════════════════════
// Slide 4: 핵심 기능
// ═══════════════════════════════════════
let s4 = pres.addSlide();
s4.background = { fill: C.lightGray };
s4.addText("핵심 기능 및 성능 목표", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.text });

const features = [
  { title: "자연어 검색", metric: "Recall@10 >= 0.90", desc: "Dense+Sparse+Graph\n하이브리드 RAG" },
  { title: "기록물 분류", metric: "F1 >= 0.92", desc: "BRM 업무기능\n자동 매핑" },
  { title: "OCR 디지털화", metric: "CER <= 3%/7%/10%", desc: "3모델 앙상블\n7종 문서 지원" },
  { title: "비밀해제 심사", metric: "Precision >= 0.95", desc: "PII 6종 탐지\nHITL 필수" },
  { title: "메타데이터 생성", metric: "ROUGE-1 >= 0.85", desc: "제목/요약/키워드\nNER 자동 추출" },
  { title: "감사추적", metric: "10년 보존", desc: "AI 기본법\n투명성 준수" },
];
features.forEach((f, i) => {
  const col = i % 3;
  const row = Math.floor(i / 3);
  const x = 0.8 + col * 3.1;
  const y = 1.2 + row * 2.1;
  s4.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x, y: y, w: 2.8, h: 1.9, fill: { color: C.white }, rectRadius: 0.1, shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 135, opacity: 0.08 } });
  s4.addText(f.title, { x: x + 0.2, y: y + 0.15, w: 2.4, h: 0.4, fontSize: 16, fontFace: "Calibri", color: C.text, bold: true, margin: 0 });
  s4.addText(f.metric, { x: x + 0.2, y: y + 0.55, w: 2.4, h: 0.35, fontSize: 20, fontFace: "Arial Black", color: C.accent, margin: 0 });
  s4.addText(f.desc, { x: x + 0.2, y: y + 1.0, w: 2.4, h: 0.7, fontSize: 12, fontFace: "Calibri", color: C.gray, margin: 0 });
});

// ═══════════════════════════════════════
// Slide 5: GPU 요청
// ═══════════════════════════════════════
let s5 = pres.addSlide();
s5.background = { fill: C.white };
s5.addText("GPU 리소스 요청", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.text });

// 큰 숫자
s5.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: 1.2, w: 4.0, h: 2.0, fill: { color: C.navy }, rectRadius: 0.15 });
s5.addText("16~32", { x: 0.8, y: 1.2, w: 4.0, h: 1.2, fontSize: 60, fontFace: "Arial Black", color: C.accent, align: "center", valign: "middle" });
s5.addText("NVIDIA B200 GPU", { x: 0.8, y: 2.3, w: 4.0, h: 0.6, fontSize: 18, fontFace: "Calibri", color: C.white, align: "center" });

// 오른쪽: GPU 활용 계획
const gpuPlans = [
  { gpu: "8 GPU", use: "7B LoRA SFT (15~30분)\nOCR 앙상블 + RAG 서빙" },
  { gpu: "16 GPU", use: "7B 풀 SFT (3~6시간)\n멀티모델 병렬 추론" },
  { gpu: "32 GPU", use: "파운데이션 모델 CPT\n대규모 OCR 파이프라인" },
];
gpuPlans.forEach((g, i) => {
  const y = 1.2 + i * 0.85;
  s5.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: y, w: 4.3, h: 0.75, fill: { color: C.lightGray }, rectRadius: 0.08 });
  s5.addText(g.gpu, { x: 5.4, y: y, w: 1.3, h: 0.75, fontSize: 16, fontFace: "Calibri", color: C.accent, bold: true, valign: "middle", margin: 0 });
  s5.addText(g.use, { x: 6.8, y: y, w: 2.5, h: 0.75, fontSize: 12, fontFace: "Calibri", color: C.text, valign: "middle", margin: 0 });
});

// 하단: 기존 자산
s5.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: 3.5, w: 8.7, h: 1.5, fill: { color: C.lightGray }, rectRadius: 0.1 });
s5.addText("기존 자산 통합으로 12~18개월 개발 기간 절감", { x: 1.0, y: 3.6, w: 8.3, h: 0.5, fontSize: 16, fontFace: "Calibri", color: C.text, bold: true, margin: 0 });
s5.addText("10개 프로젝트 (283K+ LOC, 482 API, 165 에이전트, 85 MCP 도구)를 MCP 프로토콜로 통합", { x: 1.0, y: 4.1, w: 8.3, h: 0.5, fontSize: 13, fontFace: "Calibri", color: C.gray, margin: 0 });

// ═══════════════════════════════════════
// Slide 6: 법률 준수
// ═══════════════════════════════════════
let s6 = pres.addSlide();
s6.background = { fill: C.lightGray };
s6.addText("법률 준수 (4대 프레임워크)", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.text });

const laws = [
  { name: "AI 기본법", date: "2026.1 시행", items: "HITL 4개 게이트\n감사추적 필수 필드\n설명가능성\n편향 방지" },
  { name: "ISMS-P", date: "2027.7 의무", items: "JWT + RBAC\nPII 6종 탐지\n4중 보안 스캔\nTLS 1.3 + AES-256" },
  { name: "N2SF", date: "적용 중", items: "에어갭 네트워크\n물리적 망분리\n데이터 주권\nCSAP 인증" },
  { name: "공공기록물법", date: "적용 중", items: "비밀해제 HITL\n폐기 2인 승인\n30년 공개 원칙\n감사 10년 보존" },
];
laws.forEach((l, i) => {
  const x = 0.8 + i * 2.3;
  s6.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x, y: 1.2, w: 2.1, h: 3.8, fill: { color: C.white }, rectRadius: 0.1, shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 135, opacity: 0.08 } });
  s6.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x, y: 1.2, w: 2.1, h: 0.9, fill: { color: C.navy }, rectRadius: 0.1 });
  s6.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.7, w: 2.1, h: 0.4, fill: { color: C.navy } });
  s6.addText(l.name, { x: x + 0.1, y: 1.3, w: 1.9, h: 0.45, fontSize: 16, fontFace: "Calibri", color: C.white, bold: true, align: "center", margin: 0 });
  s6.addText(l.date, { x: x + 0.1, y: 1.7, w: 1.9, h: 0.35, fontSize: 11, fontFace: "Calibri", color: C.lightText, align: "center", margin: 0 });
  s6.addText(l.items, { x: x + 0.2, y: 2.3, w: 1.7, h: 2.5, fontSize: 12, fontFace: "Calibri", color: C.text, margin: 0 });
});

// ═══════════════════════════════════════
// Slide 7: 국민 혜택
// ═══════════════════════════════════════
let s7 = pres.addSlide();
s7.background = { fill: C.navy };
s7.addText("국민 혜택", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.white });

const benefits = [
  { title: "접근성 혁신", before: "키워드 검색, 전문가만", after: "자연어 검색, 누구나 (P99 <= 2초)" },
  { title: "투명성 강화", before: "수작업 비밀해제 심사", after: "AI 추천 + 인간 최종결정" },
  { title: "효율성 향상", before: "수작업 분류/메타데이터", after: "AI 자동화 (10배 효율화)" },
  { title: "역사 보존", before: "스캔 이미지만 열람", after: "100만 페이지 OCR 전문 검색" },
];
benefits.forEach((b, i) => {
  const y = 1.2 + i * 1.05;
  s7.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: y, w: 8.4, h: 0.9, fill: { color: C.darkBlue }, rectRadius: 0.08 });
  s7.addText(b.title, { x: 1.0, y: y, w: 1.8, h: 0.9, fontSize: 16, fontFace: "Calibri", color: C.accent, bold: true, valign: "middle", margin: 0 });
  s7.addText(b.before, { x: 3.0, y: y, w: 2.8, h: 0.9, fontSize: 13, fontFace: "Calibri", color: C.gray, valign: "middle", margin: 0 });
  s7.addText("→", { x: 5.7, y: y, w: 0.5, h: 0.9, fontSize: 20, fontFace: "Calibri", color: C.accent, align: "center", valign: "middle" });
  s7.addText(b.after, { x: 6.2, y: y, w: 2.8, h: 0.9, fontSize: 13, fontFace: "Calibri", color: C.white, valign: "middle", margin: 0, bold: true });
});

// ═══════════════════════════════════════
// Slide 8: 타임라인
// ═══════════════════════════════════════
let s8 = pres.addSlide();
s8.background = { fill: C.white };
s8.addText("추진 타임라인", { x: 0.8, y: 0.3, w: 8.4, h: 0.7, fontSize: 36, fontFace: "Arial Black", color: C.text });

// 타임라인 바
s8.addShape(pres.shapes.RECTANGLE, { x: 1.5, y: 2.5, w: 7.5, h: 0.08, fill: { color: C.accent } });

const timeline = [
  { period: "2027 H1", phase: "1단계 MVP", items: "분류+검색+OCR\n기본 동작" },
  { period: "2027 H2", phase: "2단계 통합", items: "비밀해제+RAG\nMCP 통합" },
  { period: "2028 H1", phase: "3단계 최적화", items: "전체 파이프라인\n성능 최적화" },
  { period: "2028 H2", phase: "4단계 안정화", items: "운영 안정화\nISMS-P 인증" },
];
timeline.forEach((t, i) => {
  const x = 1.5 + i * 2.0;
  // 원형 마커
  s8.addShape(pres.shapes.OVAL, { x: x + 0.55, y: 2.3, w: 0.4, h: 0.4, fill: { color: C.accent } });
  // 위: 기간
  s8.addText(t.period, { x: x, y: 1.4, w: 1.5, h: 0.4, fontSize: 14, fontFace: "Calibri", color: C.accent, bold: true, align: "center", margin: 0 });
  s8.addText(t.phase, { x: x, y: 1.8, w: 1.5, h: 0.4, fontSize: 13, fontFace: "Calibri", color: C.text, align: "center", margin: 0 });
  // 아래: 내용
  s8.addText(t.items, { x: x, y: 2.9, w: 1.5, h: 1.0, fontSize: 12, fontFace: "Calibri", color: C.gray, align: "center", margin: 0 });
});

// 하단
s8.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: 4.3, w: 8.4, h: 0.8, fill: { color: C.lightGray }, rectRadius: 0.1 });
s8.addText("웹 데모:  https://nara-ai-project.vercel.app   |   GitHub:  github.com/changgi/nara-ai-project", { x: 1.0, y: 4.3, w: 8.0, h: 0.8, fontSize: 14, fontFace: "Calibri", color: C.accent, valign: "middle", align: "center", margin: 0 });

// 저장
const outPath = process.argv[2] || "docs/NARA-AI-과제기획서.pptx";
pres.writeFile({ fileName: outPath }).then(() => {
  console.log(`프레젠테이션 생성: ${outPath}`);
});
