import base64
import json

import httpx
import pytest

from nao_gateway.nemotron import NemotronClient, ToolCall


@pytest.mark.asyncio
async def test_perception_sends_synchronized_audio_and_image():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "transcript": "¿Qué ves?", "scene_summary": "Una botella roja",
                "objects": ["botella roja"], "uncertainties": "La imagen es pequeña"
            })}}]
        })

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )
    result = await client.perceive(b"RIFF-audio", b"jpeg-image")

    assert captured["messages"][0]["role"] == "system"
    assert "evidencia visible" in captured["messages"][0]["content"]
    assert captured["response_format"] == {"type": "json_object"}
    content = captured["messages"][1]["content"]
    assert [item["type"] for item in content] == ["audio_url", "image_url"]
    assert content[0]["audio_url"]["url"].startswith("data:audio/wav;base64,")
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert result.transcript == "¿Qué ves?"
    assert result.scene_summary == "Una botella roja"
    assert result.uncertainties == ["La imagen es pequeña"]


@pytest.mark.asyncio
async def test_perception_allows_audio_only_when_camera_is_unavailable():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "transcript": "Hola", "scene_summary": "Sin imagen disponible",
            "objects": [], "uncertainties": ["camera unavailable"]
        })}}]})

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    result = await client.perceive(b"RIFF-audio", None)

    assert [item["type"] for item in captured["messages"][1]["content"]] == ["audio_url"]
    assert result.transcript == "Hola"


@pytest.mark.asyncio
async def test_decision_rejects_unknown_tool_shape():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"speech":"Hola","tool_calls":[{"name":"say","args":["Hola"]}]}'}}]
        })

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )
    decision = await client.decide("Hola", "Una mesa", [{"name": "say"}])

    assert captured["messages"][0]["role"] == "system"
    assert "cerebro conversacional" in captured["messages"][0]["content"]
    assert '"name":"set_posture"' in captured["messages"][0]["content"]
    assert "Nunca prometas una acción física" in captured["messages"][0]["content"]
    assert "response_format" not in captured
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert decision.speech == "Hola"
    assert decision.tool_calls[0].name == "say"
    assert decision.tool_calls[0].arguments == {"text": "Hola"}


@pytest.mark.asyncio
async def test_decision_normalizes_response_only_shape_to_safe_speech():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"response":"Hola desde NAO"}'}}]
        })

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    decision = await client.decide("Hola", "Una mesa", [])

    assert decision.speech == "Hola desde NAO"
    assert decision.tool_calls == []


@pytest.mark.asyncio
async def test_decision_uses_native_function_call_for_posture_request():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {
            "content": "Claro, me siento.",
            "tool_calls": [{"type": "function", "function": {
                "name": "set_posture", "arguments": '{"posture":"Sit","speed":0.3}'
            }}],
        }}]})

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    decision = await client.decide("Siéntate", "Sin contexto visual", [{
        "name": "set_posture", "constraints": {
            "allowed": ["Stand", "Sit"], "max_speed": 0.5,
        }
    }])

    assert captured["tool_choice"] == "auto"
    assert captured["tools"][0]["function"]["name"] == "set_posture"
    assert decision.speech == "Claro, me siento."
    assert decision.tool_calls == [ToolCall("set_posture", {"posture": "Sit", "speed": 0.3})]


@pytest.mark.asyncio
async def test_decision_extracts_first_json_object_when_model_appends_text():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": (
                '{"speech":"Hola","tool_calls":[]}{"debug":"ignored"}'
            )}}]
        })

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    decision = await client.decide("Hola", "Una mesa", [])

    assert decision.speech == "Hola"


@pytest.mark.asyncio
async def test_decision_accepts_safe_python_dict_fallback():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{'speech': 'Hola', 'tool_calls': []}"}}]
        })

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    assert (await client.decide("Hola", "Una mesa", [])).speech == "Hola"


@pytest.mark.asyncio
async def test_perception_retries_one_transient_nvidia_failure():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"detail": "temporarily unavailable"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "transcript": "Hola", "scene_summary": "Mesa", "objects": [], "uncertainties": []
        })}}]})

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    assert (await client.perceive(b"wav", b"jpg")).transcript == "Hola"
    assert attempts == 2


@pytest.mark.asyncio
async def test_perception_retries_one_nvidia_read_timeout():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("upstream stalled", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "transcript": "Hola", "scene_summary": "Mesa", "objects": [], "uncertainties": []
        })}}]})

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    assert (await client.perceive(b"wav", b"jpg")).transcript == "Hola"
    assert attempts == 2


@pytest.mark.asyncio
async def test_perception_retries_busy_nvidia_endpoint_twice_with_backoff(monkeypatch):
    attempts = 0

    async def no_delay(seconds):
        assert seconds in (1, 2)

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ReadTimeout("upstream busy", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "transcript": "Hola", "scene_summary": "Mesa", "objects": [], "uncertainties": []
        })}}]})

    monkeypatch.setattr("nao_gateway.nemotron.asyncio.sleep", no_delay)
    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )

    assert (await client.perceive(b"wav", b"jpg")).transcript == "Hola"
    assert attempts == 3
