"""Credential-safe live NVIDIA multimodal smoke test."""
from __future__ import annotations

import asyncio
import base64
import io
import os
import wave

from dotenv import load_dotenv

from .config import GatewaySettings
from .nemotron import NemotronClient


IMAGE_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
    "AQUBAScY42YAAAAASUVORK5CYII="
)


def silent_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(6400))
    return output.getvalue()


async def run() -> None:
    load_dotenv(".env")
    settings = GatewaySettings.from_env(os.environ)
    client = NemotronClient(
        settings.nvidia_api_key, settings.nvidia_base_url,
        settings.agent_model, settings.vision_model,
    )
    try:
        perception = await client.perceive(silent_wav(), IMAGE_1PX, "image/png")
        decision = await client.decide(
            perception.transcript, perception.scene_summary, [{"name": "say"}]
        )
        print("NVIDIA_PERCEPTION_OK=true")
        print("NVIDIA_DECISION_OK={}".format(bool(decision.speech)))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
