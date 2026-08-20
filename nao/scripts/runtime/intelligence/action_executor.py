# -*- coding: utf-8 -*-
"""Translate allowlisted semantic actions into exact facade calls."""


class ActionExecutor(object):
    COLORS = {
        "off": (0.0, 0.0, 0.0), "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0), "blue": (0.0, 0.0, 1.0),
        "yellow": (1.0, 1.0, 0.0), "white": (1.0, 1.0, 1.0),
    }
    LED_GROUPS = ("FaceLeds", "ChestLeds", "EarLeds")
    def __init__(self, facade, registry):
        self.facade = facade
        self.registry = registry

    def _reject(self, reason):
        return {"status": "rejected", "reason": reason}

    def execute(self, command):
        action = command.get("action")
        arguments = command.get("arguments") or {}
        rule = self.registry.get("actions", {}).get(action)
        if rule is None:
            return self._reject("action_not_allowed")
        try:
            if action == "stop_all":
                self.facade.stop_move()
                self.facade.stop_all_behaviors()
            elif action == "say":
                text = arguments.get("text", "")
                if not text or len(text) > rule.get("max_text_length", 500):
                    return self._reject("invalid_text")
                self.facade.say(text)
            elif action == "set_led":
                group = arguments.get("group", "FaceLeds")
                color = self.COLORS.get(arguments.get("color"))
                if group not in self.LED_GROUPS or color is None:
                    return self._reject("invalid_led")
                self.facade.set_led_rgb(group, color[0], color[1], color[2], 0.3)
            elif action == "set_posture":
                posture = arguments.get("posture")
                if posture not in rule.get("allowed", []):
                    return self._reject("invalid_posture")
                speed = min(float(arguments.get("speed", 0.3)), rule.get("max_speed", 0.5))
                self.facade.go_to_posture(posture, speed)
            elif action == "look":
                yaw = float(arguments.get("yaw", 0.0))
                pitch = float(arguments.get("pitch", 0.0))
                yaw_range = rule.get("yaw_range", [-1.0, 1.0])
                pitch_range = rule.get("pitch_range", [-0.5, 0.5])
                if not yaw_range[0] <= yaw <= yaw_range[1] or not pitch_range[0] <= pitch <= pitch_range[1]:
                    return self._reject("unsafe_head_angle")
                speed = min(float(arguments.get("speed", 0.1)), rule.get("max_speed", 0.15))
                self.facade.set_angles("HeadYaw", yaw, speed)
                self.facade.set_angles("HeadPitch", pitch, speed)
            elif action == "run_behavior":
                behavior = self.registry.get("behaviors", {}).get(arguments.get("behavior_id"))
                if behavior is None:
                    return self._reject("unknown_behavior")
                posture = self.facade.get_posture()
                if posture not in rule.get("allowed_postures", []):
                    return self._reject("unsafe_posture")
                self.facade.run_behavior(behavior["package"])
            else:
                return self._reject("action_not_implemented")
        except Exception as error:
            return self._reject("facade_error: {}".format(error))
        return {"status": "completed", "action": action}
