import base64

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
    async def perceive(self, audio, image):
        return Perception("¿Qué color tiene?", "Una botella roja", ["botella roja"], [])

    async def decide(self, transcript, scene, tools):
        return AgentDecision("La botella es roja.", [ToolCall("set_led", {"group": "FaceLeds", "color": "red"})])


@pytest.mark.asyncio
async def test_audio_event_executes_policy_tools_then_speaks():
    robot = FakeRobot()
    host = AgentHost(robot, FakeNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["red"]},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-1"})

    assert robot.actions == [
        ("set_led", {"group": "FaceLeds", "color": "red"}),
        ("say", {"text": "La botella es roja."}),
    ]
