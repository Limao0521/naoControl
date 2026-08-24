"""Typed, redacted inputs for the PC-side NAO network broker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


ALLOWED_OPERATIONS = frozenset(
    {"status", "scan", "profiles", "connect", "disconnect", "forget"}
)
ALLOWED_FIELDS = frozenset({"operation", "service_id", "ssid", "passphrase"})
SENSITIVE_KEYS = frozenset({"passphrase", "password", "secret", "psk"})


class NetworkRequestError(ValueError):
    """Raised when an administrative network request is not safe to execute."""


@dataclass(frozen=True)
class NetworkRequest:
    operation: str
    service_id: str = ""
    ssid: str = ""
    passphrase: str = ""


def _string_field(payload: Mapping[str, object], name: str, maximum: int) -> str:
    value = payload.get(name, "")
    if not isinstance(value, str):
        raise NetworkRequestError(f"{name} must be a string")
    if "\x00" in value:
        raise NetworkRequestError(f"{name} must not contain NUL")
    if len(value) > maximum:
        raise NetworkRequestError(f"{name} exceeds {maximum} characters")
    return value


def parse_network_request(payload: Mapping[str, object]) -> NetworkRequest:
    """Validate an untrusted JSON-compatible network request."""
    if not isinstance(payload, Mapping):
        raise NetworkRequestError("Network request must be an object")

    operation = _string_field(payload, "operation", 32)
    if operation not in ALLOWED_OPERATIONS:
        raise NetworkRequestError(f"Unsupported network operation: {operation}")

    unknown = sorted(set(payload) - ALLOWED_FIELDS)
    if unknown:
        raise NetworkRequestError(
            "Unknown network request fields: " + ", ".join(str(name) for name in unknown)
        )

    service_id = _string_field(payload, "service_id", 512)
    ssid = _string_field(payload, "ssid", 32)
    passphrase = _string_field(payload, "passphrase", 63)

    if operation in {"connect", "disconnect", "forget"} and not service_id:
        raise NetworkRequestError(f"service_id is required for {operation}")
    if passphrase and not 8 <= len(passphrase) <= 63:
        raise NetworkRequestError("passphrase must be between 8 and 63 characters")

    return NetworkRequest(operation, service_id, ssid, passphrase)


def redact_sensitive(value: Any) -> Any:
    """Return a deep redacted copy of JSON-compatible diagnostic data."""
    if isinstance(value, Mapping):
        return {
            key: "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    return value
