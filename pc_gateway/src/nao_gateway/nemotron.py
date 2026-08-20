"""NVIDIA Nemotron multimodal perception and decision clients."""
from __future__ import annotations

import base64
import asyncio
import ast
import json
import logging
from typing import Any

import httpx
from pydantic import TypeAdapter
from pydantic.dataclasses import dataclass


logger = logging.getLogger(__name__)


PERCEPTION_SYSTEM_PROMPT = (
    "Eres el módulo de percepción multimodal de NAO. Transcribe el audio en español "
    "y describe solamente evidencia visible en la imagen. No inventes objetos ni "
    "atributos. Responde JSON con transcript, scene_summary, objects y uncertainties."
)

DECISION_SYSTEM_PROMPT = (
    "Eres el cerebro conversacional de NAO. Responde breve y amablemente en español. "
    "Usa solo las herramientas proporcionadas y nunca inventes una acción o información "
    "visual. Si hay incertidumbre, dilo. Devuelve exclusivamente JSON con speech y "
    "tool_calls; speech será pronunciado por NAO. No uses Markdown. Ejemplo exacto: "
    "{\"speech\":\"Hola\",\"tool_calls\":[]}."
)


@dataclass
class Perception:
    transcript: str
    scene_summary: str
    objects: list[str]
    uncertainties: list[str]


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentDecision:
    speech: str
    tool_calls: list[ToolCall]


def _json_content(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    message = response.json()["choices"][0]["message"]
    content = (message.get("content") or "").strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    decoder = json.JSONDecoder()
    for start, character in enumerate(content):
        if character != "{":
            continue
        fragment = content[start:]
        try:
            value, _ = decoder.raw_decode(fragment)
        except json.JSONDecodeError:
            try:
                value = ast.literal_eval(fragment)
            except (SyntaxError, ValueError):
                continue
        if isinstance(value, dict):
            return value
    logger.warning(
        "NVIDIA response lacked JSON object finish_reason=%r content_chars=%d reasoning_chars=%d prefix=%r",
        response.json()["choices"][0].get("finish_reason"), len(content),
        len(message.get("reasoning") or ""), content[:160],
    )
    raise ValueError("Nemotron response did not contain a valid object")


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _normalize_decision(data: dict[str, Any]) -> dict[str, Any]:
    """Accept a text-only model response without turning it into an action."""
    if "speech" not in data:
        for key in ("response", "/response", "answer", "text"):
            if isinstance(data.get(key), str):
                data["speech"] = data[key]
                break
    data.setdefault("speech", "")
    data.setdefault("tool_calls", [])
    return data


class NemotronClient:
    MAX_ATTEMPTS = 3

    def __init__(
        self, api_key: str, base_url: str, agent_model: str, omni_model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.agent_model = agent_model
        self.omni_model = omni_model
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(60, connect=10),
            transport=transport,
        )

    async def _post(self, body: dict, stage: str) -> httpx.Response:
        """Retry temporary NVIDIA capacity failures with bounded backoff."""
        retry_statuses = (502, 503, 504)
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = await self.client.post("/chat/completions", json=body)
            except httpx.ReadTimeout:
                if attempt == self.MAX_ATTEMPTS:
                    logger.error(
                        "NVIDIA timeout stage=%s model=%s attempts=%d",
                        stage, body["model"], attempt,
                    )
                    raise
                delay = 2 ** (attempt - 1)
                logger.warning(
                    "NVIDIA timeout stage=%s model=%s attempt=%d/%d retry_in_s=%d",
                    stage, body["model"], attempt, self.MAX_ATTEMPTS, delay,
                )
                await asyncio.sleep(delay)
                continue
            if response.status_code not in retry_statuses or attempt == self.MAX_ATTEMPTS:
                return response
            delay = 2 ** (attempt - 1)
            logger.warning(
                "NVIDIA temporary_status=%d stage=%s model=%s attempt=%d/%d retry_in_s=%d",
                response.status_code, stage, body["model"], attempt,
                self.MAX_ATTEMPTS, delay,
            )
            await asyncio.sleep(delay)
        raise RuntimeError("unreachable NVIDIA retry state")

    async def perceive(
        self, audio_wav: bytes, image: bytes, image_media_type: str = "image/jpeg"
    ) -> Perception:
        content = [
            {"type": "audio_url", "audio_url": {
                "url": "data:audio/wav;base64," + base64.b64encode(audio_wav).decode("ascii")
            }},
            {"type": "image_url", "image_url": {
                "url": "data:" + image_media_type + ";base64," + base64.b64encode(image).decode("ascii")
            }},
        ]
        response = await self._post({
            "model": self.omni_model,
            "messages": [
                {"role": "system", "content": PERCEPTION_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }, "perception")
        data = _json_content(response)
        data["objects"] = _normalize_string_list(data.get("objects"))
        data["uncertainties"] = _normalize_string_list(data.get("uncertainties"))
        return TypeAdapter(Perception).validate_python(data)

    async def decide(self, transcript: str, scene: str, tools: list[dict]) -> AgentDecision:
        prompt = {
            "transcript": transcript,
            "visual_context": scene,
            "tools": tools,
        }
        response = await self._post({
            "model": self.agent_model,
            "messages": [
                {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": 180,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }, "decision")
        data = _json_content(response)
        data = _normalize_decision(data)
        for call in data["tool_calls"]:
            if "arguments" not in call and "args" in call:
                args = call.pop("args")
                if isinstance(args, dict):
                    call["arguments"] = args
                elif call.get("name") == "say" and isinstance(args, list) and args:
                    call["arguments"] = {"text": args[0]}
                else:
                    call["arguments"] = {}
        return TypeAdapter(AgentDecision).validate_python(data)

    async def close(self) -> None:
        await self.client.aclose()
