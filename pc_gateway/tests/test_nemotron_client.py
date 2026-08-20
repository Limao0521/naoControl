import base64
import json

import httpx
import pytest

from nao_gateway.nemotron import NemotronClient


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
    assert [item["type"] for item in content] == ["input_audio", "image_url"]
    assert result.transcript == "¿Qué ves?"
    assert result.scene_summary == "Una botella roja"
    assert result.uncertainties == ["La imagen es pequeña"]


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
    assert captured["response_format"] == {"type": "json_object"}
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
