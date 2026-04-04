# -*- coding: utf-8 -*-
"""
NARA-AI 하드웨어 프로파일 시스템

GPU 6종 (B200, H100, A100, RTX 5090, RTX 4060, RTX 3060)
CPU 3종 (x86 Intel, x86 AMD, ARM64)
GPU 벤더 3종 (NVIDIA CUDA, AMD ROCm, Intel oneAPI)
OS 3종 (Windows, Linux, macOS)

모든 조합에서 최적의 설정을 자동 결정한다.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════
# GPU 프로파일
# ═══════════════════════════════════════════

class GPUTier(str, Enum):
    """GPU 등급"""
    DATACENTER = "datacenter"    # B200, H100, A100
    WORKSTATION = "workstation"  # RTX 5090, RTX 6000 Ada
    CONSUMER = "consumer"        # RTX 4060, 3060
    NONE = "none"                # GPU 없음


class GPUVendor(str, Enum):
    """GPU 벤더"""
    NVIDIA = "nvidia"   # CUDA
    AMD = "amd"         # ROCm
    INTEL = "intel"     # oneAPI / Level Zero
    APPLE = "apple"     # Metal (Apple Silicon)
    NONE = "none"


class CPUArch(str, Enum):
    """CPU 아키텍처"""
    X86_INTEL = "x86_intel"
    X86_AMD = "x86_amd"
    ARM64 = "arm64"
    UNKNOWN = "unknown"


class OSType(str, Enum):
    """운영체제"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


@dataclass
class GPUProfile:
    """개별 GPU 프로파일"""
    name: str                    # "B200", "H100", "RTX 4060" 등
    codename: str                # "b200", "h100", "rtx4060" 등
    tier: GPUTier
    vendor: GPUVendor
    vram_gb: float               # VRAM (GB)
    bandwidth_gbps: float        # 메모리 대역폭 (GB/s)
    # vLLM 추론 설정
    max_tensor_parallel: int     # 최대 텐서 병렬
    recommended_max_model_len: int  # 권장 max_model_len
    recommended_dtype: str       # "bfloat16", "float16", "int8"
    gpu_memory_utilization: float  # vLLM GPU 메모리 사용률
    # 학습 설정
    can_train_8b: bool           # 8B 모델 학습 가능 여부
    can_train_70b: bool          # 70B 모델 학습 가능 여부
    recommended_batch_size: int  # 추천 배치 크기
    # 모델 추천
    recommended_model_size: str  # "8b", "3b", "1.5b"
    quantization: str            # "none", "int8", "int4"


@dataclass
class CPUProfile:
    """CPU 프로파일"""
    arch: CPUArch
    vendor: str           # "Intel", "AMD", "Apple", "ARM"
    name: str             # CPU 이름
    cores: int
    # 검색 모드
    search_mode: str      # "tfidf_bm25", "onnx", "openvino"
    supports_onnx: bool
    supports_openvino: bool  # Intel CPU 전용


@dataclass
class SystemProfile:
    """시스템 전체 프로파일"""
    os: OSType
    os_version: str
    cpu: CPUProfile
    gpus: list[GPUProfile]
    gpu_vendor: GPUVendor
    gpu_count: int
    total_vram_gb: float
    # 추천 모드
    recommended_mode: str  # "gpu", "cpu", "hybrid"
    # 실행 환경
    python_version: str
    has_cuda: bool
    has_rocm: bool
    has_oneapi: bool
    has_metal: bool


# ═══════════════════════════════════════════
# GPU 프로파일 데이터베이스
# ═══════════════════════════════════════════

