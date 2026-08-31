import json

import pytest

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


def test_interaction_update_envelope_is_authenticated():
    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)

    envelope = client.interaction_update_envelope({
        "interaction_id": "turn-1",
        "phase": "processing",
        "transcript": "Hola NAO",
        "response": "",
        "actions": [],
    })
    payload = verify_envelope(envelope, b"shared-secret", 1000, ReplayGuard())

    assert envelope["message_type"] == "interaction_update"
    assert payload["transcript"] == "Hola NAO"


def test_provider_status_update_envelope_contains_no_configuration_or_secret():
    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)
    builder = getattr(client, "provider_status_envelope", None)
    assert builder is not None, "provider status envelope is missing"

    envelope = builder({
        "active": "gemma_local", "healthy": True, "error": "",
    })
    payload = verify_envelope(envelope, b"shared-secret", 1000, ReplayGuard())

    assert envelope["message_type"] == "provider_status_update"
    assert payload == {"active": "gemma_local", "healthy": True, "error": ""}
    assert "url" not in json.dumps(envelope).lower()
    assert "key" not in json.dumps(envelope).lower()


def test_keyword_detection_envelope_is_authenticated_and_has_no_audio():
    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)

    envelope = client.keyword_detected_envelope()
    payload = verify_envelope(envelope, b"shared-secret", 1000, ReplayGuard())

    assert envelope["message_type"] == "keyword_detected"
    assert payload == {}


@pytest.mark.asyncio
async def test_receive_loop_reports_connection_loss_instead_of_crashing_gateway():
    class BrokenSocket(object):
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionError("cable disconnected")

    client = RobotClient("ws://robot:6674", b"shared-secret", now_ms=lambda: 1000)
    client.socket = BrokenSocket()

    await client.receive_forever()

    message_type, payload = await client.events.get()
    assert message_type == "connection_lost"
    assert payload["error_type"] == "ConnectionError"
