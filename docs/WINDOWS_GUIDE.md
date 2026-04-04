# NARA-AI Windows 사용 가이드

비개발자도 따라할 수 있는 Windows 설치 및 실행 가이드입니다.

## 사전 준비

### 1. Python 설치

1. https://www.python.org/downloads/ 접속
2. **Python 3.11 이상** 다운로드 (Download Python 3.x.x 버튼)
3. 설치 시 반드시 **"Add Python to PATH"** 체크!
4. Install Now 클릭

확인:
```
Win + R → cmd → python --version
```
`Python 3.11.x` 이상이 나오면 성공.

### 2. 프로젝트 다운로드

프로젝트 폴더를 원하는 위치에 복사합니다.
예: `C:\nara-ai\nara-ai-project\`

## 실행 방법

### 방법 1: 더블클릭 (가장 쉬움)

프로젝트 폴더에서:

1. **`setup.bat`** 더블클릭 → 초기 설정 (최초 1회)
2. **`run.bat`** 더블클릭 → 서버 시작
3. 브라우저에서 **http://localhost:8080** 접속

CPU 전용 모드 (GPU 없는 노트북):
- **`run_cpu.bat`** 더블클릭

### 방법 2: 명령 프롬프트

```
cd C:\nara-ai\nara-ai-project
python run.py --setup          초기 설정
python run.py --check          환경 점검
python run.py --demo           데모 실행
python run.py --server         서버 시작
python run.py --cpu --server   CPU 모드 서버
```

## 데모 데이터 인덱싱

서버 시작 전에 검색 데이터를 준비합니다:

```
python scripts\data\index_demo_data.py
```

30건의 국가기록물 샘플 데이터가 인덱싱됩니다.

## 웹 UI 사용법

### 검색 탭
1. 검색창에 자연어 입력 (예: "한국전쟁 외교 문서")
2. "검색" 버튼 클릭 또는 Enter
3. 결과 목록에서 관련 기록물 확인

### PII 탐지 탭
1. "PII 탐지" 탭 클릭
2. 텍스트 입력 (예: "홍길동 850101-1234567 연락처 010-1234-5678")
3. "PII 탐지" 버튼 클릭
4. 주민번호, 전화번호 등이 자동 마스킹됨

### OCR 교정 탭
1. "OCR 교정" 탭 클릭
2. OCR로 인식된 텍스트 입력 (예: "행정안전뷰 공공기록뭄")
3. "교정" 버튼 클릭
4. "행정안전부 공공기록물"로 자동 교정됨

## GPU 자동 감지

프로그램은 GPU를 자동으로 감지합니다:

```
python run.py --check
```

결과 예시:
```
GPU: NVIDIA GeForce RTX 4060 Laptop GPU (8GB, consumer)
추천: 3B 모델, int8 양자화, TP=1, max_len=1024
```

| GPU | 추천 모드 |
|-----|---------|
| RTX 4090 (24GB) | 8B 모델, bfloat16 |
| RTX 4060 (8GB) | 3B 모델, int8 양자화 |
| RTX 3060 (12GB) | 3B 모델, int8 양자화 |
| GPU 없음 | CPU 모드 (TF-IDF + BM25) |

## 문제 해결

### "Python이 설치되어 있지 않습니다"
- Python을 설치하세요: https://www.python.org/downloads/
- **"Add Python to PATH"** 반드시 체크

### "한글이 깨져 보입니다"
- cmd 창에서: `chcp 65001` 입력 후 재실행
- 또는 `run.bat` 사용 (자동으로 UTF-8 설정)

### "검색 결과가 없습니다"
- 데이터 인덱싱 필요: `python scripts\data\index_demo_data.py`

### "포트가 이미 사용 중입니다"
- 다른 포트 사용: `python run.py --server --port 9000`
- 또는 기존 프로세스 종료 후 재시작

### "패키지 설치 실패"
- 관리자 권한으로 cmd 실행
- `python -m pip install --upgrade pip`
- `python -m pip install -r scripts\windows\requirements-cpu.txt`

## 종료

- 서버 창에서 **Ctrl + C** 누르면 종료됩니다.