GPU_DATABASE: dict[str, GPUProfile] = {
    # ── 데이터센터 GPU ──
    "b200": GPUProfile(
        name="NVIDIA B200", codename="b200", tier=GPUTier.DATACENTER,
        vendor=GPUVendor.NVIDIA, vram_gb=192, bandwidth_gbps=8000,
        max_tensor_parallel=16, recommended_max_model_len=8192,
        recommended_dtype="bfloat16", gpu_memory_utilization=0.92,
        can_train_8b=True, can_train_70b=True, recommended_batch_size=32,
        recommended_model_size="8b", quantization="none",
    ),
    "h100": GPUProfile(
        name="NVIDIA H100", codename="h100", tier=GPUTier.DATACENTER,
        vendor=GPUVendor.NVIDIA, vram_gb=80, bandwidth_gbps=2000,
        max_tensor_parallel=8, recommended_max_model_len=4096,
        recommended_dtype="bfloat16", gpu_memory_utilization=0.90,
        can_train_8b=True, can_train_70b=True, recommended_batch_size=16,
        recommended_model_size="8b", quantization="none",
    ),
    "a100": GPUProfile(
        name="NVIDIA A100", codename="a100", tier=GPUTier.DATACENTER,
        vendor=GPUVendor.NVIDIA, vram_gb=80, bandwidth_gbps=2000,
        max_tensor_parallel=8, recommended_max_model_len=4096,
        recommended_dtype="bfloat16", gpu_memory_utilization=0.90,
        can_train_8b=True, can_train_70b=True, recommended_batch_size=16,
        recommended_model_size="8b", quantization="none",
    ),
    # ── 워크스테이션 / 하이엔드 소비자 GPU ──
    "rtx5090": GPUProfile(
        name="NVIDIA RTX 5090", codename="rtx5090", tier=GPUTier.WORKSTATION,
        vendor=GPUVendor.NVIDIA, vram_gb=32, bandwidth_gbps=1792,
        max_tensor_parallel=2, recommended_max_model_len=2048,
        recommended_dtype="bfloat16", gpu_memory_utilization=0.88,
        can_train_8b=True, can_train_70b=False, recommended_batch_size=8,
        recommended_model_size="8b", quantization="none",
    ),
    "rtx4090": GPUProfile(
        name="NVIDIA RTX 4090", codename="rtx4090", tier=GPUTier.WORKSTATION,
        vendor=GPUVendor.NVIDIA, vram_gb=24, bandwidth_gbps=1008,
        max_tensor_parallel=1, recommended_max_model_len=2048,
        recommended_dtype="bfloat16", gpu_memory_utilization=0.88,
        can_train_8b=True, can_train_70b=False, recommended_batch_size=4,
        recommended_model_size="8b", quantization="none",
    ),
    # ── 소비자 GPU ──
    "rtx4060": GPUProfile(
        name="NVIDIA RTX 4060", codename="rtx4060", tier=GPUTier.CONSUMER,
        vendor=GPUVendor.NVIDIA, vram_gb=8, bandwidth_gbps=272,
        max_tensor_parallel=1, recommended_max_model_len=1024,
        recommended_dtype="float16", gpu_memory_utilization=0.85,
        can_train_8b=False, can_train_70b=False, recommended_batch_size=1,
        recommended_model_size="3b", quantization="int8",
    ),
    "rtx4060_laptop": GPUProfile(
        name="NVIDIA RTX 4060 Laptop", codename="rtx4060_laptop", tier=GPUTier.CONSUMER,
        vendor=GPUVendor.NVIDIA, vram_gb=8, bandwidth_gbps=256,
        max_tensor_parallel=1, recommended_max_model_len=1024,
        recommended_dtype="float16", gpu_memory_utilization=0.82,
        can_train_8b=False, can_train_70b=False, recommended_batch_size=1,
        recommended_model_size="3b", quantization="int8",
    ),
    "rtx3060": GPUProfile(
        name="NVIDIA RTX 3060", codename="rtx3060", tier=GPUTier.CONSUMER,
        vendor=GPUVendor.NVIDIA, vram_gb=12, bandwidth_gbps=360,
        max_tensor_parallel=1, recommended_max_model_len=1024,
        recommended_dtype="float16", gpu_memory_utilization=0.85,
        can_train_8b=False, can_train_70b=False, recommended_batch_size=2,
        recommended_model_size="3b", quantization="int8",
    ),
    # ── AMD GPU (ROCm) ──
    "mi300x": GPUProfile(
        name="AMD Instinct MI300X", codename="mi300x", tier=GPUTier.DATACENTER,
        vendor=GPUVendor.AMD, vram_gb=192, bandwidth_gbps=5300,
        max_tensor_parallel=8, recommended_max_model_len=8192,
        recommended_dtype="bfloat16", gpu_memory_utilization=0.90,
        can_train_8b=True, can_train_70b=True, recommended_batch_size=16,
        recommended_model_size="8b", quantization="none",
    ),
    "rx7900xtx": GPUProfile(
        name="AMD RX 7900 XTX", codename="rx7900xtx", tier=GPUTier.CONSUMER,
        vendor=GPUVendor.AMD, vram_gb=24, bandwidth_gbps=960,
        max_tensor_parallel=1, recommended_max_model_len=2048,
        recommended_dtype="float16", gpu_memory_utilization=0.85,
        can_train_8b=True, can_train_70b=False, recommended_batch_size=4,
        recommended_model_size="8b", quantization="none",
    ),
    # ── Intel GPU ──
    "arc_a770": GPUProfile(
        name="Intel Arc A770", codename="arc_a770", tier=GPUTier.CONSUMER,
        vendor=GPUVendor.INTEL, vram_gb=16, bandwidth_gbps=560,
        max_tensor_parallel=1, recommended_max_model_len=1024,
        recommended_dtype="float16", gpu_memory_utilization=0.80,
        can_train_8b=False, can_train_70b=False, recommended_batch_size=2,
        recommended_model_size="3b", quantization="int8",
    ),
}

