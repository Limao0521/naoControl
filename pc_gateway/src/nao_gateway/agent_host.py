"""One-turn orchestration from synchronized NAO media to safe actions."""
from __future__ import annotations

import base64
import inspect

from .policy_engine import PolicyEngine, PolicyViolation


class AgentHost:
    def __init__(self, robot, nemotron, image_provider, registry: dict) -> None:
        self.robot = robot
        self.nemotron = nemotron
        self.image_provider = image_provider
        self.registry = registry

    def tool_schemas(self) -> list[dict]:
        return [{"name": name, "constraints": rule} for name, rule in self.registry["actions"].items()]

    async def handle_audio(self, payload: dict) -> None:
        audio = base64.b64decode(payload["audio_b64"])
        image = self.image_provider()
        if inspect.isawaitable(image):
            image = await image
        perception = await self.nemotron.perceive(audio, image)
        decision = await self.nemotron.decide(
            perception.transcript, perception.scene_summary, self.tool_schemas()
        )
        policy = PolicyEngine(self.registry)
        for call in decision.tool_calls:
            try:
                command = policy.authorize(call.name, call.arguments)
            except PolicyViolation:
                continue
            await self.robot.execute(command["action"], command["arguments"])
        if decision.speech:
            command = policy.authorize("say", {"text": decision.speech[:500]})
            await self.robot.execute(command["action"], command["arguments"])
