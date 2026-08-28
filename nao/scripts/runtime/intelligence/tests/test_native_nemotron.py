import base64
import json

import pytest

from nao.scripts.runtime.intelligence.native_nemotron import (
    NativeAgent,
    NativeCloudConfig,
    NativeNemotronClient,
    NativeRuntimeError,
    FallbackJsonTransport,
    fetch_latest_jpeg,
)


class Responses(object):
    def __init__(self, values):
        self.values = list(values)
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        self.requests.append((url, dict(headers), body, timeout))
        return self.values.pop(0)


def completion(content, tool_calls=None):
    message = {"content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message, "finish_reason": "stop"}]}


def test_native_config_keeps_secret_out_of_non_secret_state(tmp_path):
    secret = tmp_path / "nvidia_api_key"
    secret.write_text("nvapi-test-only-123456789\n", encoding="utf-8")

    config = NativeCloudConfig(str(secret))

    assert config.api_key() == "nvapi-test-only-123456789"
    assert "nvapi-test-only-123456789" not in repr(config)


def test_native_client_rejects_missing_secret(tmp_path):
    config = NativeCloudConfig(str(tmp_path / "missing"))

    with pytest.raises(NativeRuntimeError, match="NVIDIA API key"):
        config.api_key()


def test_fetch_latest_jpeg_bounds_local_mjpeg_stream():
    class Response(object):
        def __init__(self):
            self.chunks = [b"boundary\r\n", b"\xff\xd8image", b"data\xff\xd9tail"]

        def read(self, _size):
            return self.chunks.pop(0) if self.chunks else b""

    assert fetch_latest_jpeg(opener=lambda *args, **kwargs: Response()) == b"\xff\xd8imagedata\xff\xd9"


def test_transport_falls_back_without_requiring_pc_service():
    calls = []

    def primary(*args):
        calls.append("python")
        raise NativeRuntimeError("legacy TLS failed")

    def fallback(*args):
        calls.append("curl")
        return {"choices": []}

    transport = FallbackJsonTransport(primary, fallback)

    assert transport("https://example.test", {}, {}, 5) == {"choices": []}
    assert calls == ["python", "curl"]


def test_native_client_perceives_and_decides_without_pc_gateway(tmp_path):
    secret = tmp_path / "nvidia_api_key"
    secret.write_text("nvapi-test-only-123456789", encoding="utf-8")
    transport = Responses([
        completion(json.dumps({
            "transcript": "Hola NAO", "scene_summary": "Una mesa",
            "objects": ["mesa"], "uncertainties": [],
        })),
        completion("Me pondré de pie", [{
            "function": {
                "name": "set_posture",
                "arguments": json.dumps({"posture": "Stand", "speed": 0.35}),
            },
        }]),
    ])
    client = NativeNemotronClient(
        NativeCloudConfig(str(secret)), transport=transport,
        knowledge_path="config/agent_knowledge.json",
    )

    perception = client.perceive(b"RIFF-audio", b"jpeg")
    decision = client.decide(
        perception["transcript"], perception["scene_summary"],
        [{"name": "set_posture", "constraints": {"allowed": ["Stand"]}}],
        language="es",
    )

    assert perception["transcript"] == "Hola NAO"
    assert decision == {
        "speech": "Me pondré de pie",
        "tool_calls": [{
            "name": "set_posture",
            "arguments": {"posture": "Stand", "speed": 0.35},
        }],
    }
    assert len(transport.requests) == 2
    assert transport.requests[0][0].endswith("/chat/completions")
    assert transport.requests[0][1]["Authorization"] == "Bearer nvapi-test-only-123456789"
    assert "nvapi-test-only-123456789" not in json.dumps(transport.requests[0][2])


def test_native_agent_executes_only_explicit_physical_action(tmp_path):
    class Client(object):
        def perceive(self, audio, image):
            return {
                "transcript": "Quiero que te pongas de pie",
                "scene_summary": "", "objects": [], "uncertainties": [],
            }

        def decide(self, transcript, scene, tools, language):
            return {"speech": "Me pondré de pie", "tool_calls": [{
                "name": "set_posture", "arguments": {"posture": "Stand"},
            }]}

    class Executor(object):
        def __init__(self):
            self.commands = []

        def execute(self, command):
            self.commands.append(command)
            return {"status": "completed", "action": command["action"]}

    updates = []
    executor = Executor()
    agent = NativeAgent(
        Client(), executor,
        {"actions": {
            "say": {"max_text_length": 500},
            "set_posture": {"allowed": ["Stand"], "max_speed": 0.5},
        }, "behaviors": {}},
        state_publisher=lambda value: updates.append(value),
        image_provider=lambda: b"jpeg", language_provider=lambda: "es",
    )

    agent.handle_audio({"interaction_id": "turn-1", "audio_b64": base64.b64encode(b"wav")})

    assert executor.commands == [
        {"action": "set_posture", "arguments": {"posture": "Stand"}},
        {"action": "say", "arguments": {"text": "Me pondré de pie"}},
    ]
    assert updates[-1]["phase"] == "ready"
    assert updates[-1]["transcript"] == "Quiero que te pongas de pie"


def test_native_agent_rejects_unrequested_physical_action():
    class Client(object):
        def perceive(self, audio, image):
            return {
                "transcript": "Cuéntame sobre el semillero",
                "scene_summary": "", "objects": [], "uncertainties": [],
            }

        def decide(self, transcript, scene, tools, language):
            return {"speech": "Claro", "tool_calls": [{
                "name": "set_posture", "arguments": {"posture": "Stand"},
            }]}

    class Executor(object):
        def __init__(self):
            self.commands = []

        def execute(self, command):
            self.commands.append(command)
            return {"status": "completed", "action": command["action"]}

    executor = Executor()
    updates = []
    agent = NativeAgent(
        Client(), executor,
        {"actions": {
            "say": {"max_text_length": 500},
            "set_posture": {"allowed": ["Stand"], "max_speed": 0.5},
        }, "behaviors": {}},
        state_publisher=lambda value: updates.append(value),
        image_provider=lambda: None, language_provider=lambda: "es",
    )

    agent.handle_audio({"interaction_id": "turn-2", "audio_b64": base64.b64encode(b"wav")})

    assert executor.commands == [{"action": "say", "arguments": {"text": "Claro"}}]
    assert updates[-1]["actions"][0]["status"] == "rejected"
    assert updates[-1]["actions"][0]["reason"] == "physical_action_not_explicitly_requested"


def test_native_agent_keeps_conversation_available_when_camera_fails():
    images = []

    class Client(object):
        def perceive(self, audio, image):
            images.append(image)
            return {"transcript": "Hola", "scene_summary": "",
                    "objects": [], "uncertainties": ["camera unavailable"]}

        def decide(self, transcript, scene, tools, language):
            return {"speech": "Hola", "tool_calls": []}

    class Executor(object):
        def execute(self, command):
            return {"status": "completed", "action": command["action"]}

    agent = NativeAgent(
        Client(), Executor(), {"actions": {"say": {}}, "behaviors": {}},
        state_publisher=lambda value: None,
        image_provider=lambda: (_ for _ in ()).throw(RuntimeError("camera busy")),
        language_provider=lambda: "es",
    )

    result = agent.handle_audio({"audio_b64": base64.b64encode(b"wav")})

    assert images == [None]
    assert result["response"] == "Hola"


def test_native_agent_allows_only_one_body_action_per_turn():
    class Client(object):
        def perceive(self, audio, image):
            return {"transcript": "Ponte de pie y saluda", "scene_summary": "",
                    "objects": [], "uncertainties": []}

        def decide(self, transcript, scene, tools, language):
            return {"speech": "Voy", "tool_calls": [
                {"name": "set_posture", "arguments": {"posture": "Stand"}},
                {"name": "run_behavior", "arguments": {"behavior_id": "wave"}},
            ]}

    class Executor(object):
        def __init__(self):
            self.commands = []

        def execute(self, command):
            self.commands.append(command)
            return {"status": "completed", "action": command["action"]}

    executor = Executor()
    updates = []
    agent = NativeAgent(
        Client(), executor,
        {"actions": {
            "say": {"risk": "low"},
            "set_posture": {"risk": "body", "allowed": ["Stand"]},
            "run_behavior": {"risk": "body"},
        }, "behaviors": {"wave": {"package": "animations/Stand/Gestures/Hey_1"}}},
        state_publisher=lambda value: updates.append(value),
        image_provider=lambda: None, language_provider=lambda: "es",
    )

    agent.handle_audio({"audio_b64": base64.b64encode(b"wav")})

    assert [item["action"] for item in executor.commands] == ["set_posture", "say"]
    assert updates[-1]["actions"][1]["reason"] == "body_action_budget_exceeded"
