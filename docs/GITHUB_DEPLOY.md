# NARA-AI GitHub 배포 가이드

## 1. GitHub 리포지토리 생성

### 방법 A: 웹에서 생성
1. https://github.com/new 접속
2. Repository name: `nara-ai-project`
3. Description: `AI 기반 국가기록물 지능형 검색/분류/활용 체계`
4. Private 선택 (보안상 권장)
5. Create repository 클릭

### 방법 B: gh CLI 사용
```bash
# gh CLI 설치 (Windows)
winget install GitHub.cli

# 인증
gh auth login

# 리포지토리 생성
gh repo create nara-ai-project --private --description "AI 기반 국가기록물 지능형 검색/분류/활용 체계"
```

## 2. 로컬 → GitHub Push

```bash
cd nara-ai-project

# 리모트 추가 (본인 GitHub 계정으로 변경)
git remote add origin https://github.com/YOUR_USERNAME/nara-ai-project.git

# push
git branch -M main
git push -u origin main
```

## 3. GitHub Actions CI/CD

push 후 자동으로 `.github/workflows/ci.yml`이 실행됩니다:
- Python 린트 (ruff)
- TypeScript 타입체크
- 단위 테스트 (pytest)
- 보안 스캔 (Semgrep, Trivy, TruffleHog)
- PII 스캔 (한국 개인정보 패턴)

## 4. GitHub Secrets 설정 (선택)

Settings > Secrets > Actions에 추가:
- `WANDB_API_KEY`: WandB 학습 추적
- `DOCKER_REGISTRY`: Docker 이미지 레지스트리

## 5. 보안 주의사항

- `.env` 파일은 `.gitignore`에 포함되어 push되지 않음
- `.env.example`만 커밋됨 (비밀키 없음)
- 모든 GitHub Actions는 commit SHA로 고정 (공급망 공격 방지)
