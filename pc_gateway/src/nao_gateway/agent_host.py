"""One-turn orchestration from synchronized NAO media to safe actions."""
from __future__ import annotations

import base64
import inspect
import logging
import re
import unicodedata

from .policy_engine import PolicyEngine, PolicyViolation


logger = logging.getLogger(__name__)


BODY_ACTION_CUES = {
    "look": ("mira", "mirar", "voltea", "gira la cabeza", "look at", "turn your head"),
    "run_behavior": ("baila", "baile", "danza", "dance", "comportamiento", "behavior"),
}

POSTURE_CUES = {
    "Stand": (
        "parate", "pararte", "levantate", "levantarte", "levantarse",
        "levantes", "levantas", "ponte de pie", "ponerte de pie",
        "estar de pie", "stand up",
    ),
    "StandInit": (
        "parate", "pararte", "levantate", "levantarte", "levantarse",
        "levantes", "levantas", "ponte de pie", "ponerte de pie",
        "estar de pie", "stand up",
    ),
    "Sit": (
        "sientate", "sentarte", "sentarse", "sientes", "toma asiento",
        "sit down",
    ),
    "Crouch": ("agachate", "agacharte", "agacharse", "crouch"),
}

POSTURE_NEGATION_PATTERNS = {
    "Stand": (
        r"\b(?:no|nunca)\s+(?:quiero\s+que\s+)?(?:te\s+)?(?:levantes|pares)\b",
        r"\b(?:no|nunca)\s+(?:quiero\s+)?(?:levantarte|pararte|ponerte\s+de\s+pie)\b",
        r"\b(?:do\s+not|don't)\s+(?:stand\s+up|get\s+up)\b",
    ),
    "StandInit": (
        r"\b(?:no|nunca)\s+(?:quiero\s+que\s+)?(?:te\s+)?(?:levantes|pares)\b",
        r"\b(?:no|nunca)\s+(?:quiero\s+)?(?:levantarte|pararte|ponerte\s+de\s+pie)\b",
        r"\b(?:do\s+not|don't)\s+(?:stand\s+up|get\s+up)\b",
    ),
    "Sit": (
        r"\b(?:no|nunca)\s+(?:quiero\s+que\s+)?(?:te\s+)?sientes\b",
        r"\b(?:no|nunca)\s+(?:quiero\s+)?(?:sentarte|tomar\s+asiento)\b",
        r"\b(?:do\s+not|don't)\s+sit\s+down\b",
    ),
    "Crouch": (
        r"\b(?:no|nunca)\s+(?:quiero\s+que\s+)?(?:te\s+)?agaches\b",
        r"\b(?:no|nunca)\s+(?:quiero\s+)?agacharte\b",
        r"\b(?:do\s+not|don't)\s+crouch\b",
    ),
}


def _normalized_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"\s+", " ", "".join(c for c in decomposed if not unicodedata.combining(c)))


def _physical_action_explicitly_requested(
    action: str, transcript: str, arguments: dict | None = None,
) -> bool:
    if action == "set_posture":
        posture = (arguments or {}).get("posture")
        cues = POSTURE_CUES.get(posture, ())
        normalized = _normalized_text(transcript)
        if any(
            re.search(pattern, normalized)
            for pattern in POSTURE_NEGATION_PATTERNS.get(posture, ())
        ):
            return False
        return any(cue in normalized for cue in cues)
    cues = BODY_ACTION_CUES.get(action)
    if cues is None:
        return True
    normalized = _normalized_text(transcript)
    return any(cue in normalized for cue in cues)


class AgentHost:
    def __init__(
        self, robot, nemotron, image_provider, registry: dict,
        state_publisher=None,
    ) -> None:
        self.robot = robot
        self.nemotron = nemotron
        self.image_provider = image_provider
        self.registry = registry
        self.state_publisher = state_publisher

    async def _publish_state(
        self, interaction_id: str, phase: str, transcript: str = "",
        response: str = "", actions: list[dict] | None = None,
    ) -> None:
        if self.state_publisher is None:
            return
        update = {
            "interaction_id": interaction_id,
            "phase": phase,
            "transcript": transcript,
            "response": response,
            "actions": [dict(item) for item in (actions or [])],
        }
        try:
            result = self.state_publisher(update)
            if inspect.isawaitable(result):
                await result
        except Exception as error:
            logger.warning(
                "STATE_PUBLISH_FAILED turn=%s error=%s: %s",
                interaction_id, type(error).__name__, error,
            )

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
        await self._publish_state(
            interaction_id, "processing", transcript=perception.transcript,
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
        action_states = [
            {"name": call.name, "status": "pending", "reason": None}
            for call in decision.tool_calls
        ]
        await self._publish_state(
            interaction_id, "responding", perception.transcript,
            decision.speech, action_states,
        )
        policy = PolicyEngine(self.registry)
        for index, call in enumerate(decision.tool_calls):
            if not _physical_action_explicitly_requested(
                call.name, perception.transcript, call.arguments,
            ):
                logger.warning(
                    "turn=%s rejected_tool=%s reason=physical_action_not_explicitly_requested",
                    interaction_id, call.name,
                )
                action_states[index] = {
                    "name": call.name, "status": "rejected",
                    "reason": "physical_action_not_explicitly_requested",
                }
                await self._publish_state(
                    interaction_id, "responding", perception.transcript,
                    decision.speech, action_states,
                )
                continue
            try:
                command = policy.authorize(call.name, call.arguments)
            except PolicyViolation as error:
                logger.warning("turn=%s rejected_tool=%s reason=%s", interaction_id, call.name, error)
                action_states[index] = {
                    "name": call.name, "status": "rejected", "reason": str(error),
                }
                await self._publish_state(
                    interaction_id, "responding", perception.transcript,
                    decision.speech, action_states,
                )
                continue
            result = await self.robot.execute(command["action"], command["arguments"])
            action_states[index] = {
                "name": command["action"], "status": result.get("status", "unknown"),
                "reason": result.get("reason"),
            }
            logger.info(
                "turn=%s action=%s arguments=%r status=%s reason=%s",
                interaction_id, command["action"], command["arguments"],
                result.get("status"), result.get("reason"),
            )
            await self._publish_state(
                interaction_id, "responding", perception.transcript,
                decision.speech, action_states,
            )
        if decision.speech:
            speech_policy = PolicyEngine(self.registry)
            command = speech_policy.authorize("say", {"text": decision.speech[:500]})
            result = await self.robot.execute(command["action"], command["arguments"])
            logger.info(
                "turn=%s action=say status=%s reason=%s",
                interaction_id, result.get("status"), result.get("reason"),
            )
        await self._publish_state(
            interaction_id, "ready", perception.transcript,
            decision.speech, action_states,
        )
