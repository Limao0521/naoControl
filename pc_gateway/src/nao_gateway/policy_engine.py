"""Deterministic authorization boundary for model-selected NAO actions."""
from __future__ import annotations


class PolicyViolation(ValueError):
    pass


class PolicyEngine:
    def __init__(self, registry: dict) -> None:
        self.registry = registry
        self.tool_count = 0
        self.body_count = 0

    def authorize(self, name: str, arguments: dict) -> dict:
        rule = self.registry.get("actions", {}).get(name)
        if rule is None:
            raise PolicyViolation("tool is not allowlisted")
        if self.tool_count >= 3:
            raise PolicyViolation("turn tool budget exceeded")
        if rule.get("risk") == "body":
            if self.body_count >= 1:
                raise PolicyViolation("only one body action is allowed per turn")
            self.body_count += 1
        if name == "say" and len(arguments.get("text", "")) > rule.get("max_text_length", 500):
            raise PolicyViolation("speech is too long")
        if name == "set_led":
            if arguments.get("group") not in rule.get("groups", []):
                raise PolicyViolation("LED group is not allowed")
            if arguments.get("color") not in rule.get("colors", []):
                raise PolicyViolation("LED color is not allowed")
        if name == "look":
            yaw, pitch = arguments.get("yaw"), arguments.get("pitch")
            if yaw is None or pitch is None:
                raise PolicyViolation("look requires yaw and pitch")
            if not rule["yaw_range"][0] <= yaw <= rule["yaw_range"][1]:
                raise PolicyViolation("yaw is outside the safe range")
            if not rule["pitch_range"][0] <= pitch <= rule["pitch_range"][1]:
                raise PolicyViolation("pitch is outside the safe range")
        self.tool_count += 1
        return {"action": name, "arguments": arguments}
