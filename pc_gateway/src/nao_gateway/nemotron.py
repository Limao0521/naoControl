"""NVIDIA Nemotron multimodal perception and decision clients."""
from __future__ import annotations

import base64
import asyncio
import json
import logging
from typing import Any

import httpx
from pydantic import TypeAdapter
from pydantic.dataclasses import dataclass


PERCEPTION_SYSTEM_PROMPT = (
    "Eres el módulo de percepción multimodal de NAO. Transcribe el audio en español "
    "y describe solamente evidencia visible en la imagen. No inventes objetos ni "
    "atributos. Responde JSON con transcript, scene_summary, objects y uncertainties."
)

DECISION_SYSTEM_PROMPT = (
    "Eres el cerebro conversacional de NAO. Responde breve y amablemente en español. "
    "Usa solo las herramientas proporcionadas y nunca inventes una acción o información "
    "visual. Si hay incertidumbre, dilo. Devuelve exclusivamente JSON con speech y "
    "tool_calls; speech será pronunciado por NAO."
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
    content = message.get("content", "").strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Nemotron response did not contain JSON")
    return json.loads(content[start:end + 1])


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


class NemotronClient:
    def __init__(
        self, api_key: str, base_url: str, agent_model: str, omni_model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.agent_model = agent_model
        self.omni_model = omni_model
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(90, connect=10),
            transport=transport,
        )

    async def _post(self, body: dict) -> httpx.Response:
        response = await self.client.post("/chat/completions", json=body)
        if response.status_code in (502, 503, 504):
            await asyncio.sleep(0.25)
            response = await self.client.post("/chat/completions", json=body)
        return response

    async def perceive(
        self, audio_wav: bytes, image: bytes, image_media_type: str = "image/jpeg"
    ) -> Perception:
        content = [
            {"type": "input_audio", "input_audio": {
                "data": base64.b64encode(audio_wav).decode("ascii"), "format": "wav"
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
        })
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
            "temperature": 0.1,
            "max_tokens": 512,
        })
        data = _json_content(response)
        for call in data.get("tool_calls", []):
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
