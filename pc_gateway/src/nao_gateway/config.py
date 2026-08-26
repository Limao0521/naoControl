"""Validated environment configuration for the PC gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when a required or security-sensitive setting is invalid."""


@dataclass(frozen=True)
class GatewaySettings:
    nvidia_api_key: str
    nvidia_base_url: str
    agent_model: str
    vision_model: str
    asr_url: str
    robot_url: str
    robot_shared_secret: str
    default_provider: str
    gemma_base_url: str
    gemma_model: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "GatewaySettings":
        default_provider = environ.get("INTELLIGENCE_PROVIDER", "nemotron").strip()
        if default_provider not in {"nemotron", "gemma_local"}:
            raise ConfigurationError("INTELLIGENCE_PROVIDER is unsupported")
        required = ["NAO_GATEWAY_SECRET"]
        if default_provider == "nemotron":
            required.append("NVIDIA_API_KEY")
        missing = [name for name in required if not environ.get(name, "").strip()]
        if missing:
            raise ConfigurationError(
                "Missing environment variables: " + ", ".join(missing)
            )

        base_url = environ.get(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        ).rstrip("/")
        asr_url = environ.get("NVIDIA_ASR_URL", "").strip()
        if urlparse(base_url).scheme != "https":
            raise ConfigurationError("NVIDIA_BASE_URL must use HTTPS")
        if asr_url and urlparse(asr_url).scheme != "https":
            raise ConfigurationError("NVIDIA_ASR_URL must use HTTPS")

        gemma_base_url = environ.get(
            "GEMMA_BASE_URL", "http://127.0.0.1:8080/v1"
        ).rstrip("/")
        parsed_gemma = urlparse(gemma_base_url)
        if (
            parsed_gemma.scheme not in {"http", "https"}
            or parsed_gemma.hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ConfigurationError("GEMMA_BASE_URL must use PC loopback")

        robot_url = environ.get("NAO_GATEWAY_URL", "ws://nao.local:6674")
        parsed_robot = urlparse(robot_url)
        if parsed_robot.scheme not in {"ws", "wss"} or not parsed_robot.hostname:
            raise ConfigurationError("NAO_GATEWAY_URL must be a ws:// or wss:// URL")

        return cls(
            nvidia_api_key=environ.get("NVIDIA_API_KEY", "").strip(),
            nvidia_base_url=base_url,
            agent_model=environ.get(
                "NVIDIA_AGENT_MODEL", "nvidia/nemotron-3-nano-30b-a3b"
            ),
            vision_model=environ.get(
                "NVIDIA_VISION_MODEL",
                "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            ),
            asr_url=asr_url,
            robot_url=robot_url,
            robot_shared_secret=environ["NAO_GATEWAY_SECRET"].strip(),
            default_provider=default_provider,
            gemma_base_url=gemma_base_url,
            gemma_model=environ.get("GEMMA_MODEL", "").strip(),
        )
