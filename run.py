#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NARA-AI v1.0 — 크로스 플랫폼 런처

Windows / macOS / Linux 모두 동일하게 동작합니다.
한글(UTF-8) 출력을 보장합니다.

사용법:
    python run.py                  전체 자동 (설정→테스트→데모→서버)
    python run.py --setup          초기 설정 (.env + 패키지)
    python run.py --check          환경 점검
    python run.py --server         임베딩 서버 시작
    python run.py --demo           전체 데모 (PII + OCR + 벤치마크)
    python run.py --test           테스트 실행
    python run.py --cpu            CPU 전용 모드
    python run.py --benchmark      벤치마크 실행
    python run.py --port 9000      포트 지정
"""

from __future__ import annotations

import io
import os
import sys
import shutil
import platform
import subprocess
import argparse
from pathlib import Path

# ═══════════════════════════════════════════
# UTF-8 강제 (Windows 한글 깨짐 방지)
# ═══════════════════════════════════════════
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# ═══════════════════════════════════════════
# 상수
# ═══════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
IS_WIN = platform.system() == "Windows"
PY = sys.executable


# ═══════════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════════
def banner():
    os_label = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(
        platform.system(), platform.system()
    )
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # GPU 감지
    gpu_info = "없음 (CPU 모드)"
    try:
        from config.hardware_profiles import detect_all_gpus
        gpus = detect_all_gpus()
        if gpus:
            gpu_info = f"{gpus[0].name} ({gpus[0].vram_gb:.0f}GB)"
            if len(gpus) > 1:
                gpu_info += f" x{len(gpus)}"
    except Exception:
        try:
            import torch
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                gpu_info = torch.cuda.get_device_name(0)
        except (ImportError, AssertionError, RuntimeError):
            pass

    print()
    print("=" * 56)
    print("  NARA-AI v1.0")
    print("  AI 기반 국가기록물 지능형 검색/분류/활용 체계")
    print("  행정안전부 / 국가기록원")
    print(f"  {os_label} / Python {py} / GPU: {gpu_info}")
    print("=" * 56)
    print()


def ok(msg: str):
    print(f"  [완료] {msg}")

def warn(msg: str):
    print(f"  [경고] {msg}")

def fail(msg: str):
    print(f"  [실패] {msg}")

def run_cmd(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = str(BASE_DIR)
    return subprocess.run(cmd, cwd=str(BASE_DIR), env=env, **kw)


# ═══════════════════════════════════════════
# 1. 환경 점검
# ═══════════════════════════════════════════
def check_python() -> bool:
    if sys.version_info < (3, 11):
        fail(f"Python 3.11 이상 필요 (현재 {sys.version})")
        if IS_WIN:
            print("     https://www.python.org/downloads/ 에서 설치")
            print("     설치 시 'Add Python to PATH' 반드시 체크!")
        return False
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def check_gpu() -> str:
    """GPU 감지 (hardware_profiles 통합). 반환값: 프로파일 codename 또는 'cpu'"""
    try:
        from config.hardware_profiles import detect_system, print_system_report
        from src.pipeline.serve.vllm_config import get_serving_configs_adaptive, print_serving_plan

        profile = detect_system()
        print_system_report(profile)

        if profile.gpus:
            print()
            print("  === vLLM 서빙 계획 ===")
            configs = get_serving_configs_adaptive(profile)
            print_serving_plan(configs)
            return profile.gpus[0].codename
        else:
            return "cpu"
    except Exception as e:
        # 폴백: 기본 torch 감지
        try:
            import torch
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                ok(f"GPU: {name} ({vram:.0f}GB) [기본 감지]")
                return "gpu"
            else:
                warn("GPU 미감지. CPU 모드로 실행합니다.")
                return "cpu"
        except (ImportError, AssertionError, RuntimeError):
            warn(f"GPU 감지 실패: {e}")
            return "cpu"


def check_env() -> bool:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        ok(".env 파일 존재")
        return True
    # 템플릿 복사
    for template in (".env.production", ".env.example"):
        src = BASE_DIR / template
        if src.exists():
            shutil.copy(src, env_file)
            warn(f"{template} -> .env 복사됨 (비밀키 변경 필요)")
            return True
    fail(".env 파일 없음")
    return False


def ensure_dirs():
    dirs = [
        "data/raw/electronic", "data/raw/non-electronic", "data/raw/ocr-gt",
        "data/processed/sft", "data/processed/dpo", "data/test",
        "data/embeddings", "data/db",
        "checkpoints", "logs", "_workspace/audit",
    ]
    for d in dirs:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════
# 2. 의존성 설치
# ═══════════════════════════════════════════
def install_deps(mode: str = "auto") -> bool:
    """의존성 설치. mode: 'auto', 'gpu', 'cpu'"""
    print("  패키지 설치 중...")

    run_cmd([PY, "-m", "pip", "install", "--upgrade", "pip", "-q",
             "--disable-pip-version-check"], capture_output=True)

    if mode == "cpu":
        req = BASE_DIR / "scripts" / "windows" / "requirements-cpu.txt"
    else:
        req = BASE_DIR / "requirements-ml.txt"

    if not req.exists():
        fail(f"requirements 파일 없음: {req}")
        return False

    result = run_cmd(
        [PY, "-m", "pip", "install", "-r", str(req), "-q", "--disable-pip-version-check"],
        capture_output=True, text=True, timeout=600,
    )

    if result.returncode != 0:
        if mode != "cpu":
            warn("GPU 패키지 실패. CPU 전용 패키지 설치 시도...")
            return install_deps("cpu")
        fail("패키지 설치 실패")
        return False

    ok("패키지 설치 완료")
    return True


# ═══════════════════════════════════════════
# 3. 테스트
# ═══════════════════════════════════════════
def run_tests() -> bool:
    print("  테스트 실행 중...")
    result = run_cmd(
        [PY, "-m", "pytest", "tests/unit/", "-q", "--tb=no",
         "-k", "not health and not connection"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode == 0:
        # 결과 파싱
        last_line = result.stdout.strip().split("\n")[-1] if result.stdout else ""
        ok(f"테스트 통과 ({last_line})")
        return True
    else:
        warn("일부 테스트 실패")
        print(f"     {result.stdout.strip().split(chr(10))[-1] if result.stdout else ''}")
        return False


# ═══════════════════════════════════════════
# 4. 데모
# ═══════════════════════════════════════════
def run_demo():
    print()
    print("=" * 56)
    print("  NARA-AI 데모")
    print("=" * 56)

    print("\n--- PII 탐지 데모 ---")
    run_cmd([PY, "src/main.py", "--mode", "pii-demo"])

    print("\n--- OCR 후처리 데모 ---")
    run_cmd([PY, "src/main.py", "--mode", "ocr-demo"])

    print("\n--- 벤치마크 ---")
    run_cmd([PY, "src/main.py", "--mode", "benchmark"])


def run_cpu_search_demo():
    """CPU 전용 검색 데모"""
    print("\n--- CPU 검색 데모 (TF-IDF + BM25) ---")
    run_cmd([PY, "-c", """
