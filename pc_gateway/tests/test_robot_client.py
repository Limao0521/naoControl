import json

from nao_gateway.protocol import ReplayGuard, sign_envelope, verify_envelope
from nao_gateway.robot_client import RobotClient


def robot_envelope(message_type, payload):
    return sign_envelope({
        "protocol_version": 1,
        "message_type": message_type,
        "message_id": "robot-message-1",
        "issued_at_ms": 1000,
        "expires_at_ms": 6000,
        "payload": payload,
    }, b"shared-secret")


def test_robot_client_verifies_and_queues_audio_event():
    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)

    event = client.ingest(json.dumps(robot_envelope("audio_result", {"audio_b64": "UklGRg=="})))

    assert event == ("audio_result", {"audio_b64": "UklGRg=="})


def test_outbound_command_is_signed_and_expiring():
    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)

    envelope = client.command_envelope("say", {"text": "Hola"})
    payload = verify_envelope(envelope, b"shared-secret", 1000, ReplayGuard())

    assert payload == {"action": "say", "arguments": {"text": "Hola"}}
    assert envelope["expires_at_ms"] == 11000


def test_turn_finished_envelope_is_authenticated():
    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)

    envelope = client.turn_finished_envelope()
    payload = verify_envelope(envelope, b"shared-secret", 1000, ReplayGuard())

    assert envelope["message_type"] == "turn_finished"
    assert payload == {}
