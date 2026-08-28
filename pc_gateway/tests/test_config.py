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


def test_local_provider_configuration_does_not_require_nvidia_key() -> None:
    """Forcing an NVIDIA key would prevent an entirely local Gemma deployment."""
    environment = valid_environment(INTELLIGENCE_PROVIDER="gemma_local")
    del environment["NVIDIA_API_KEY"]

    settings = GatewaySettings.from_env(environment)

    assert settings.default_provider == "gemma_local"
    assert settings.nvidia_api_key == ""
    assert settings.gemma_base_url == "http://127.0.0.1:8080/v1"


def test_authenticated_private_lan_gemma_endpoint_is_allowed() -> None:
    environment = valid_environment(
        INTELLIGENCE_PROVIDER="gemma_local",
        GEMMA_BASE_URL="http://172.23.12.52:8080/v1",
        GEMMA_API_KEY="private-lan-test-key",
    )
    del environment["NVIDIA_API_KEY"]

    settings = GatewaySettings.from_env(environment)

    assert settings.gemma_base_url == "http://172.23.12.52:8080/v1"
    assert settings.gemma_api_key == "private-lan-test-key"


def test_private_lan_gemma_endpoint_requires_api_key() -> None:
    environment = valid_environment(
        INTELLIGENCE_PROVIDER="gemma_local",
        GEMMA_BASE_URL="http://172.23.12.52:8080/v1",
    )
    del environment["NVIDIA_API_KEY"]

    with pytest.raises(ConfigurationError, match="GEMMA_API_KEY"):
        GatewaySettings.from_env(environment)


def test_public_gemma_endpoint_is_rejected_even_with_api_key() -> None:
    environment = valid_environment(
        GEMMA_BASE_URL="http://8.8.8.8:8080/v1",
        GEMMA_API_KEY="must-not-authorize-public-destinations",
    )

    with pytest.raises(ConfigurationError, match="private network"):
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


def test_legacy_network_broker_values_do_not_affect_gateway_settings() -> None:
    baseline = GatewaySettings.from_env(valid_environment())
    with_legacy_values = GatewaySettings.from_env(
        valid_environment(
            NAO_NETWORK_HOST="169.254.197.40",
            NAO_NETWORK_BROKER_PORT="6675",
            NAO_SSH_KEY="C:/keys/obsolete",
        )
    )

    assert with_legacy_values == baseline
