# -*- coding: utf-8 -*-
"""Translate allowlisted semantic actions into exact facade calls."""

import math


class ActionExecutor(object):
    COLORS = {
        "off": (0.0, 0.0, 0.0), "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0), "blue": (0.0, 0.0, 1.0),
        "yellow": (1.0, 1.0, 0.0), "white": (1.0, 1.0, 1.0),
    }
    LED_GROUPS = ("FaceLeds", "ChestLeds", "EarLeds")
    def __init__(self, facade, registry, led_controller=None):
        self.facade = facade
        self.registry = registry
        self.led_controller = led_controller

    def _reject(self, reason):
        return {"status": "rejected", "reason": reason}

    def _facade_failed(self, result):
        return result is False

    def execute(self, command):
        action = command.get("action")
        arguments = command.get("arguments") or {}
        status = "completed"
        rule = self.registry.get("actions", {}).get(action)
        if rule is None:
            return self._reject("action_not_allowed")
        try:
            if action == "stop_all":
                stopped_motion = self.facade.stop_move()
                stopped_behaviors = self.facade.stop_all_behaviors()
                if self._facade_failed(stopped_motion) or self._facade_failed(stopped_behaviors):
                    return self._reject("facade_failed")
            elif action == "say":
                text = arguments.get("text", "")
                if not text or len(text) > rule.get("max_text_length", 500):
                    return self._reject("invalid_text")
                outcome = self.facade.say(text)
                if self._facade_failed(outcome):
                    return self._reject("facade_failed")
                if outcome == "accepted":
                    status = "accepted"
            elif action == "set_led":
                group = arguments.get("group", "FaceLeds")
                color_name = arguments.get("color")
                color = self.COLORS.get(color_name)
                if group not in self.LED_GROUPS or color is None:
                    return self._reject("invalid_led")
                if group == "EarLeds" and color_name not in ("blue", "off"):
                    return self._reject("invalid_ear_led_color")
                led_target = self.led_controller or self.facade
                led_method = (
                    led_target.show_action if self.led_controller
                    else led_target.set_led_rgb
                )
                if self._facade_failed(led_method(group, color[0], color[1], color[2], 0.3)):
                    return self._reject("facade_failed")
            elif action == "set_posture":
                posture = arguments.get("posture")
                if posture not in rule.get("allowed", []):
                    return self._reject("invalid_posture")
                raw_speed = arguments.get("speed", 0.35)
                if isinstance(raw_speed, bool):
                    return self._reject("invalid_posture_speed")
                try:
                    speed = float(raw_speed)
                except (TypeError, ValueError):
                    return self._reject("invalid_posture_speed")
                if math.isnan(speed) or math.isinf(speed) or speed <= 0:
                    return self._reject("invalid_posture_speed")
                speed = min(speed, rule.get("max_speed", 0.5))
                outcome = self.facade.go_to_posture(posture, speed)
                if self._facade_failed(outcome):
                    return self._reject("facade_failed")
                if outcome == "accepted":
                    status = "accepted"
            elif action == "look":
                yaw = float(arguments.get("yaw", 0.0))
                pitch = float(arguments.get("pitch", 0.0))
                yaw_range = rule.get("yaw_range", [-1.0, 1.0])
                pitch_range = rule.get("pitch_range", [-0.5, 0.5])
                if not yaw_range[0] <= yaw <= yaw_range[1] or not pitch_range[0] <= pitch <= pitch_range[1]:
                    return self._reject("unsafe_head_angle")
                speed = min(float(arguments.get("speed", 0.1)), rule.get("max_speed", 0.15))
                if self._facade_failed(self.facade.set_angles("HeadYaw", yaw, speed)):
                    return self._reject("facade_failed")
                if self._facade_failed(self.facade.set_angles("HeadPitch", pitch, speed)):
                    return self._reject("facade_failed")
            elif action == "run_behavior":
                behavior = self.registry.get("behaviors", {}).get(arguments.get("behavior_id"))
                if behavior is None:
                    return self._reject("unknown_behavior")
                posture = self.facade.get_posture()
                if posture not in rule.get("allowed_postures", []):
                    return self._reject("unsafe_posture")
                outcome = self.facade.run_behavior(behavior["package"])
                if self._facade_failed(outcome):
                    return self._reject("facade_failed")
                if outcome == "accepted":
                    status = "accepted"
            else:
                return self._reject("action_not_implemented")
        except Exception as error:
            return self._reject("facade_error: {}".format(error))
        return {"status": status, "action": action}
