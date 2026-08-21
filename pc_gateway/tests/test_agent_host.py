import base64
import logging

import pytest

from nao_gateway.agent_host import AgentHost
from nao_gateway.nemotron import AgentDecision, Perception, ToolCall


class FakeRobot(object):
    def __init__(self, result=None):
        self.actions = []
        self.result = result or {"status": "completed"}

    async def execute(self, action, arguments):
        self.actions.append((action, arguments))
        return self.result


class FakeNemotron(object):
    def __init__(self):
        self.tools = None

    async def perceive(self, audio, image):
        return Perception("¿Qué color tiene?", "Una botella roja", ["botella roja"], [])

    async def decide(self, transcript, scene, tools):
        self.tools = tools
        return AgentDecision("La botella es roja.", [ToolCall("set_led", {"group": "FaceLeds", "color": "red"})])


@pytest.mark.asyncio
async def test_audio_event_executes_policy_tools_then_speaks(caplog, capsys):
    robot = FakeRobot()
    nemotron = FakeNemotron()
    host = AgentHost(robot, nemotron, image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["red"]},
            "say": {"risk": "low", "max_text_length": 500},
            "play_sound": {"risk": "low", "enabled": False},
        }
    })

    with caplog.at_level(logging.INFO):
        await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-1"})

    assert robot.actions == [
        ("set_led", {"group": "FaceLeds", "color": "red"}),
        ("say", {"text": "La botella es roja."}),
    ]
    assert [tool["name"] for tool in nemotron.tools] == ["set_led"]
    assert "transcript='¿Qué color tiene?'" in caplog.text
    assert "action=set_led arguments={'group': 'FaceLeds', 'color': 'red'} status=completed reason=None" in caplog.text
    assert "TRANSCRIPTION" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_audio_event_logs_rejected_action_arguments_and_reason(caplog):
    robot = FakeRobot({"status": "rejected", "reason": "invalid_posture"})
    nemotron = FakeNemotron()
    host = AgentHost(robot, nemotron, image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["red"]},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    with caplog.at_level(logging.INFO):
        await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-rejected"})

    assert "action=set_led arguments={'group': 'FaceLeds', 'color': 'red'} status=rejected reason=invalid_posture" in caplog.text


@pytest.mark.asyncio
async def test_audio_event_continues_without_vision_when_camera_times_out(caplog):
    robot = FakeRobot()
    nemotron = FakeNemotron()

    async def unavailable_camera():
        raise TimeoutError("camera unavailable")

    host = AgentHost(robot, nemotron, image_provider=unavailable_camera, registry={
        "actions": {
            "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["red"]},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    with caplog.at_level(logging.WARNING):
        await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-camera"})

    assert "VISION_UNAVAILABLE turn=i-camera" in caplog.text
    assert robot.actions[-1] == ("say", {"text": "La botella es roja."})


@pytest.mark.asyncio
async def test_unsolicited_body_action_is_rejected_but_speech_continues(caplog):
    class ConversationalNemotron(FakeNemotron):
        async def perceive(self, audio, image):
            return Perception("Hola, ¿cómo estás?", "Una persona", ["persona"], [])

        async def decide(self, transcript, scene, tools):
            return AgentDecision(
                "Estoy bien, gracias.",
                [ToolCall("look", {"yaw": 0.4, "pitch": 0.0, "speed": 0.1})],
            )

    robot = FakeRobot()
    host = AgentHost(robot, ConversationalNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "look": {"risk": "body", "max_speed": 0.15, "yaw_range": [-1.0, 1.0], "pitch_range": [-0.5, 0.5]},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    with caplog.at_level(logging.WARNING):
        await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-chat"})

    assert robot.actions == [("say", {"text": "Estoy bien, gracias."})]
    assert "rejected_tool=look reason=physical_action_not_explicitly_requested" in caplog.text


@pytest.mark.asyncio
async def test_explicit_posture_request_allows_matching_body_action():
    class PostureNemotron(FakeNemotron):
        async def perceive(self, audio, image):
            return Perception("Por favor, párate.", "Una persona", ["persona"], [])

        async def decide(self, transcript, scene, tools):
            return AgentDecision(
                "Me pondré de pie.",
                [ToolCall("set_posture", {"posture": "Stand", "speed": 0.3})],
            )

    robot = FakeRobot()
    host = AgentHost(robot, PostureNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_posture": {"risk": "body", "allowed": ["Stand"], "max_speed": 0.5},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-stand"})

    assert robot.actions == [
        ("set_posture", {"posture": "Stand", "speed": 0.3}),
        ("say", {"text": "Me pondré de pie."}),
    ]
