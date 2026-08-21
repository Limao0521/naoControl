from __future__ import absolute_import

from nao.scripts.runtime.intelligence import protocol


NOW_MS = 1700000000000
UNSIGNED = {
    "protocol_version": 1,
    "message_type": "command",
    "message_id": "message-001",
    "issued_at_ms": NOW_MS - 100,
    "expires_at_ms": NOW_MS + 5000,
    "payload": {"action": "say", "arguments": {"text": "Hola"}},
}


def test_robot_signature_matches_shared_golden_vector():
    signed = protocol.sign_envelope(UNSIGNED, b"test-secret")
    assert signed["signature"] == "pnZS9Zps9MXYdAZ3ZW/DBLvizkJbPWjjwFYEosWWJpk="


def test_robot_float_arguments_use_shared_canonical_representation():
    envelope = dict(UNSIGNED)
    envelope["payload"] = {
        "action": "set_posture",
        "arguments": {"posture": "Stand", "speed": 0.3},
    }

    assert b'"speed":"__nao_float__:0.3"' in protocol._canonical(envelope)


def test_robot_rejects_replay():
    guard = protocol.ReplayGuard(100)
    signed = protocol.sign_envelope(UNSIGNED, b"test-secret")
    protocol.verify_envelope(signed, b"test-secret", NOW_MS, guard)
    try:
        protocol.verify_envelope(signed, b"test-secret", NOW_MS, guard)
    except protocol.ProtocolError:
        return
    raise AssertionError("replayed envelope was accepted")


def test_robot_accepts_a_one_minute_clock_offset():
    guard = protocol.ReplayGuard(100)
    signed = protocol.sign_envelope(UNSIGNED, b"test-secret")

    payload = protocol.verify_envelope(
        signed, b"test-secret", NOW_MS + 60000, guard
    )

    assert payload["action"] == "say"
