"""Safe runtime selection between cloud Nemotron and PC-local Gemma."""
from __future__ import annotations

import base64
import inspect
import json
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import TypeAdapter

from .nemotron import (
    AgentDecision,
    DECISION_SYSTEM_PROMPT,
    PERCEPTION_SYSTEM_PROMPT,
    Perception,
    _decision_content,
    _json_content,
    _native_tools,
    _normalize_decision,
    _normalize_string_list,
)
from .agent_identity import build_decision_system_prompt


class ProviderActivationError(RuntimeError):
    """A requested provider could not safely become active."""


class ProviderRouter:
    """Own lazy provider clients and preserve the last healthy selection."""

    def __init__(self, factories: dict[str, Callable[[], Any]]) -> None:
        self.factories = dict(factories)
        self.clients: dict[str, Any] = {}
        self.active_name = ""
        self.last_error = ""
        self.language = "es"

    def set_language(self, language: str) -> None:
        if language not in {"es", "en"}:
            raise ProviderActivationError("unsupported language")
        self.language = language
        for client in self.clients.values():
            setter = getattr(client, "set_language", None)
            if setter is not None:
                setter(language)

    async def activate(self, name: str) -> dict[str, Any]:
        if name not in self.factories:
            raise ProviderActivationError("unsupported provider")
        created = name not in self.clients
        client = self.clients.get(name)
        if client is None:
            try:
                client = self.factories[name]()
            except Exception as error:
                self.last_error = str(error) or type(error).__name__
                raise ProviderActivationError(self.last_error) from error
        setter = getattr(client, "set_language", None)
        if setter is not None:
            setter(self.language)
        try:
            validate = getattr(client, "validate", None)
            if validate is not None:
                result = validate()
                if inspect.isawaitable(result):
                    await result
        except Exception as error:
            self.last_error = str(error) or type(error).__name__
            if created:
                close = getattr(client, "close", None)
                if close is not None:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
            raise ProviderActivationError(self.last_error) from error
        self.clients[name] = client
        self.active_name = name
        self.last_error = ""
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "active": self.active_name,
            "healthy": bool(self.active_name),
            "error": self.last_error,
        }

    def _active(self):
        if not self.active_name:
            raise ProviderActivationError("no active provider")
        return self.clients[self.active_name]

    async def perceive(self, *args, **kwargs):
        return await self._active().perceive(*args, **kwargs)

    async def decide(self, *args, **kwargs):
        return await self._active().decide(*args, **kwargs)

    async def close(self) -> None:
        for client in list(self.clients.values()):
            close = getattr(client, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        self.clients.clear()
        self.active_name = ""

    async def replace_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Discard a stale provider client before changing its network endpoint."""
        if name not in self.factories:
            raise ProviderActivationError("unsupported provider")
        previous = self.clients.pop(name, None)
        if self.active_name == name:
            self.active_name = ""
        if previous is not None:
            close = getattr(previous, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        self.factories[name] = factory


class GemmaLocalClient:
    """OpenAI-compatible adapter for authenticated local or private-LAN Gemma."""

    def __init__(
        self,
        base_url: str,
        model: str = "",
        api_key: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        language: str = "es",
    ) -> None:
        self.model = model.strip()
        self.language = language
        self.decision_system_prompt = build_decision_system_prompt(language)
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": "Bearer " + (api_key.strip() or "local-no-key")},
            timeout=httpx.Timeout(180, connect=5),
            transport=transport,
        )

    def set_language(self, language: str) -> None:
        self.language = language
        self.decision_system_prompt = build_decision_system_prompt(language)

    async def validate(self) -> None:
        response = await self.client.get("/models")
        response.raise_for_status()
        models = response.json().get("data", [])
        identifiers = [item.get("id") for item in models if isinstance(item, dict)]
        identifiers = [item for item in identifiers if isinstance(item, str) and item]
        if not identifiers:
            raise ProviderActivationError("Gemma local did not report a model")
        if self.model and self.model not in identifiers:
            raise ProviderActivationError("configured Gemma model is unavailable")
        if not self.model:
            self.model = identifiers[0]

    async def _post(self, body: dict) -> httpx.Response:
        if not self.model:
            await self.validate()
        request_body = dict(body)
        request_body["model"] = self.model
        return await self.client.post("/chat/completions", json=request_body)

    async def perceive(
        self, audio_wav: bytes, image: bytes | None,
        image_media_type: str = "image/jpeg",
    ) -> Perception:
        content = [
            {"type": "text", "text": (
                "Transcribe fielmente el audio en el idioma hablado y describe solo la evidencia visible. "
                "Devuelve el objeto JSON solicitado."
            )},
            {"type": "input_audio", "input_audio": {
                "data": base64.b64encode(audio_wav).decode("ascii"),
                "format": "wav",
            }},
        ]
        if image:
            content.append({"type": "image_url", "image_url": {
                "url": "data:" + image_media_type + ";base64," +
                base64.b64encode(image).decode("ascii")
            }})
        response = await self._post({
            "model": self.model,
            "messages": [
                {"role": "system", "content": PERCEPTION_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        })
        data = _json_content(response)
        data["objects"] = _normalize_string_list(data.get("objects"))
        data["uncertainties"] = _normalize_string_list(data.get("uncertainties"))
        return TypeAdapter(Perception).validate_python(data)

    async def decide(self, transcript: str, scene: str, tools: list[dict]) -> AgentDecision:
        response = await self._post({
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.decision_system_prompt},
                {"role": "user", "content": json.dumps({
                    "transcript": transcript,
                    "visual_context": scene,
                    "tools": tools,
                }, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": 180,
            "chat_template_kwargs": {"enable_thinking": False},
            "tools": _native_tools(tools),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
        })
        data = _normalize_decision(_decision_content(response))
        return TypeAdapter(AgentDecision).validate_python(data)

    async def close(self) -> None:
        await self.client.aclose()
