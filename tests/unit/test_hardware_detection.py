# -*- coding: utf-8 -*-
"""하드웨어 감지 시스템 테스트"""

import pytest
from config.hardware_profiles import (
    GPUTier, GPUVendor, CPUArch, OSType,
    GPUProfile, GPU_DATABASE, GPU_NAME_PATTERNS,
    classify_gpu, detect_os, detect_cpu, detect_system,
    print_system_report,
)
from src.pipeline.serve.vllm_config import (
    VLLMServerConfig, SERVICE_PORTS, get_serving_configs,
    print_serving_plan,
)


class TestGPUDatabase:
    """GPU 프로파일 데이터베이스 테스트"""

    def test_all_gpu_profiles_exist(self):
        """핵심 GPU 프로파일이 모두 정의되어야 한다"""
        required = ["b200", "h100", "a100", "rtx5090", "rtx4060", "rtx3060"]
        for code in required:
            assert code in GPU_DATABASE, f"GPU 프로파일 누락: {code}"

    def test_datacenter_gpus_high_vram(self):
        """데이터센터 GPU는 VRAM 80GB 이상이어야 한다"""
        for code in ["b200", "h100", "a100"]:
            gpu = GPU_DATABASE[code]
            assert gpu.vram_gb >= 80
            assert gpu.tier == GPUTier.DATACENTER
            assert gpu.can_train_8b is True
            assert gpu.can_train_70b is True

    def test_consumer_gpus_low_vram(self):
        """소비자 GPU는 적절한 VRAM 범위여야 한다"""
        for code in ["rtx4060", "rtx3060"]:
            gpu = GPU_DATABASE[code]
            assert gpu.vram_gb <= 16
            assert gpu.tier == GPUTier.CONSUMER

    def test_consumer_gpu_uses_quantization(self):
        """소비자 GPU는 양자화를 권장해야 한다"""
        gpu = GPU_DATABASE["rtx4060"]
        assert gpu.quantization == "int8"
        assert gpu.recommended_model_size == "3b"

    def test_amd_gpu_profiles(self):
        """AMD GPU 프로파일이 정의되어야 한다"""
        assert "mi300x" in GPU_DATABASE
        assert GPU_DATABASE["mi300x"].vendor == GPUVendor.AMD

    def test_intel_gpu_profiles(self):
        """Intel GPU 프로파일이 정의되어야 한다"""
        assert "arc_a770" in GPU_DATABASE
        assert GPU_DATABASE["arc_a770"].vendor == GPUVendor.INTEL


class TestGPUClassification:
    """GPU 이름 분류 테스트"""

    @pytest.mark.parametrize("name,expected", [
        ("NVIDIA B200", "b200"),
        ("NVIDIA H100 80GB HBM3", "h100"),
        ("NVIDIA A100-SXM4-80GB", "a100"),
        ("NVIDIA GeForce RTX 5090", "rtx5090"),
        ("NVIDIA GeForce RTX 4090", "rtx4090"),
        ("NVIDIA GeForce RTX 4060 Laptop GPU", "rtx4060_laptop"),
        ("NVIDIA GeForce RTX 4060", "rtx4060"),
        ("NVIDIA GeForce RTX 3060", "rtx3060"),
        ("AMD Instinct MI300X", "mi300x"),
    ])
    def test_classify_by_name(self, name, expected):
        result = classify_gpu(name, 0)
        assert result == expected, f"'{name}' → '{result}' (기대: '{expected}')"

    def test_classify_by_vram_fallback(self):
        """이름이 매칭되지 않을 때 VRAM 기반 폴백"""
        assert classify_gpu("Unknown GPU", 192) == "h100"
        assert classify_gpu("Unknown GPU", 24) == "rtx4090"
        assert classify_gpu("Unknown GPU", 12) == "rtx3060"
        assert classify_gpu("Unknown GPU", 8) == "rtx4060"


class TestOSDetection:
    def test_detect_os_returns_valid(self):
        os_type, version = detect_os()
        assert os_type in (OSType.WINDOWS, OSType.LINUX, OSType.MACOS)
        assert len(version) > 0


class TestCPUDetection:
    def test_detect_cpu_returns_profile(self):
        cpu = detect_cpu()
        assert cpu.arch in (CPUArch.X86_INTEL, CPUArch.X86_AMD, CPUArch.ARM64, CPUArch.UNKNOWN)
        assert cpu.cores >= 1
        assert cpu.search_mode in ("tfidf_bm25", "onnx", "openvino")

    def test_cpu_vendor_detected(self):
        cpu = detect_cpu()
        assert cpu.vendor in ("Intel", "AMD", "Apple", "ARM", "Unknown")


class TestSystemDetection:
    def test_detect_system_complete(self):
        """전체 시스템 감지가 에러 없이 완료되어야 한다"""
        profile = detect_system()
        assert profile.os in (OSType.WINDOWS, OSType.LINUX, OSType.MACOS)
        assert profile.cpu.cores >= 1
        assert profile.recommended_mode in ("gpu", "cpu", "hybrid")
        assert len(profile.python_version) > 0

    def test_print_report_no_error(self, capsys):
        """리포트 출력이 에러 없이 완료되어야 한다"""
        profile = detect_system()
        print_system_report(profile)
        captured = capsys.readouterr()
        assert "OS:" in captured.out
        assert "CPU:" in captured.out


class TestVLLMConfig:
    def test_service_ports_complete(self):
        """서비스 포트가 모두 정의되어야 한다"""
        required = ["vllm_llm", "vllm_ocr", "embedding", "milvus",
                     "mcp_archive", "mcp_iarna", "mcp_nara", "mcp_law", "mcp_ramp"]
        for name in required:
            assert name in SERVICE_PORTS

    def test_config_to_cli_args(self):
        """CLI 인자 변환이 올바라야 한다"""
        cfg = VLLMServerConfig(
            name="test", model="test-model", port=8000,
            tensor_parallel_size=2, max_model_len=4096,
        )
        args = cfg.to_cli_args()
        assert "--model" in args
        assert "test-model" in args
        assert "--tensor-parallel-size" in args
        assert "2" in args

    def test_config_with_quantization(self):
        """양자화 설정이 CLI 인자에 포함되어야 한다"""
        cfg = VLLMServerConfig(
            name="test", model="test-model", port=8000,
            quantization="awq",
        )
        args = cfg.to_cli_args()
        assert "--quantization" in args
        assert "awq" in args

    def test_legacy_get_serving_configs(self):
        """레거시 호환 함수가 동작해야 한다"""
        configs = get_serving_configs(8)
        assert "llm" in configs

    def test_print_serving_plan_no_error(self, capsys):
        """서빙 계획 출력이 에러 없이 완료되어야 한다"""
        configs = get_serving_configs(8)
        print_serving_plan(configs)
        captured = capsys.readouterr()
        assert "nara" in captured.out or "CPU 모드" in captured.out
