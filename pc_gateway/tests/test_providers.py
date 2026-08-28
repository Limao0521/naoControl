from __future__ import annotations

import json

import httpx
import pytest

try:
    from nao_gateway.providers import GemmaLocalClient, ProviderActivationError, ProviderRouter
except ImportError:
    GemmaLocalClient = None
    ProviderActivationError = RuntimeError
    ProviderRouter = None


class FakeProvider:
    def __init__(self, healthy=True):
        self.healthy = healthy
        self.closed = False
        self.language = "es"

    def set_language(self, language):
        self.language = language

    async def validate(self):
        if not self.healthy:
            raise RuntimeError("provider unavailable")

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_router_lazily_activates_provider_and_keeps_previous_on_failed_switch():
    """A failed Gemma health check must not break a working Nemotron session."""
    assert ProviderRouter is not None, "provider router is missing"
    created = []
    nemotron = FakeProvider()
    gemma = FakeProvider(healthy=False)

    def factory(name, provider):
        def create():
            created.append(name)
            return provider
        return create

    router = ProviderRouter({
        "nemotron": factory("nemotron", nemotron),
        "gemma_local": factory("gemma_local", gemma),
    })

    assert await router.activate("nemotron") == {
        "active": "nemotron", "healthy": True, "error": "",
    }
    assert created == ["nemotron"]

    with pytest.raises(ProviderActivationError, match="unavailable"):
        await router.activate("gemma_local")

    assert router.status()["active"] == "nemotron"
    assert router.status()["healthy"] is True


@pytest.mark.asyncio
async def test_router_rejects_unknown_provider_without_calling_factory():
    assert ProviderRouter is not None, "provider router is missing"
    router = ProviderRouter({"nemotron": lambda: FakeProvider()})

    with pytest.raises(ProviderActivationError, match="unsupported"):
        await router.activate("other")

    assert router.status()["active"] == ""


@pytest.mark.asyncio
async def test_router_applies_selected_language_to_current_and_future_provider():
    first = FakeProvider()
    second = FakeProvider()
    router = ProviderRouter({"nemotron": lambda: first, "gemma_local": lambda: second})

    router.set_language("en")
    await router.activate("nemotron")
    await router.activate("gemma_local")

    assert first.language == "en"
    assert second.language == "en"
    with pytest.raises(ProviderActivationError, match="unsupported language"):
        router.set_language("French")


@pytest.mark.asyncio
async def test_gemma_discovers_model_and_sends_wav_image_as_local_multimodal_content():
    """Changing Gemma media fields would make the documented llama.cpp API ignore audio."""
    assert GemmaLocalClient is not None, "Gemma local client is missing"
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma-local-model"}]})
        body = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "transcript": "Hola NAO", "scene_summary": "Una mesa",
            "objects": ["mesa"], "uncertainties": [],
        })}}]})

    client = GemmaLocalClient(
        "http://127.0.0.1:8080/v1", transport=httpx.MockTransport(handler)
    )

    await client.validate()
    perception = await client.perceive(b"RIFF-wav", b"jpeg")

    assert client.model == "gemma-local-model"
    body = json.loads(requests[-1].content)
    content = body["messages"][1]["content"]
    assert [item["type"] for item in content] == ["text", "input_audio", "image_url"]
    assert content[1]["input_audio"]["format"] == "wav"
    assert content[1]["input_audio"]["data"]
    assert content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert perception.transcript == "Hola NAO"


@pytest.mark.asyncio
async def test_gemma_lan_client_authenticates_every_request_with_configured_key():
    authorization = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorization.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"data": [{"id": "gemma-lan-model"}]})

    client = GemmaLocalClient(
        "http://172.23.12.52:8080/v1",
        api_key="private-lan-test-key",
        transport=httpx.MockTransport(handler),
    )

    await client.validate()

    assert authorization == ["Bearer private-lan-test-key"]


@pytest.mark.asyncio
async def test_gemma_decision_uses_same_native_safe_tool_contract():
    assert GemmaLocalClient is not None, "Gemma local client is missing"
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {
            "content": "Me sentaré.",
            "tool_calls": [{"type": "function", "function": {
                "name": "set_posture", "arguments": '{"posture":"Sit","speed":0.35}',
            }}],
        }}]})

    client = GemmaLocalClient(
        "http://127.0.0.1:8080/v1", model="gemma-local-model",
        transport=httpx.MockTransport(handler),
    )
    decision = await client.decide("Siéntate", "Área despejada", [{
        "name": "set_posture",
        "constraints": {"allowed": ["Stand", "Sit"], "max_speed": 0.5},
    }])

    assert captured["parallel_tool_calls"] is False
    assert captured["tools"][0]["function"]["name"] == "set_posture"
    assert decision.speech == "Me sentaré."
    assert decision.tool_calls[0].name == "set_posture"
    assert decision.tool_calls[0].arguments == {"posture": "Sit", "speed": 0.35}


@pytest.mark.asyncio
async def test_gemma_decision_uses_runtime_language_and_shared_identity():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {
            "content": '{"speech":"Hello","tool_calls":[]}',
        }}]})

    client = GemmaLocalClient(
        "http://127.0.0.1:8080/v1", model="gemma-local-model",
        language="en", transport=httpx.MockTransport(handler),
    )

    await client.decide("Hello", "A person", [])

    system_prompt = captured["messages"][0]["content"]
    assert "Respond only in English" in system_prompt
    assert "robotic captain of the HSL team" in system_prompt


@pytest.mark.asyncio
async def test_gemma_direct_turn_uses_discovered_model_in_first_completion():
    """Lazy discovery must update the request body, not only the client field."""
    completion_models = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "discovered-model"}]})
        body = json.loads(request.content)
        completion_models.append(body["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "transcript": "Hola", "scene_summary": "Sin cámara",
            "objects": [], "uncertainties": [],
        })}}]})

    client = GemmaLocalClient(
        "http://127.0.0.1:8080/v1", transport=httpx.MockTransport(handler)
    )

    await client.perceive(b"RIFF-wav", None)

    assert completion_models == ["discovered-model"]
