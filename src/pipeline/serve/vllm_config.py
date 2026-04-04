"""
NARA-AI 적응형 vLLM 멀티모델 서빙 설정

하드웨어 프로파일 기반으로 최적 설정을 자동 결정한다.
B200 ~ RTX 3060까지 모든 GPU에서 동작.
CPU 전용 모드에서는 vLLM 대신 경량 추론 사용.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VLLMServerConfig:
    """vLLM 서버 설정"""
    name: str
    model: str
    port: int
    tensor_parallel_size: int = 1
    max_model_len: int = 4096
    gpu_memory_utilization: float = 0.90
    dtype: str = "bfloat16"
    gpu_ids: list[int] | None = None
    quantization: str | None = None  # "awq", "gptq", "squeezellm", None
    extra_args: dict[str, Any] = field(default_factory=dict)

    def to_cli_args(self) -> list[str]:
        """vLLM CLI 인자로 변환"""
        args = [
            "--model", self.model,
            "--port", str(self.port),
            "--tensor-parallel-size", str(self.tensor_parallel_size),
            "--max-model-len", str(self.max_model_len),
            "--gpu-memory-utilization", str(self.gpu_memory_utilization),
            "--dtype", self.dtype,
            "--served-model-name", self.name,
            "--enable-prefix-caching",
        ]
        if self.quantization:
            args.extend(["--quantization", self.quantization])
        for k, v in self.extra_args.items():
            args.extend([f"--{k}", str(v)])
        return args

    def to_env_vars(self) -> dict[str, str]:
        """환경 변수로 변환"""
        env = {
            f"VLLM_{self.name.upper().replace('-', '_')}_MODEL": self.model,
            f"VLLM_{self.name.upper().replace('-', '_')}_PORT": str(self.port),
        }
        if self.gpu_ids:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in self.gpu_ids)
        return env


# ─── 서비스 포트 매핑 ───

SERVICE_PORTS = {
    "vllm_llm": 8000,
    "vllm_ocr": 8001,
    "embedding": 8002,
    "milvus": 19530,
    "mcp_archive": 3001,
    "mcp_iarna": 3002,
    "mcp_nara": 3003,
    "mcp_law": 3004,
    "mcp_ramp": 3005,
    "orchestrator": 8080,
    "prometheus": 9090,
    "grafana": 3000,
}


# ─── 적응형 설정 생성 ───

def get_serving_configs_adaptive(
    system_profile: Any = None,
) -> dict[str, VLLMServerConfig]:
    """하드웨어 프로파일 기반 최적 vLLM 설정을 자동 생성한다.

    감지된 GPU 종류와 수에 따라:
    - 데이터센터 (B200/H100/A100): 텐서 병렬 최대 활용, 8B 모델 풀 정밀도
    - 워크스테이션 (RTX 5090/4090): 적당한 TP, 8B 모델
    - 소비자 (RTX 4060/3060): TP=1, 3B 모델 + int8 양자화
    """
    if system_profile is None:
        from config.hardware_profiles import detect_system
        system_profile = detect_system()

    gpus = system_profile.gpus
    gpu_count = len(gpus)

    if gpu_count == 0:
        return {}  # CPU 모드 — vLLM 사용 안 함

    primary_gpu = gpus[0]
    configs: dict[str, VLLMServerConfig] = {}

    # ── 데이터센터 GPU (B200, H100, A100) ──
    if primary_gpu.tier.value == "datacenter":
        llm_tp = min(4, gpu_count)
        ocr_tp = min(2, max(1, gpu_count - llm_tp))
        llm_gpus = list(range(llm_tp))
        ocr_gpus = list(range(llm_tp, llm_tp + ocr_tp))

        configs["llm"] = VLLMServerConfig(
            name="nara-classifier-v1",
            model="checkpoints/nara-sft-v1",
            port=8000,
            tensor_parallel_size=llm_tp,
            max_model_len=primary_gpu.recommended_max_model_len,
            gpu_memory_utilization=primary_gpu.gpu_memory_utilization,
            dtype=primary_gpu.recommended_dtype,
            gpu_ids=llm_gpus,
        )
        if ocr_tp > 0:
            configs["ocr"] = VLLMServerConfig(
                name="nara-ocr-v1",
                model="Qwen/Qwen3-VL-8B",
                port=8001,
                tensor_parallel_size=ocr_tp,
                max_model_len=min(8192, primary_gpu.recommended_max_model_len * 2),
                gpu_memory_utilization=primary_gpu.gpu_memory_utilization,
                dtype=primary_gpu.recommended_dtype,
                gpu_ids=ocr_gpus,
            )

    # ── 워크스테이션 GPU (RTX 5090, 4090) ──
    elif primary_gpu.tier.value == "workstation":
        configs["llm"] = VLLMServerConfig(
            name="nara-classifier-v1",
            model="checkpoints/nara-sft-v1",
            port=8000,
            tensor_parallel_size=min(primary_gpu.max_tensor_parallel, gpu_count),
            max_model_len=primary_gpu.recommended_max_model_len,
            gpu_memory_utilization=primary_gpu.gpu_memory_utilization,
            dtype=primary_gpu.recommended_dtype,
            gpu_ids=[0] if gpu_count == 1 else [0, 1],
        )
        if gpu_count >= 2:
            configs["ocr"] = VLLMServerConfig(
                name="nara-ocr-v1",
                model="Qwen/Qwen3-VL-8B",
                port=8001,
                tensor_parallel_size=1,
                max_model_len=2048,
                gpu_memory_utilization=primary_gpu.gpu_memory_utilization,
                dtype=primary_gpu.recommended_dtype,
                gpu_ids=[gpu_count - 1],
            )

    # ── 소비자 GPU (RTX 4060, 3060 등) ──
    else:
        # 소형 GPU: 3B 모델 + int8 양자화 권장
        model_size = primary_gpu.recommended_model_size
        quant = primary_gpu.quantization if primary_gpu.quantization != "none" else None

        configs["llm"] = VLLMServerConfig(
            name="nara-classifier-v1",
            model=f"checkpoints/nara-sft-{model_size}-v1" if model_size != "8b" else "checkpoints/nara-sft-v1",
            port=8000,
            tensor_parallel_size=1,
            max_model_len=primary_gpu.recommended_max_model_len,
            gpu_memory_utilization=primary_gpu.gpu_memory_utilization,
            dtype=primary_gpu.recommended_dtype,
            gpu_ids=[0],
            quantization=quant,
        )
        # 소형 GPU에서 OCR은 CPU로 폴백
        # configs["ocr"] 는 생성하지 않음

    return configs


def get_serving_configs(gpu_count: int = 8) -> dict[str, VLLMServerConfig]:
    """레거시 호환: GPU 수 기반 설정 (기존 코드 호환)"""
    try:
        return get_serving_configs_adaptive()
    except Exception:
        # 폴백: 하드코딩 설정
        if gpu_count >= 16:
            return {
                "llm": VLLMServerConfig(
                    name="nara-classifier-v1", model="checkpoints/nara-sft-v1",
                    port=8000, tensor_parallel_size=4, max_model_len=4096, gpu_ids=[0, 1, 2, 3],
                ),
                "ocr": VLLMServerConfig(
                    name="nara-ocr-v1", model="Qwen/Qwen3-VL-8B",
                    port=8001, tensor_parallel_size=2, max_model_len=8192, gpu_ids=[4, 5],
                ),
            }
        elif gpu_count >= 8:
            return {
                "llm": VLLMServerConfig(
                    name="nara-classifier-v1", model="checkpoints/nara-sft-v1",
                    port=8000, tensor_parallel_size=2, max_model_len=4096, gpu_ids=[0, 1],
                ),
                "ocr": VLLMServerConfig(
                    name="nara-ocr-v1", model="Qwen/Qwen3-VL-8B",
                    port=8001, tensor_parallel_size=1, max_model_len=8192, gpu_ids=[2],
                ),
            }
        else:
            return {
                "llm": VLLMServerConfig(
                    name="nara-classifier-v1", model="checkpoints/nara-sft-v1",
                    port=8000, tensor_parallel_size=1, max_model_len=2048, gpu_ids=[0],
                ),
            }


def print_serving_plan(configs: dict[str, VLLMServerConfig]) -> None:
    """서빙 계획 출력"""
    if not configs:
        print("  [CPU 모드] vLLM 서빙 없음 → TF-IDF/BM25 검색 사용")
        return

    for name, cfg in configs.items():
        quant = f", 양자화={cfg.quantization}" if cfg.quantization else ""
        gpus = f", GPU={cfg.gpu_ids}" if cfg.gpu_ids else ""
        print(f"  [{name}] {cfg.model}")
        print(f"    포트={cfg.port}, TP={cfg.tensor_parallel_size}, "
              f"max_len={cfg.max_model_len}, dtype={cfg.dtype}{quant}{gpus}")
