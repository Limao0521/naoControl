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
}

COMMAND_PREFIX = (
    r"^(?:(?:nao|por favor|please)\s*,?\s*)?"
    r"(?:(?:quiero que|i want you to|can you|could you)\s+)?"
)

RUN_BEHAVIOR_PATTERNS = {
    "wave": COMMAND_PREFIX + r"(?:saluda|saludes|wave|haz\s+(?:un\s+)?saludo)\s*[.!?]*$",
    "yes": COMMAND_PREFIX + r"(?:asiente|asientas)(?:\s+con\s+la\s+cabeza)?\s*[.!?]*$|"
            + COMMAND_PREFIX + r"nod(?:\s+your\s+head)?\s*[.!?]*$",
    "no": COMMAND_PREFIX + r"(?:niega|niegues)(?:\s+con\s+la\s+cabeza)?\s*[.!?]*$|"
           + COMMAND_PREFIX + r"shake(?:\s+your)?\s+head\s*[.!?]*$",
    "thinking": COMMAND_PREFIX + r"(?:piensa|pienses|think)(?:\s+(?:un\s+momento|for\s+a\s+moment))?\s*[.!?]*$",
    "play_saxophone": COMMAND_PREFIX + r"(?:toca|toques)(?:\s+el)?\s+saxofon\s*[.!?]*$|"
                      + COMMAND_PREFIX + r"play(?:\s+the)?\s+saxophone\s*[.!?]*$",
    "taichi": COMMAND_PREFIX + r"(?:haz|hagas|practica|practiques)\s+(?:tai\s+chi|taichi)\s*[.!?]*$|"
              + COMMAND_PREFIX + r"(?:do|practice)\s+(?:tai\s+chi|taichi)\s*[.!?]*$",
}

DANCE_STYLES = {
    "dance_siu": ("siu", "ronaldo"),
    "dance_gangnam": ("gangnam",),
    "dance_macarena": ("macarena",),
}
DANCE_COMMAND_PATTERN = COMMAND_PREFIX + r"(?:baila|bailes|dance)\s*[.!?]*$"
DANCE_NAMED_COMMAND_PATTERNS = {
    behavior_id: COMMAND_PREFIX + r"(?:baila|bailes|dance)\s+(?:{})\s*[.!?]*$|".format(
        "|".join(styles),
    ) + COMMAND_PREFIX + r"(?:haz|hagas|do)\s+(?:{})\s*[.!?]*$".format(
        "|".join(styles),
    )
    for behavior_id, styles in DANCE_STYLES.items()
}
BEHAVIOR_NEGATION_PATTERN = r"\b(?:no|nunca|not|never|don\'t|do not)\b"

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
    if action == "run_behavior":
        behavior_id = (arguments or {}).get("behavior_id")
        normalized = _normalized_text(transcript)
        if not isinstance(behavior_id, str) or re.search(BEHAVIOR_NEGATION_PATTERN, normalized):
            return False
        if behavior_id.startswith("dance_"):
            named_styles = [
                dance_id for dance_id, styles in DANCE_STYLES.items()
                if any(re.search(r"\b{}\b".format(style), normalized) for style in styles)
            ]
            if len(named_styles) > 1 or (named_styles and named_styles[0] != behavior_id):
                return False
            if named_styles:
                return bool(re.search(DANCE_NAMED_COMMAND_PATTERNS[behavior_id], normalized))
            return bool(re.search(DANCE_COMMAND_PATTERN, normalized))
        pattern = RUN_BEHAVIOR_PATTERNS.get(behavior_id)
        return bool(pattern and re.search(pattern, normalized))
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
        tools = []
        for name, rule in self.registry["actions"].items():
            if not rule.get("enabled", True) or name == "say":
                continue
            constraints = dict(rule)
            if name == "run_behavior":
                constraints["allowed_behavior_ids"] = sorted(self.registry.get("behaviors", {}).keys())
            tools.append({"name": name, "constraints": constraints})
        return tools

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
