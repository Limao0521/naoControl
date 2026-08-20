from __future__ import annotations

import copy

import pytest

from nao_gateway.protocol import ProtocolError, ReplayGuard, sign_envelope, verify_envelope


NOW_MS = 1_700_000_000_000
UNSIGNED = {
    "protocol_version": 1,
    "message_type": "command",
    "message_id": "message-001",
    "issued_at_ms": NOW_MS - 100,
    "expires_at_ms": NOW_MS + 5_000,
    "payload": {"action": "say", "arguments": {"text": "Hola"}},
}
GOLDEN_SIGNATURE = "pnZS9Zps9MXYdAZ3ZW/DBLvizkJbPWjjwFYEosWWJpk="


def test_signature_matches_golden_vector() -> None:
    assert sign_envelope(UNSIGNED, b"test-secret")["signature"] == GOLDEN_SIGNATURE


@pytest.mark.parametrize("mutation", ["expired", "replayed", "bad_signature", "unknown_version"])
def test_invalid_envelopes_are_rejected(mutation: str) -> None:
    envelope = sign_envelope(UNSIGNED, b"test-secret")
    guard = ReplayGuard(100)
    if mutation == "expired":
        verification_time = UNSIGNED["expires_at_ms"] + 120_001
    elif mutation == "replayed":
        verify_envelope(envelope, b"test-secret", NOW_MS, guard)
        verification_time = NOW_MS
    elif mutation == "bad_signature":
        envelope["signature"] = "not-a-valid-signature"
        verification_time = NOW_MS
    else:
        changed = copy.deepcopy(UNSIGNED)
        changed["protocol_version"] = 99
        envelope = sign_envelope(changed, b"test-secret")
        verification_time = NOW_MS

    with pytest.raises(ProtocolError):
        verify_envelope(envelope, b"test-secret", verification_time, guard)


def test_replay_guard_stays_bounded() -> None:
    guard = ReplayGuard(2)
    for index in range(3):
        envelope = dict(UNSIGNED, message_id=f"message-{index}")
        verify_envelope(sign_envelope(envelope, b"test-secret"), b"test-secret", NOW_MS, guard)

    assert len(guard) == 2


def test_accepts_a_one_minute_clock_offset() -> None:
    envelope = sign_envelope(UNSIGNED, b"test-secret")

    payload = verify_envelope(envelope, b"test-secret", NOW_MS + 60_000, ReplayGuard())

    assert payload["action"] == "say"
