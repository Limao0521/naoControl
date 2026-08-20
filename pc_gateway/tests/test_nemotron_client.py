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

    content = captured["messages"][0]["content"]
    assert [item["type"] for item in content] == ["text", "input_audio", "image_url"]
    assert result.transcript == "¿Qué ves?"
    assert result.scene_summary == "Una botella roja"
    assert result.uncertainties == ["La imagen es pequeña"]


@pytest.mark.asyncio
async def test_decision_rejects_unknown_tool_shape():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"speech":"Hola","tool_calls":[{"name":"say","args":["Hola"]}]}'}}]
        })

    client = NemotronClient(
        "test-key", "https://example.test/v1", "agent-model", "omni-model",
        transport=httpx.MockTransport(handler),
    )
    decision = await client.decide("Hola", "Una mesa", [{"name": "say"}])

    assert decision.speech == "Hola"
    assert decision.tool_calls[0].name == "say"
    assert decision.tool_calls[0].arguments == {"text": "Hola"}


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
