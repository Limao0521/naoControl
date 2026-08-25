import base64
import logging

import pytest

from nao_gateway.agent_host import AgentHost, _physical_action_explicitly_requested
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


def test_tool_schemas_exposes_sorted_behavior_ids():
    host = AgentHost(None, None, lambda: None, registry={
        "actions": {"run_behavior": {"risk": "body"}},
        "behaviors": {name: {} for name in (
            "yes", "wave", "dance_siu", "no", "taichi", "thinking",
            "dance_gangnam", "play_saxophone", "dance_macarena",
        )},
    })
    run_behavior = next(tool for tool in host.tool_schemas() if tool["name"] == "run_behavior")
    assert run_behavior["constraints"]["allowed_behavior_ids"] == [
        "dance_gangnam", "dance_macarena", "dance_siu", "no",
        "play_saxophone", "taichi", "thinking", "wave", "yes",
    ]


@pytest.mark.parametrize("behavior_id, transcript", [
    ("wave", "Por favor, saluda"),
    ("yes", "Asiente"),
    ("no", "Niega"),
    ("thinking", "Piensa"),
    ("dance_siu", "Baila siu"),
    ("dance_gangnam", "Haz gangnam"),
    ("dance_macarena", "Baila macarena"),
    ("play_saxophone", "Toca el saxofón"),
    ("taichi", "Haz tai chi"),
])
def test_run_behavior_requires_matching_registered_intent(behavior_id, transcript):
    assert _physical_action_explicitly_requested(
        "run_behavior", transcript, {"behavior_id": behavior_id}
    ) is True


def test_run_behavior_rejects_mismatched_behavior_intent():
    assert _physical_action_explicitly_requested(
        "run_behavior", "Baila", {"behavior_id": "play_saxophone"}
    ) is False
    assert _physical_action_explicitly_requested(
        "run_behavior", "Toca saxofón", {"behavior_id": "play_saxophone"}
    ) is True
    assert _physical_action_explicitly_requested(
        "run_behavior", "Saluda", {"behavior_id": "unknown"}
    ) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("behavior_id, transcript", [
    ("wave", "Por favor, saluda"),
    ("yes", "Asiente"),
    ("no", "Niega"),
    ("thinking", "Piensa"),
    ("dance_siu", "Baila siu"),
    ("dance_gangnam", "Haz gangnam"),
    ("dance_macarena", "Baila macarena"),
    ("play_saxophone", "Toca el saxofón"),
    ("taichi", "Haz tai chi"),
])
async def test_explicit_registered_behavior_reaches_robot(behavior_id, transcript):
    class BehaviorNemotron(object):
        async def perceive(self, audio, image):
            return Perception(transcript, "", [], [])

        async def decide(self, transcript, scene, tools):
            return AgentDecision("", [ToolCall("run_behavior", {"behavior_id": behavior_id})])

    robot = FakeRobot()
    host = AgentHost(robot, BehaviorNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "run_behavior": {"risk": "body", "allowed_postures": ["Stand"]},
        },
        "behaviors": {behavior_id: {"package": "registered/package"}},
    })

    await host.handle_audio({
        "audio_b64": base64.b64encode(b"RIFF").decode(),
        "interaction_id": "behavior-" + behavior_id,
    })

    assert robot.actions == [("run_behavior", {"behavior_id": behavior_id})]


@pytest.mark.asyncio
async def test_generic_dance_does_not_authorize_saxophone_behavior():
    class SaxNemotron(object):
        async def perceive(self, audio, image):
            return Perception("Baila", "", [], [])

        async def decide(self, transcript, scene, tools):
            return AgentDecision("", [ToolCall("run_behavior", {"behavior_id": "play_saxophone"})])

    robot = FakeRobot()
    host = AgentHost(robot, SaxNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {"run_behavior": {"risk": "body", "allowed_postures": ["Stand"]}},
        "behaviors": {"play_saxophone": {"package": "registered/package"}},
    })

    await host.handle_audio({
        "audio_b64": base64.b64encode(b"RIFF").decode(),
        "interaction_id": "behavior-mismatch",
    })

    assert robot.actions == []


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


