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
        image = self.image_provider()
        if inspect.isawaitable(image):
            image = await image
        logger.info(
            "turn=%s media audio_bytes=%d image_bytes=%d",
            interaction_id, len(audio), len(image),
        )
        perception = await self.nemotron.perceive(audio, image)
        logger.info(
            "turn=%s perception transcript=%r scene=%r uncertainties=%r",
            interaction_id, perception.transcript, perception.scene_summary,
            perception.uncertainties,
        )
        decision = await self.nemotron.decide(
            perception.transcript, perception.scene_summary, self.tool_schemas()
        )
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
            logger.info("turn=%s action=%s status=%s", interaction_id, command["action"], result.get("status"))
        if decision.speech:
            speech_policy = PolicyEngine(self.registry)
            command = speech_policy.authorize("say", {"text": decision.speech[:500]})
            result = await self.robot.execute(command["action"], command["arguments"])
            logger.info("turn=%s action=say status=%s", interaction_id, result.get("status"))
