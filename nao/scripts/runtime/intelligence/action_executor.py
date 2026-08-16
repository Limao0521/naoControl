# -*- coding: utf-8 -*-
"""Translate allowlisted semantic actions into exact facade calls."""


class ActionExecutor(object):
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
