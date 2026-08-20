import base64
import logging

import pytest

from nao_gateway.agent_host import AgentHost
from nao_gateway.nemotron import AgentDecision, Perception, ToolCall


class FakeRobot(object):
    def __init__(self):
        self.actions = []

    async def execute(self, action, arguments):
        self.actions.append((action, arguments))
        return {"status": "completed"}


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
    assert "action=set_led status=completed" in caplog.text
    assert "TRANSCRIPTION" in capsys.readouterr().out
