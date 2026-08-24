"""Validated environment configuration for the PC gateway."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
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
    network_broker_enabled: bool
    network_broker_host: str
    network_broker_port: int
    nao_ssh_host: str
    nao_ssh_user: str
    nao_ssh_key: str
    network_allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "GatewaySettings":
        required = ("NVIDIA_API_KEY", "NAO_GATEWAY_SECRET")
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

        robot_url = environ.get("NAO_GATEWAY_URL", "ws://nao.local:6674")
        parsed_robot = urlparse(robot_url)
        if parsed_robot.scheme not in {"ws", "wss"} or not parsed_robot.hostname:
            raise ConfigurationError("NAO_GATEWAY_URL must be a ws:// or wss:// URL")

        enabled_text = environ.get("NAO_NETWORK_BROKER_ENABLED", "false").strip().lower()
        if enabled_text not in {"true", "false"}:
            raise ConfigurationError("NAO_NETWORK_BROKER_ENABLED must be true or false")
        network_broker_enabled = enabled_text == "true"

        try:
            network_broker_port = int(environ.get("NAO_NETWORK_BROKER_PORT", "6675"))
        except ValueError as error:
            raise ConfigurationError("NAO_NETWORK_BROKER_PORT must be an integer") from error
        if not 1024 <= network_broker_port <= 65535:
            raise ConfigurationError("NAO_NETWORK_BROKER_PORT must be between 1024 and 65535")

        ssh_user = environ.get("NAO_SSH_USER", "nao").strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,31}", ssh_user):
            raise ConfigurationError("NAO_SSH_USER is invalid")

        ssh_key = environ.get("NAO_SSH_KEY", "").strip()
        resolved_key = str(Path(ssh_key).expanduser().resolve()) if ssh_key else ""
        if network_broker_enabled and (not ssh_key or not Path(resolved_key).is_file()):
            raise ConfigurationError("NAO_SSH_KEY must name an existing private key")

        default_origin = f"http://{parsed_robot.hostname}:3000"
        origins_text = environ.get("NAO_NETWORK_ALLOWED_ORIGINS", default_origin)
        origins = tuple(item.strip() for item in origins_text.split(",") if item.strip())
        if not origins:
            raise ConfigurationError("At least one network broker origin is required")
        for origin in origins:
            parsed_origin = urlparse(origin)
            if (
                parsed_origin.scheme not in {"http", "https"}
                or not parsed_origin.hostname
                or parsed_origin.path not in {"", "/"}
                or parsed_origin.params
                or parsed_origin.query
                or parsed_origin.fragment
                or parsed_origin.username
                or parsed_origin.password
            ):
                raise ConfigurationError("NAO network origin must be an explicit origin")

        return cls(
            nvidia_api_key=environ["NVIDIA_API_KEY"].strip(),
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
            network_broker_enabled=network_broker_enabled,
            network_broker_host="127.0.0.1",
            network_broker_port=network_broker_port,
            nao_ssh_host=parsed_robot.hostname,
            nao_ssh_user=ssh_user,
            nao_ssh_key=resolved_key,
            network_allowed_origins=origins,
        )