# GPU 이름 매칭 패턴 (torch.cuda.get_device_name() 결과와 대조)
GPU_NAME_PATTERNS: list[tuple[str, str]] = [
    # NVIDIA 데이터센터
    (r"b200", "b200"),
    (r"b100", "b200"),  # B100도 B200 프로파일 사용
    (r"h100", "h100"),
    (r"h200", "h100"),  # H200도 H100 프로파일
    (r"a100", "a100"),
    (r"a6000", "rtx4090"),  # A6000은 RTX 4090급
    # NVIDIA 소비자
    (r"5090", "rtx5090"),
    (r"5080", "rtx5090"),
    (r"4090", "rtx4090"),
    (r"4080", "rtx4090"),
    (r"4070", "rtx4060"),
    (r"4060\s*laptop", "rtx4060_laptop"),
    (r"4060", "rtx4060"),
    (r"4050", "rtx4060"),
    (r"3090", "rtx4090"),
    (r"3080", "rtx4060"),
    (r"3070", "rtx4060"),
    (r"3060", "rtx3060"),
    (r"3050", "rtx3060"),
    # AMD
    (r"mi300", "mi300x"),
    (r"mi250", "mi300x"),
    (r"7900\s*xtx", "rx7900xtx"),
    (r"7900\s*xt", "rx7900xtx"),
    (r"7800\s*xt", "rx7900xtx"),
    # Intel
    (r"arc.*a770", "arc_a770"),
    (r"arc.*a750", "arc_a770"),
    (r"arc.*a580", "arc_a770"),
]


# ═══════════════════════════════════════════
# 하드웨어 감지 함수
# ═══════════════════════════════════════════

def detect_os() -> tuple[OSType, str]:
    """운영체제 감지"""
    system = platform.system()
    version = platform.version()
    if system == "Windows":
        return OSType.WINDOWS, f"Windows {platform.release()} ({version})"
    elif system == "Linux":
        return OSType.LINUX, f"Linux {platform.release()}"
    elif system == "Darwin":
        return OSType.MACOS, f"macOS {platform.mac_ver()[0]}"
    return OSType.LINUX, f"{system} {version}"


