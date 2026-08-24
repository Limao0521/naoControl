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


logger = logging.getLogger(__name__)


async def handle_audio_result(robot, host, payload: dict) -> None:
    """Finish a turn without allowing API or network errors to kill the gateway."""
    try:
        await host.handle_audio(payload)
    except Exception as error:
        logger.error("Interaction failed: %s: %s", type(error).__name__, error)
        try:
            await robot.execute("say", {"text": "No pude procesar la solicitud."})
        except Exception as fallback_error:
            logger.error(
                "Fallback speech failed: %s: %s",
                type(fallback_error).__name__, fallback_error,
            )
    finally:
        try:
            await robot.complete_turn()
        except Exception as completion_error:
            logger.error(
                "Turn completion failed: %s: %s",
                type(completion_error).__name__, completion_error,
            )


async def run_robot_session(robot, host) -> dict:
    """Process one connected robot session until the socket is lost."""
    receiver = asyncio.create_task(robot.receive_forever())
    heartbeat = asyncio.create_task(robot.heartbeat_forever())
    try:
        while True:
            message_type, payload = await robot.events.get()
            if message_type != "heartbeat_result":
                print(f"Robot event: {message_type}")
            if message_type == "connection_lost":
                return payload
            if message_type == "audio_result":
                await handle_audio_result(robot, host, payload)
            elif message_type == "emergency":
                print("Emergency stop requested on robot.")
    finally:
        receiver.cancel()
        heartbeat.cancel()
        await asyncio.gather(receiver, heartbeat, return_exceptions=True)


async def maintain_robot_connection(
    robot, host, retry_delay: float = 2.0, sleep=asyncio.sleep
) -> None:
    """Reconnect forever so a cable or robot restart does not kill Nemotron."""
    while True:
        try:
            await robot.connect()
            print("PC Nemotron gateway connected. Waiting for bumper interactions.")
            details = await run_robot_session(robot, host)
            logger.warning("Robot connection lost: %s", details.get("reason", "unknown"))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "Robot connection failed: %s: %s", type(error).__name__, error,
            )
        finally:
            try:
                await robot.close()
            except Exception as close_error:
                logger.warning(
                    "Robot close failed: %s: %s", type(close_error).__name__, close_error,
                )
        await sleep(retry_delay)


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

    host = AgentHost(
        robot, nemotron, latest_image, registry,
        state_publisher=robot.publish_interaction_state,
    )
    try:
        await maintain_robot_connection(robot, host)
    finally:
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
