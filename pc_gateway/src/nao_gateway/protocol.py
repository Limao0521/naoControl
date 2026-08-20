"""Authenticated, expiring envelopes shared with the robot gateway."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any


PROTOCOL_VERSION = 1
CLOCK_SKEW_TOLERANCE_MS = 120_000
UNSIGNED_FIELDS = (
    "protocol_version",
    "message_type",
    "message_id",
    "issued_at_ms",
    "expires_at_ms",
    "payload",
)


class ProtocolError(ValueError):
    """The envelope is malformed, unauthenticated, stale, or replayed."""


class ReplayGuard:
    def __init__(self, capacity: int = 1000) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._entries: OrderedDict[str, int] = OrderedDict()

    def record(self, message_id: str, expires_at_ms: int, now_ms: int) -> None:
        expired = [key for key, expiry in self._entries.items() if expiry < now_ms]
        for key in expired:
            self._entries.pop(key, None)
        if message_id in self._entries:
            raise ProtocolError("message replayed")
        self._entries[message_id] = expires_at_ms
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)

    def __len__(self) -> int:
        return len(self._entries)


def _unsigned(envelope: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in UNSIGNED_FIELDS if field not in envelope]
    if missing:
        raise ProtocolError("missing fields: " + ", ".join(missing))
    return {field: envelope[field] for field in UNSIGNED_FIELDS}


def _canonical(envelope: Mapping[str, Any]) -> bytes:
    return json.dumps(
        _unsigned(envelope), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sign_envelope(envelope: Mapping[str, Any], secret: bytes) -> dict[str, Any]:
    if not secret:
        raise ProtocolError("shared secret is empty")
    signed = dict(_unsigned(envelope))
    digest = hmac.new(secret, _canonical(signed), hashlib.sha256).digest()
    signed["signature"] = base64.b64encode(digest).decode("ascii")
    return signed


def verify_envelope(
    envelope: Mapping[str, Any], secret: bytes, now_ms: int, replay_guard: ReplayGuard
) -> dict[str, Any]:
    if envelope.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    signature = envelope.get("signature")
    if not isinstance(signature, str):
        raise ProtocolError("missing signature")
    expected = sign_envelope(envelope, secret)["signature"]
    if not hmac.compare_digest(signature, expected):
        raise ProtocolError("invalid signature")
    issued = envelope["issued_at_ms"]
    expires = envelope["expires_at_ms"]
    if not isinstance(issued, int) or not isinstance(expires, int) or expires <= issued:
        raise ProtocolError("invalid validity interval")
    if (now_ms < issued - CLOCK_SKEW_TOLERANCE_MS or
            now_ms > expires + CLOCK_SKEW_TOLERANCE_MS):
        raise ProtocolError("envelope expired or issued in the future")
    message_id = envelope["message_id"]
    if not isinstance(message_id, str) or not message_id:
        raise ProtocolError("invalid message id")
    replay_guard.record(message_id, expires, now_ms)
    return dict(envelope["payload"])