def detect_cpu() -> CPUProfile:
    """CPU 아키텍처 및 벤더 감지"""
    machine = platform.machine().lower()
    processor = platform.processor().lower()

    # 아키텍처
    if machine in ("arm64", "aarch64"):
        arch = CPUArch.ARM64
    elif machine in ("x86_64", "amd64", "x86"):
        arch = CPUArch.X86_INTEL  # 기본값, 아래에서 AMD 확인
    else:
        arch = CPUArch.UNKNOWN

    # 벤더
    vendor = "Unknown"
    cpu_name = platform.processor() or "Unknown CPU"

    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
            winreg.CloseKey(key)
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_name = line.split(":")[1].strip()
                        break
    except Exception:
        pass

    if "amd" in cpu_name.lower() or "ryzen" in cpu_name.lower():
        vendor = "AMD"
        if arch == CPUArch.X86_INTEL:
            arch = CPUArch.X86_AMD
    elif "intel" in cpu_name.lower() or "core" in cpu_name.lower():
        vendor = "Intel"
    elif "apple" in cpu_name.lower() or "m1" in cpu_name.lower() or "m2" in cpu_name.lower() or "m3" in cpu_name.lower() or "m4" in cpu_name.lower():
        vendor = "Apple"
        arch = CPUArch.ARM64

    # 코어 수
    cores = os.cpu_count() or 1

    # 검색 모드 결정
    supports_openvino = vendor == "Intel"
    supports_onnx = arch in (CPUArch.X86_INTEL, CPUArch.X86_AMD)

    if supports_openvino:
        search_mode = "openvino"
    elif supports_onnx:
        search_mode = "onnx"
    else:
        search_mode = "tfidf_bm25"

    return CPUProfile(
        arch=arch, vendor=vendor, name=cpu_name, cores=cores,
        search_mode=search_mode, supports_onnx=supports_onnx,
        supports_openvino=supports_openvino,
    )


def detect_gpu_vendor() -> GPUVendor:
    """GPU 벤더 감지 (NVIDIA/AMD/Intel/Apple)"""
    # NVIDIA CUDA
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            if hasattr(torch.version, 'hip') and torch.version.hip:
                return GPUVendor.AMD  # ROCm
            return GPUVendor.NVIDIA
    except (ImportError, AssertionError):
        pass

    # Apple Metal
    try:
        import torch
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return GPUVendor.APPLE
    except (ImportError, AttributeError):
        pass

    # Intel oneAPI
    try:
        import intel_extension_for_pytorch
        return GPUVendor.INTEL
    except ImportError:
        pass

    return GPUVendor.NONE


def classify_gpu(device_name: str, vram_gb: float) -> str:
    """GPU 이름과 VRAM으로 프로파일 코드명 반환"""
    name_lower = device_name.lower()

    # 패턴 매칭
    for pattern, codename in GPU_NAME_PATTERNS:
        if re.search(pattern, name_lower):
            return codename

    # VRAM 기반 폴백
    if vram_gb >= 80:
        return "h100"
    elif vram_gb >= 24:
        return "rtx4090"
    elif vram_gb >= 12:
        return "rtx3060"
    elif vram_gb >= 8:
        return "rtx4060"
    else:
        return "rtx3060"