@pytest.mark.asyncio
async def test_natural_stand_request_from_real_transcript_executes_posture():
    class NaturalPostureNemotron(FakeNemotron):
        async def perceive(self, audio, image):
            return Perception(
                "Quiero que te levantes, quiero que hagas la acción de levantarte.",
                "Una persona", ["persona"], [],
            )

        async def decide(self, transcript, scene, tools):
            return AgentDecision(
                "Me levantaré ahora mismo.",
                [ToolCall("set_posture", {"posture": "Stand", "speed": 0.3})],
            )

    robot = FakeRobot()
    host = AgentHost(robot, NaturalPostureNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_posture": {"risk": "body", "allowed": ["Stand"], "max_speed": 0.5},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-natural-stand"})

    assert robot.actions[0] == ("set_posture", {"posture": "Stand", "speed": 0.3})


@pytest.mark.asyncio
async def test_posture_request_does_not_authorize_a_different_posture(caplog):
    class MismatchedPostureNemotron(FakeNemotron):
        async def perceive(self, audio, image):
            return Perception("Quiero que te levantes.", "Una persona", ["persona"], [])

        async def decide(self, transcript, scene, tools):
            return AgentDecision(
                "Me sentaré.",
                [ToolCall("set_posture", {"posture": "Sit", "speed": 0.3})],
            )

    robot = FakeRobot()
    host = AgentHost(robot, MismatchedPostureNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_posture": {"risk": "body", "allowed": ["Sit"], "max_speed": 0.5},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    with caplog.at_level(logging.WARNING):
        await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-mismatch"})

    assert robot.actions == [("say", {"text": "Me sentaré."})]
    assert "rejected_tool=set_posture reason=physical_action_not_explicitly_requested" in caplog.text


@pytest.mark.asyncio
async def test_negated_posture_request_does_not_authorize_body_action(caplog):
    class NegatedPostureNemotron(FakeNemotron):
        async def perceive(self, audio, image):
            return Perception("No quiero que te levantes.", "Una persona", ["persona"], [])

        async def decide(self, transcript, scene, tools):
            return AgentDecision(
                "De acuerdo, permaneceré donde estoy.",
                [ToolCall("set_posture", {"posture": "Stand", "speed": 0.3})],
            )

    robot = FakeRobot()
    host = AgentHost(robot, NegatedPostureNemotron(), image_provider=lambda: b"jpeg", registry={
        "actions": {
            "set_posture": {"risk": "body", "allowed": ["Stand"], "max_speed": 0.5},
            "say": {"risk": "low", "max_text_length": 500},
        }
    })

    with caplog.at_level(logging.WARNING):
        await host.handle_audio({"audio_b64": base64.b64encode(b"RIFF").decode(), "interaction_id": "i-negated"})

    assert robot.actions == [("say", {"text": "De acuerdo, permaneceré donde estoy."})]
    assert "rejected_tool=set_posture reason=physical_action_not_explicitly_requested" in caplog.text


@pytest.mark.asyncio
async def test_turn_state_publishes_transcript_response_and_action_result():
    updates = []

    async def publish(update):
        updates.append(update)

    robot = FakeRobot()
    host = AgentHost(
        robot, FakeNemotron(), image_provider=lambda: b"jpeg",
        registry={
            "actions": {
                "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["red"]},
                "say": {"risk": "low", "max_text_length": 500},
            }
        },
        state_publisher=publish,
    )

    await host.handle_audio({
        "audio_b64": base64.b64encode(b"RIFF").decode(),
        "interaction_id": "turn-observable",
    })

    assert updates[0] == {
        "interaction_id": "turn-observable", "phase": "processing",
        "transcript": "¿Qué color tiene?", "response": "", "actions": [],
    }
    assert updates[-1] == {
        "interaction_id": "turn-observable", "phase": "ready",
        "transcript": "¿Qué color tiene?", "response": "La botella es roja.",
        "actions": [{"name": "set_led", "status": "completed", "reason": None}],
    }


@pytest.mark.asyncio
async def test_observability_failure_does_not_block_robot_response(caplog):
    async def unavailable_state_channel(update):
        raise ConnectionError("state channel unavailable")

    robot = FakeRobot()
    host = AgentHost(
        robot, FakeNemotron(), image_provider=lambda: b"jpeg",
        registry={
            "actions": {
                "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["red"]},
                "say": {"risk": "low", "max_text_length": 500},
            }
        },
        state_publisher=unavailable_state_channel,
    )

    with caplog.at_level(logging.WARNING):
        await host.handle_audio({
            "audio_b64": base64.b64encode(b"RIFF").decode(),
            "interaction_id": "turn-state-failure",
        })

    assert robot.actions[-1] == ("say", {"text": "La botella es roja."})
    assert "STATE_PUBLISH_FAILED turn=turn-state-failure" in caplog.text