import sys; sys.stdout.reconfigure(encoding='utf-8')
from src.search.embedding.cpu_embedder import CPUEmbedder

embedder = CPUEmbedder(db_path='data/db/demo_vectors.pkl')

documents = [
    {"id": "1", "title": "2024년 정부혁신 추진계획", "content": "행정안전부는 디지털 정부혁신, 국민참여, 정부내부 혁신 3대 전략을 추진한다."},
    {"id": "2", "title": "기록물 관리 지침", "content": "국가기록원은 공공기록물법에 따라 기록물의 효율적 보존과 관리를 수행한다."},
    {"id": "3", "title": "비밀해제 심사 기준", "content": "30년 경과 비공개 기록물은 공공기록물법 제34조에 따라 공개 전환 심사를 실시한다."},
    {"id": "4", "title": "국방 전략 보고서", "content": "국방부는 한반도 안보 환경 변화에 대응하기 위한 국가안보전략을 수립하였다."},
    {"id": "5", "title": "OCR 디지털화 사업", "content": "비전자기록물 100만 페이지를 OCR 기술로 디지털 텍스트로 변환하는 사업을 추진한다."},
]

count = embedder.index_documents(documents)
print(f'  인덱싱 완료: {count}건')
print()

queries = ['기록물 관리', '비밀해제 공개', '국방 안보']
for q in queries:
    results = embedder.search(q, top_k=3)
    print(f'  검색: "{q}"')
    for i, r in enumerate(results):
        print(f'    [{i+1}] {r.title} (점수: {r.score:.4f})')
    print()
