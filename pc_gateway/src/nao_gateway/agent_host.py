"""One-turn orchestration from synchronized NAO media to safe actions."""
from __future__ import annotations

import base64
import inspect
import logging

from .policy_engine import PolicyEngine, PolicyViolation


logger = logging.getLogger(__name__)


class AgentHost:
    def __init__(self, robot, nemotron, image_provider, registry: dict) -> None:
        self.robot = robot
        self.nemotron = nemotron
        self.image_provider = image_provider
        self.registry = registry

    def tool_schemas(self) -> list[dict]:
        return [
            {"name": name, "constraints": rule}
            for name, rule in self.registry["actions"].items()
            if rule.get("enabled", True) and name != "say"
        ]

    async def handle_audio(self, payload: dict) -> None:
        interaction_id = payload.get("interaction_id", "unknown")
        audio = base64.b64decode(payload["audio_b64"])
        try:
            image = self.image_provider()
            if inspect.isawaitable(image):
                image = await image
        except Exception as error:
            logger.warning(
                "VISION_UNAVAILABLE turn=%s error=%s: %s",
                interaction_id, type(error).__name__, error,
            )
            image = None
        logger.info(
            "turn=%s media audio_bytes=%d image_bytes=%d",
            interaction_id, len(audio), len(image or b""),
        )
        logger.info(
            "turn=%s audio_diagnostics=%r", interaction_id,
            payload.get("audio_diagnostics", {}),
        )
        try:
            perception = await self.nemotron.perceive(audio, image)
        except Exception as error:
            logger.error(
                "PERCEPTION_FAILED turn=%s error=%s: %s",
                interaction_id, type(error).__name__, error,
            )
            raise
        print(
            "TRANSCRIPTION turn={} text={!r}".format(
                interaction_id, perception.transcript or "(vacía)"
            )
        )
        logger.info(
            "turn=%s perception transcript=%r scene=%r uncertainties=%r",
            interaction_id, perception.transcript, perception.scene_summary,
            perception.uncertainties,
        )
        try:
            decision = await self.nemotron.decide(
                perception.transcript, perception.scene_summary, self.tool_schemas()
            )
        except Exception as error:
            logger.error(
                "DECISION_FAILED turn=%s error=%s: %s",
                interaction_id, type(error).__name__, error,
            )
            raise
        logger.info(
            "turn=%s decision speech=%r tools=%r",
            interaction_id, decision.speech,
            [call.name for call in decision.tool_calls],
        )
        policy = PolicyEngine(self.registry)
        for call in decision.tool_calls:
            try:
                command = policy.authorize(call.name, call.arguments)
            except PolicyViolation as error:
                logger.warning("turn=%s rejected_tool=%s reason=%s", interaction_id, call.name, error)
                continue
            result = await self.robot.execute(command["action"], command["arguments"])
            logger.info(
                "turn=%s action=%s arguments=%r status=%s reason=%s",
                interaction_id, command["action"], command["arguments"],
                result.get("status"), result.get("reason"),
            )
        if decision.speech:
            speech_policy = PolicyEngine(self.registry)
            command = speech_policy.authorize("say", {"text": decision.speech[:500]})
            result = await self.robot.execute(command["action"], command["arguments"])
            logger.info(
                "turn=%s action=say status=%s reason=%s",
                interaction_id, result.get("status"), result.get("reason"),
            )
