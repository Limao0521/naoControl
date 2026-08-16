from nao.scripts.runtime.intelligence.action_executor import ActionExecutor
from nao.scripts.runtime.intelligence.safety_supervisor import SafetySupervisor


class FakeFacade(object):
    def __init__(self, posture="Stand", battery=80):
        self.posture = posture
        self.battery = battery
        self.calls = []

    def get_battery_level(self):
        return self.battery

    def get_posture(self):
        return self.posture

    def stop_move(self):
        self.calls.append(("stop_move",))
        return True

    def stop_all_behaviors(self):
        self.calls.append(("stop_all_behaviors",))
        return True

    def say(self, text):
        self.calls.append(("say", text))
        return True

    def run_behavior(self, name):
        self.calls.append(("run_behavior", name))
        return True


REGISTRY = {
    "actions": {
        "say": {"max_text_length": 500},
        "run_behavior": {"allowed_postures": ["Stand"]},
        "stop_all": {},
    },
    "behaviors": {"dance_siu": {"package": "siu-17777b/behavior_1"}},
}


def test_unknown_action_is_rejected_without_facade_call():
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute({"action": "move", "arguments": {}})
    assert result["status"] == "rejected"
    assert facade.calls == []


def test_behavior_requires_known_posture_and_registry_id():
    facade = FakeFacade(posture="Crouch")
    executor = ActionExecutor(facade, REGISTRY)
    result = executor.execute({"action": "run_behavior", "arguments": {"behavior_id": "dance_siu"}})
    assert result["status"] == "rejected"
    assert facade.calls == []


def test_known_behavior_uses_exact_package_name():
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "run_behavior", "arguments": {"behavior_id": "dance_siu"}}
    )
    assert result["status"] == "completed"
    assert facade.calls == [("run_behavior", "siu-17777b/behavior_1")]


def test_emergency_stop_preempts_body_actions():
    facade = FakeFacade()
    result = SafetySupervisor(facade).emergency_stop("both_bumpers")
    assert facade.calls[:2] == [("stop_move",), ("stop_all_behaviors",)]
    assert result == {"status": "stopped", "reason": "both_bumpers"}
