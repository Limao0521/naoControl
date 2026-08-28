"""Validated environment configuration for the PC gateway."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_address
from typing import Mapping
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when a required or security-sensitive setting is invalid."""


def validate_gemma_base_url(value: str) -> str:
    """Return a safe private-LAN Gemma endpoint or reject it before any request."""
    gemma_base_url = value.strip().rstrip("/")
    parsed_gemma = urlparse(gemma_base_url)
    if parsed_gemma.scheme not in {"http", "https"} or not parsed_gemma.hostname:
        raise ConfigurationError("GEMMA_BASE_URL must be an HTTP URL")
    if parsed_gemma.username is not None or parsed_gemma.password is not None:
        raise ConfigurationError("GEMMA_BASE_URL must not contain credentials")
    if parsed_gemma.query or parsed_gemma.fragment or parsed_gemma.path != "/v1":
        raise ConfigurationError("GEMMA_BASE_URL must end in /v1")
    gemma_host = parsed_gemma.hostname
    try:
        gemma_address = ip_address(gemma_host)
    except ValueError:
        raise ConfigurationError("GEMMA_BASE_URL must use a literal IPv4 address")
    is_loopback = gemma_address.is_loopback
    private_networks = (
        IPv4Network("10.0.0.0/8"),
        IPv4Network("172.16.0.0/12"),
        IPv4Network("192.168.0.0/16"),
        IPv4Network("169.254.0.0/16"),
    )
    is_private_lan = (
        isinstance(gemma_address, IPv4Address)
        and any(gemma_address in network for network in private_networks)
    )
    if not is_loopback and not is_private_lan:
        raise ConfigurationError(
            "GEMMA_BASE_URL must use loopback or a private network IPv4 address"
        )
    return gemma_base_url


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
    gemma_api_key: str

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

        gemma_base_url = validate_gemma_base_url(environ.get(
            "GEMMA_BASE_URL", "http://127.0.0.1:8080/v1"
        ))
        gemma_address = ip_address(urlparse(gemma_base_url).hostname)
        is_loopback = gemma_address.is_loopback
        private_networks = (
            IPv4Network("10.0.0.0/8"),
            IPv4Network("172.16.0.0/12"),
            IPv4Network("192.168.0.0/16"),
            IPv4Network("169.254.0.0/16"),
        )
        is_private_lan = (
            isinstance(gemma_address, IPv4Address)
            and any(gemma_address in network for network in private_networks)
        )
        if not is_loopback and not is_private_lan:
            raise ConfigurationError(
                "GEMMA_BASE_URL must use loopback or a private network IPv4 address"
            )
        gemma_api_key = environ.get("GEMMA_API_KEY", "").strip()
        if not is_loopback and not gemma_api_key:
            raise ConfigurationError(
                "GEMMA_API_KEY is required for a private network Gemma server"
            )

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
            gemma_api_key=gemma_api_key,
        )