def detect_all_gpus() -> list[GPUProfile]:
    """시스템의 모든 GPU를 감지하고 프로파일을 반환"""
    gpus: list[GPUProfile] = []
    vendor = detect_gpu_vendor()

    if vendor == GPUVendor.NVIDIA or vendor == GPUVendor.AMD:
        try:
            import torch
            count = torch.cuda.device_count()
            for i in range(count):
                name = torch.cuda.get_device_name(i)
                vram = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                codename = classify_gpu(name, vram)
                profile = GPU_DATABASE.get(codename)
                if profile:
                    # 실제 VRAM으로 업데이트
                    import copy
                    gpu = copy.copy(profile)
                    gpu.vram_gb = round(vram, 1)
                    gpu.name = name
                    gpus.append(gpu)
        except (ImportError, AssertionError, RuntimeError):
            pass

    elif vendor == GPUVendor.APPLE:
        # Apple Silicon은 통합 메모리
        gpus.append(GPUProfile(
            name="Apple Silicon GPU", codename="apple_metal",
            tier=GPUTier.CONSUMER, vendor=GPUVendor.APPLE,
            vram_gb=0, bandwidth_gbps=0,
            max_tensor_parallel=1, recommended_max_model_len=1024,
            recommended_dtype="float16", gpu_memory_utilization=0.80,
            can_train_8b=False, can_train_70b=False,
            recommended_batch_size=1, recommended_model_size="3b",
            quantization="int8",
        ))

    return gpus


def detect_system() -> SystemProfile:
    """시스템 전체 프로파일 감지"""
    os_type, os_version = detect_os()
    cpu = detect_cpu()
    gpus = detect_all_gpus()
    vendor = detect_gpu_vendor()

    gpu_count = len(gpus)
    total_vram = sum(g.vram_gb for g in gpus)

    # 추천 모드
    if gpu_count > 0 and total_vram >= 8:
        recommended_mode = "gpu"
    elif gpu_count > 0:
        recommended_mode = "hybrid"
    else:
        recommended_mode = "cpu"

    # 프레임워크 확인
    has_cuda = False
    has_rocm = False
    has_oneapi = False
    has_metal = False
    try:
        import torch
        has_cuda = torch.cuda.is_available() and not (hasattr(torch.version, 'hip') and torch.version.hip)
        has_rocm = hasattr(torch.version, 'hip') and bool(torch.version.hip)
        has_metal = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
    except ImportError:
        pass
    try:
        import intel_extension_for_pytorch
        has_oneapi = True
    except ImportError:
        pass

    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    return SystemProfile(
        os=os_type, os_version=os_version,
        cpu=cpu, gpus=gpus, gpu_vendor=vendor,
        gpu_count=gpu_count, total_vram_gb=total_vram,
        recommended_mode=recommended_mode,
        python_version=py,
        has_cuda=has_cuda, has_rocm=has_rocm,
        has_oneapi=has_oneapi, has_metal=has_metal,
    )


def print_system_report(profile: SystemProfile) -> None:
    """시스템 프로파일 리포트 출력"""
    print(f"  OS:     {profile.os_version}")
    print(f"  CPU:    {profile.cpu.name} ({profile.cpu.cores}코어, {profile.cpu.arch.value})")
    print(f"  GPU 벤더: {profile.gpu_vendor.value}")
    print(f"  GPU 수: {profile.gpu_count}개 (총 VRAM: {profile.total_vram_gb:.0f}GB)")
    for i, gpu in enumerate(profile.gpus):
        print(f"    [{i}] {gpu.name} ({gpu.vram_gb:.0f}GB, {gpu.tier.value})")
        print(f"        추천: TP={gpu.max_tensor_parallel}, max_len={gpu.recommended_max_model_len}, "
              f"dtype={gpu.recommended_dtype}, 양자화={gpu.quantization}")
        print(f"        모델: {gpu.recommended_model_size}, 학습 8B={gpu.can_train_8b}, 70B={gpu.can_train_70b}")
    if not profile.gpus:
        print(f"    GPU 없음 → CPU 모드 ({profile.cpu.search_mode})")
    print(f"  CUDA:   {profile.has_cuda}")
    print(f"  ROCm:   {profile.has_rocm}")
    print(f"  oneAPI:  {profile.has_oneapi}")
    print(f"  Metal:  {profile.has_metal}")
    print(f"  추천 모드: {profile.recommended_mode}")
