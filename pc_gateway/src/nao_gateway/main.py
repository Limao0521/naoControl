"""Executable PC-side NAO Nemotron gateway."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .agent_host import AgentHost
from .config import GatewaySettings
from .nemotron import NemotronClient
from .robot_client import RobotClient
from .sensor_hub import fetch_latest_jpeg


async def run_gateway(settings: GatewaySettings, registry_path: Path) -> None:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    robot = RobotClient(settings.robot_url, settings.robot_shared_secret.encode("utf-8"))
    nemotron = NemotronClient(
        settings.nvidia_api_key, settings.nvidia_base_url,
        settings.agent_model, settings.vision_model,
    )
    robot_host = settings.robot_url.split("//", 1)[1].split(":", 1)[0]

    async def latest_image() -> bytes:
        return await fetch_latest_jpeg(f"http://{robot_host}:8080/video.mjpeg")

    host = AgentHost(robot, nemotron, latest_image, registry)
    await robot.connect()
    receiver = asyncio.create_task(robot.receive_forever())
    heartbeat = asyncio.create_task(robot.heartbeat_forever())
    print("PC Nemotron gateway connected. Waiting for bumper interactions.")
    try:
        while True:
            message_type, payload = await robot.events.get()
            if message_type != "heartbeat_result":
                print(f"Robot event: {message_type}")
            if message_type == "audio_result":
                try:
                    await host.handle_audio(payload)
                except Exception as error:
                    print(f"Interaction failed: {type(error).__name__}: {error}")
                    await robot.execute("say", {"text": "No pude procesar la solicitud."})
                finally:
                    await robot.complete_turn()
            elif message_type == "emergency":
                print("Emergency stop requested on robot.")
    finally:
        receiver.cancel()
        heartbeat.cancel()
        await robot.close()
        await nemotron.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--registry", default="config/action_registry.json")
    args = parser.parse_args()
    load_dotenv(args.env_file)
    settings = GatewaySettings.from_env(os.environ)
    asyncio.run(run_gateway(settings, Path(args.registry)))


if __name__ == "__main__":
    main()
