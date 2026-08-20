from __future__ import annotations

import pytest

from nao_gateway.config import ConfigurationError, GatewaySettings


def valid_environment(**overrides: str) -> dict[str, str]:
    environment = {
        "NVIDIA_API_KEY": "test-nvidia-key",
        "NVIDIA_ASR_URL": "https://speech.example.test/v1/transcribe",
        "NAO_GATEWAY_SECRET": "test-shared-secret-with-enough-entropy",
    }
    environment.update(overrides)
    return environment


def test_settings_require_all_secrets() -> None:
    environment = valid_environment()
    del environment["NVIDIA_API_KEY"]

    with pytest.raises(ConfigurationError, match="NVIDIA_API_KEY"):
        GatewaySettings.from_env(environment)


def test_nvidia_base_url_must_use_https() -> None:
    environment = valid_environment(NVIDIA_BASE_URL="http://example.test/v1")

    with pytest.raises(ConfigurationError, match="HTTPS"):
        GatewaySettings.from_env(environment)


def test_settings_use_documented_nemotron_defaults() -> None:
    settings = GatewaySettings.from_env(valid_environment())

    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.agent_model == "nvidia/nemotron-3-nano-30b-a3b"
    assert settings.vision_model == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    assert settings.robot_url == "ws://nao.local:6674"


def test_omni_perception_does_not_require_separate_asr_endpoint() -> None:
    environment = valid_environment()
    del environment["NVIDIA_ASR_URL"]

    settings = GatewaySettings.from_env(environment)

    assert settings.asr_url == ""
