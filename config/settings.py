# -*- coding: utf-8 -*-
"""
NARA-AI 설정 관리 모듈

환경 변수(.env)에서 설정을 로드한다.
GPU/CPU 모드 자동 감지, 서비스 포트, 모델 경로 등.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv 미설치 시 환경 변수만 사용


class Settings:
    """NARA-AI 전체 설정"""

    # ── 프로젝트 ──
    PROJECT_NAME: str = "NARA-AI"
    VERSION: str = "1.0.0"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # ── 실행 모드 ──
    MODE: str = os.getenv("NARA_MODE", "auto")  # "auto" | "gpu" | "cpu"

    # ── 서버 포트 ──
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8080"))
    EMBEDDING_PORT: int = int(os.getenv("EMBEDDING_PORT", "8002"))
    VLLM_LLM_PORT: int = int(os.getenv("VLLM_LLM_PORT", "8000"))
    VLLM_OCR_PORT: int = int(os.getenv("VLLM_OCR_PORT", "8001"))

    # ── MCP 서버 포트 ──
    MCP_ARCHIVE_PORT: int = int(os.getenv("MCP_ARCHIVE_PORT", "3001"))
    MCP_IARNA_PORT: int = int(os.getenv("MCP_IARNA_PORT", "3002"))
    MCP_NARA_PORT: int = int(os.getenv("MCP_NARA_PORT", "3003"))
    MCP_LAW_PORT: int = int(os.getenv("MCP_LAW_PORT", "3004"))
    MCP_RAMP_PORT: int = int(os.getenv("MCP_RAMP_PORT", "3005"))

    # ── 모델 ──
    LLM_MODEL: str = os.getenv("VLLM_LLM_MODEL", "checkpoints/nara-sft-v1")
    OCR_MODEL: str = os.getenv("VLLM_OCR_MODEL", "Qwen/Qwen3-VL-8B")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "upskyy/bge-m3-korean")
    SERVED_MODEL_NAME: str = "nara-classifier-v1"

    # ── 데이터 경로 ──
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DIR: Path = DATA_DIR / "processed"
    TEST_DIR: Path = DATA_DIR / "test"
    DB_DIR: Path = DATA_DIR / "db"
    EMBEDDINGS_DIR: Path = DATA_DIR / "embeddings"

    # ── Milvus ──
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "nara_records")
    EMBEDDING_DIM: int = 1024

    # ── 감사추적 ──
    AUDIT_DIR: Path = BASE_DIR / "_workspace" / "audit"
    AUDIT_RETENTION_DAYS: int = int(os.getenv("AUDIT_RETENTION_DAYS", "3650"))  # 10년

    # ── 보안 ──
    JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")
    JWT_ACCESS_EXPIRY: int = int(os.getenv("JWT_ACCESS_EXPIRY", "3600"))

    # ── CPU 검색 ──
    CPU_VECTORS_PATH: Path = DB_DIR / "cpu_vectors.pkl"

    # ── 하드웨어 프로파일 (캐시) ──
    _system_profile = None

    @classmethod
    def get_system_profile(cls):
        """하드웨어 프로파일 (지연 로드 + 캐시)"""
        if cls._system_profile is None:
            try:
                from config.hardware_profiles import detect_system
                cls._system_profile = detect_system()
            except Exception:
                cls._system_profile = None
        return cls._system_profile

    @classmethod
    def is_cpu_mode(cls) -> bool:
        """CPU 전용 모드 여부"""
        if cls.MODE == "cpu":
            return True
        if cls.MODE == "auto":
            profile = cls.get_system_profile()
            if profile:
                return profile.recommended_mode == "cpu"
            try:
                import torch
                return not (torch.cuda.is_available() and torch.cuda.device_count() > 0)
            except (ImportError, AssertionError):
                return True
        return False

    @classmethod
    def get_gpu_tier(cls) -> str:
        """GPU 등급 반환: 'datacenter', 'workstation', 'consumer', 'none'"""
        profile = cls.get_system_profile()
        if profile and profile.gpus:
            return profile.gpus[0].tier.value
        return "none"

    @classmethod
    def get_recommended_model(cls) -> str:
        """추천 모델 크기: '8b', '3b', '1.5b'"""
        profile = cls.get_system_profile()
        if profile and profile.gpus:
            return profile.gpus[0].recommended_model_size
        return "3b"

    @classmethod
    def ensure_dirs(cls):
        """필수 디렉토리 생성"""
        for d in [cls.RAW_DIR, cls.PROCESSED_DIR, cls.TEST_DIR, cls.DB_DIR,
                  cls.EMBEDDINGS_DIR, cls.AUDIT_DIR,
                  cls.BASE_DIR / "checkpoints", cls.BASE_DIR / "logs"]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def dump(cls) -> dict:
        """설정 덤프 (디버깅용, 비밀키 제외)"""
        profile = cls.get_system_profile()
        gpu_info = "없음"
        if profile and profile.gpus:
            g = profile.gpus[0]
            gpu_info = f"{g.name} ({g.vram_gb:.0f}GB, {g.tier.value})"

        return {
            "project": cls.PROJECT_NAME,
            "version": cls.VERSION,
            "mode": "cpu" if cls.is_cpu_mode() else "gpu",
            "gpu_tier": cls.get_gpu_tier(),
            "gpu": gpu_info,
            "recommended_model": cls.get_recommended_model(),
            "api_port": cls.API_PORT,
            "embedding_port": cls.EMBEDDING_PORT,
            "milvus": f"{cls.MILVUS_HOST}:{cls.MILVUS_PORT}",
            "data_dir": str(cls.DATA_DIR),
            "model": cls.SERVED_MODEL_NAME,
        }


settings = Settings()
