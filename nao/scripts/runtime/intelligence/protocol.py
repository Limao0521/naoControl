# -*- coding: utf-8 -*-
"""Python 2.7-compatible authenticated gateway protocol."""
from __future__ import absolute_import

import base64
import hashlib
import hmac
import json
import math
from collections import OrderedDict

try:
    basestring
except NameError:
    basestring = str
    long = int


PROTOCOL_VERSION = 1
CLOCK_SKEW_TOLERANCE_MS = 120000
UNSIGNED_FIELDS = (
    "protocol_version", "message_type", "message_id", "issued_at_ms",
    "expires_at_ms", "payload"
)


class ProtocolError(ValueError):
    pass


class ReplayGuard(object):
    def __init__(self, capacity=1000):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._entries = OrderedDict()

    def record(self, message_id, expires_at_ms, now_ms):
        for key, expiry in list(self._entries.items()):
            if expiry < now_ms:
                self._entries.pop(key, None)
        if message_id in self._entries:
            raise ProtocolError("message replayed")
        self._entries[message_id] = expires_at_ms
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)

    def __len__(self):
        return len(self._entries)


def _unsigned(envelope):
    missing = [field for field in UNSIGNED_FIELDS if field not in envelope]
    if missing:
        raise ProtocolError("missing fields: " + ", ".join(missing))
    return dict((field, envelope[field]) for field in UNSIGNED_FIELDS)


def _canonical(envelope):
    return json.dumps(
        _normalize_numbers(_unsigned(envelope)),
        sort_keys=True, separators=(",", ":"),
        ensure_ascii=True
    ).encode("utf-8")


def _normalize_numbers(value):
    """Make HMAC input stable across the PC's Python 3 and NAO's Python 2."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ProtocolError("non-finite number")
        return "__nao_float__:" + ("%.12g" % value)
    if isinstance(value, dict):
        return dict((key, _normalize_numbers(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [_normalize_numbers(item) for item in value]
    return value


def _constant_time_equal(left, right):
    if len(left) != len(right):
        return False
    result = 0
    for left_char, right_char in zip(bytearray(left), bytearray(right)):
        result |= left_char ^ right_char
    return result == 0


def sign_envelope(envelope, secret):
    if not secret:
        raise ProtocolError("shared secret is empty")
    signed = _unsigned(envelope)
    digest = hmac.new(secret, _canonical(signed), hashlib.sha256).digest()
    signed["signature"] = base64.b64encode(digest).decode("ascii")
    return signed


def verify_envelope(envelope, secret, now_ms, replay_guard):
    if envelope.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    signature = envelope.get("signature")
    if not isinstance(signature, basestring):
        raise ProtocolError("missing signature")
    expected = sign_envelope(envelope, secret)["signature"]
    if not _constant_time_equal(signature.encode("ascii"), expected.encode("ascii")):
        raise ProtocolError("invalid signature")
    issued = envelope["issued_at_ms"]
    expires = envelope["expires_at_ms"]
    if not isinstance(issued, (int, long)) or not isinstance(expires, (int, long)):
        raise ProtocolError("invalid validity interval")
    if (expires <= issued or now_ms < issued - CLOCK_SKEW_TOLERANCE_MS or
            now_ms > expires + CLOCK_SKEW_TOLERANCE_MS):
        raise ProtocolError("envelope expired or issued in the future")
    message_id = envelope["message_id"]
    if not isinstance(message_id, basestring) or not message_id:
        raise ProtocolError("invalid message id")
    replay_guard.record(message_id, expires, now_ms)
    return dict(envelope["payload"])
