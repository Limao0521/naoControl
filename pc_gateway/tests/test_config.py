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


def test_network_broker_is_disabled_by_default() -> None:
    settings = GatewaySettings.from_env(valid_environment())

    assert settings.network_broker_enabled is False
    assert settings.network_broker_host == "127.0.0.1"
    assert settings.network_broker_port == 6675


def test_enabled_network_broker_uses_robot_origin_and_existing_ssh_key(tmp_path) -> None:
    key_path = tmp_path / "nao_control_ed25519"
    key_path.write_text("test-key-placeholder", encoding="utf-8")

    settings = GatewaySettings.from_env(
        valid_environment(
            NAO_GATEWAY_URL="ws://169.254.1.2:6674",
            NAO_NETWORK_BROKER_ENABLED="true",
            NAO_SSH_KEY=str(key_path),
        )
    )

    assert settings.network_broker_enabled is True
    assert settings.nao_ssh_host == "169.254.1.2"
    assert settings.nao_ssh_user == "nao"
    assert settings.nao_ssh_key == str(key_path.resolve())
    assert settings.network_allowed_origins == ("http://169.254.1.2:3000",)


def test_enabled_network_broker_requires_existing_ssh_key(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="NAO_SSH_KEY"):
        GatewaySettings.from_env(
            valid_environment(
                NAO_NETWORK_BROKER_ENABLED="true",
                NAO_SSH_KEY=str(tmp_path / "missing"),
            )
        )


def test_network_origin_must_not_contain_path(tmp_path) -> None:
    key_path = tmp_path / "nao_control_ed25519"
    key_path.write_text("test-key-placeholder", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="origin"):
        GatewaySettings.from_env(
            valid_environment(
                NAO_NETWORK_BROKER_ENABLED="true",
                NAO_SSH_KEY=str(key_path),
                NAO_NETWORK_ALLOWED_ORIGINS="http://169.254.1.2:3000/admin",
            )
        )
