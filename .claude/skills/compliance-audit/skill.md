---
name: compliance-audit
description: "법적/보안 컴플라이언스 감사 스킬. ISMS-P 101개 항목 검증, 한국 AI 기본법(2026년 1월 시행) 위험평가/투명성/인간개입/편향방지 준수, N2SF 보안 프레임워크('민감' 등급), 공공기록물법(제6조/33-35조/38조) 적합성, PII 탐지 및 가명처리(제28조의2), 감사추적 10년 보존을 검증한다. '컴플라이언스', '보안 감사', 'ISMS-P', 'AI 기본법', '공공기록물법', 'N2SF', 'PII', '개인정보', '감사추적', '법적 요구사항' 관련 작업 시 반드시 이 스킬을 사용할 것."
---

# 컴플라이언스 감사

국가기록원 AI 시스템이 준수해야 하는 법적/보안 요구사항을 검증한다.

## 4대 컴플라이언스 프레임워크

### 1. 한국 AI 기본법 (2026년 1월 시행)

국가기록원의 AI 시스템은 **고위험 AI**로 분류될 가능성이 높다 (공공기관의 기록물 접근/분류 자동화). 필수 요구사항:

| 요구사항 | 구현 검증 포인트 |
|---------|---------------|
| 위험평가 | AI 모델별 위험평가서 작성, 정기 갱신 |
| 투명성 | AI 의사결정 근거 기록 (LangGraph 감사추적) |
| 인간 개입 | HITL 게이트 3개 (비밀해제/보존기간/분류이의) |
| 편향 방지 | 학습 데이터 편향 분석, 기관/시기/유형별 공정성 검증 |
| 설명 가능성 | 분류/비밀해제 결정의 근거 자동 생성 |

### 2. ISMS-P 인증 (2027년 7월 의무)

101개 항목 중 AI 시스템에 해당하는 핵심 항목:

- **접근 통제**: JWT + RBAC (admin/archivist/researcher/public)
- **암호화**: 전송 중 TLS 1.3, 저장 시 AES-256, 한국 암호 표준(ARIA/SEED)
- **로그 관리**: 모든 API 호출 로깅, 10년 보존, 위변조 방지 (해시 체인)
- **개인정보**: PII 자동 탐지 + 가명처리 (제28조의2)
- **취약점 관리**: CodeQL + Semgrep Pro + Trivy + TruffleHog 4중 스캔

### 3. N2SF 보안 프레임워크

- **등급**: "민감" (Sensitive) -- 인터넷 물리적 망분리 필수
- **에어갭**: 외부 API 호출 불가, 모든 모델/데이터 사전 로드
- **데이터 주권**: 모든 데이터 국내 저장, 해외 클라우드 사용 금지
- **인증**: 클라우드 서비스 CSAP 인증 필수 (Supabase 서울 리전 확인 필요)

### 4. 공공기록물법

| 조항 | 요구사항 | AI 시스템 구현 |
|------|---------|-------------|
| 제6조 | 기록물 관리 원칙 | 원본 보존, AI 처리 이력 별도 기록 |
| 제33조 | 비밀기록물 관리 | 보안 등급별 접근 통제, 자동 등급 부여 금지 (HITL) |
| 제34조 | 비공개 기록물 공개 | 비밀해제 심사 AI 지원, 최종 결정은 인간 |
| 제35조 | 기록물 열람 | 국민 열람권 보장, AI 검색으로 접근성 향상 |
| 제38조 | 기록물 폐기 | AI 폐기 추천 시 2인 이상 승인 필수 |

## 컴플라이언스 검증 체크리스트

```python
# scripts/compliance_check.py
COMPLIANCE_CHECKS = {
    "ai_basic_act": [
        "risk_assessment_exists",           # 위험평가서 존재
        "hitl_gates_configured",            # HITL 게이트 3개 설정
        "decision_explanations_logged",     # 의사결정 근거 기록
        "bias_analysis_completed",          # 편향 분석 완료
        "transparency_report_generated",    # 투명성 보고서 생성
    ],
    "isms_p": [
        "jwt_rbac_implemented",             # JWT + RBAC 구현
        "tls_1_3_enforced",                 # TLS 1.3 강제
        "aes_256_at_rest",                  # 저장 시 AES-256 암호화
        "audit_log_10_year_retention",      # 10년 감사로그 보존
        "pii_detection_active",             # PII 자동 탐지 활성
        "pii_pseudonymization_applied",     # PII 가명처리 적용
        "vulnerability_scan_4_layer",       # 4중 취약점 스캔
    ],
    "n2sf": [
        "air_gap_verified",                 # 에어갭 환경 검증
        "no_external_api_calls",            # 외부 API 호출 없음
        "data_sovereignty_confirmed",       # 데이터 국내 저장 확인
        "csap_certification_checked",       # CSAP 인증 확인
    ],
    "records_act": [
        "original_preserved",              # 원본 보존 확인
        "ai_processing_history_separate",  # AI 처리 이력 별도 기록
        "classification_hitl_required",    # 분류 변경 시 인간 개입
        "redaction_hitl_required",         # 비밀해제 인간 최종 결정
        "disposal_dual_approval",          # 폐기 2인 이상 승인
    ]
}
```

## PII 탐지 및 가명처리

```python
PII_PATTERNS = {
    "resident_id": r"\d{6}-[1-4]\d{6}",     # 주민등록번호
    "phone": r"01[0-9]-\d{3,4}-\d{4}",      # 전화번호
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "passport": r"[A-Z]\d{8}",              # 여권번호
    "driver_license": r"\d{2}-\d{6}-\d{2}", # 운전면허번호
    "account": r"\d{3}-\d{2,6}-\d{2,6}",   # 계좌번호
}
# 탐지된 PII는 SHA-256 기반 가명처리 (복원 불가)
```

## 감사추적 요구사항

모든 AI 의사결정에 다음 필드를 기록한다:
- `decision_id`: 고유 식별자
- `timestamp`: ISO 8601 (KST)
- `user_id`: 요청자 ID
- `agent_name`: 처리한 AI 에이전트명
- `action`: 수행한 작업 (classify/generate_metadata/review_redaction/...)
- `input_hash`: 입력 데이터 해시
- `output`: AI 출력 결과
- `confidence`: 신뢰도 점수
- `reasoning`: 결정 근거 (자연어 설명)
- `hitl_required`: 인간 개입 필요 여부
- `hitl_decision`: 인간의 최종 결정 (해당 시)