"""])


# ═══════════════════════════════════════════
# 5. 서버
# ═══════════════════════════════════════════
def start_server(host: str = "127.0.0.1", port: int = 8002):
    print()
    print("=" * 56)
    print("  NARA-AI 임베딩 서버 시작")
    print("=" * 56)
    print(f"  웹 UI:     http://{host}:{port}")
    print(f"  API 문서:  http://{host}:{port}/docs")
    print(f"  헬스체크:  http://{host}:{port}/health")
    print()
    print("  종료: Ctrl+C")
    print("=" * 56)
    print()

    try:
        run_cmd([PY, "-m", "uvicorn", "src.search.embedding.server:app",
                 "--host", host, "--port", str(port), "--reload"])
    except KeyboardInterrupt:
        print("\n  서버 종료")


# ═══════════════════════════════════════════
# 전체 실행
# ═══════════════════════════════════════════
def cmd_full(host: str, port: int, cpu_mode: bool):
    banner()

    print("[1/5] 환경 확인")
    if not check_python():
        sys.exit(1)
    gpu = check_gpu()
    if cpu_mode:
        gpu = "cpu"
        os.environ["NARA_MODE"] = "cpu"
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    check_env()
    ensure_dirs()

    mode = "cpu" if gpu == "cpu" else "auto"
    print(f"\n[2/5] 패키지 확인 (모드: {mode})")
    install_deps(mode)

    print(f"\n[3/5] 테스트")
    run_tests()

    print(f"\n[4/5] 데모")
    run_demo()
    if gpu == "cpu":
        run_cpu_search_demo()

    print(f"\n[5/5] 서버 시작")
    start_server(host, port)


def show_troubleshoot():
    print()
    print("  문제 해결 가이드:")
    print(f"    설정:  {'notepad .env' if IS_WIN else 'nano .env'}")
    print("    테스트: python run.py --test")
    print("    CPU:   python run.py --cpu")
    print("    문서:  docs/tdd/technical-design.md")
    print()


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="NARA-AI v1.0 - 국가기록원 AI 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python run.py              전체 자동 실행
  python run.py --cpu        CPU 전용 모드 (노트북/RTX 3060)
  python run.py --setup      초기 설정
  python run.py --test       테스트 실행
  python run.py --demo       데모 실행
  python run.py --server     서버 시작
  python run.py --benchmark  벤치마크
""",
    )
    p.add_argument("--setup", action="store_true", help="초기 설정 (.env + 패키지)")
    p.add_argument("--check", action="store_true", help="환경 점검")
    p.add_argument("--test", action="store_true", help="테스트 실행")
    p.add_argument("--demo", action="store_true", help="데모 실행")
    p.add_argument("--server", action="store_true", help="서버 시작")
    p.add_argument("--benchmark", action="store_true", help="벤치마크")
    p.add_argument("--cpu", action="store_true", help="CPU 전용 모드")
    p.add_argument("--host", default="127.0.0.1", help="호스트 (기본: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8002, help="포트 (기본: 8002)")
    args = p.parse_args()

    os.chdir(str(BASE_DIR))

    if args.cpu:
        os.environ["NARA_MODE"] = "cpu"
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    if args.setup:
        banner()
        print("[설정] 초기 설정")
        check_python()
        check_env()
        ensure_dirs()
        install_deps("cpu" if args.cpu else "auto")
    elif args.check:
        banner()
        print("[점검] 환경 확인")
        check_python()
        check_gpu()
        check_env()
        ensure_dirs()
        ok("환경 점검 완료")
    elif args.test:
        banner()
        os.environ["PYTHONPATH"] = str(BASE_DIR)
        run_tests()
    elif args.demo:
        banner()
        os.environ["PYTHONPATH"] = str(BASE_DIR)
        run_demo()
        if args.cpu:
            run_cpu_search_demo()
    elif args.server:
        banner()
        os.environ["PYTHONPATH"] = str(BASE_DIR)
        start_server(args.host, args.port)
    elif args.benchmark:
        banner()
        os.environ["PYTHONPATH"] = str(BASE_DIR)
        run_cmd([PY, "src/main.py", "--mode", "benchmark"])
    else:
        cmd_full(args.host, args.port, args.cpu)


if __name__ == "__main__":
    main()
