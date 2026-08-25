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

    def set_led_rgb(self, group, red, green, blue, duration=0.3):
        self.calls.append(("set_led_rgb", group, red, green, blue, duration))
        return True

    def go_to_posture(self, posture, speed):
        self.calls.append(("go_to_posture", posture, speed))
        return True

    def set_angles(self, joint, angle, speed):
        self.calls.append(("set_angles", joint, angle, speed))
        return True


REGISTRY = {
    "actions": {
        "say": {"max_text_length": 500},
        "run_behavior": {"allowed_postures": ["Stand"]},
        "stop_all": {},
        "set_led": {},
        "set_posture": {"allowed": ["Stand", "Sit", "Crouch"], "max_speed": 0.5},
        "look": {"max_speed": 0.15, "yaw_range": [-1.0, 1.0], "pitch_range": [-0.5, 0.5]},
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


def test_led_uses_named_safe_color():
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "set_led", "arguments": {"group": "FaceLeds", "color": "blue"}}
    )
    assert result["status"] == "completed"
    assert facade.calls == [("set_led_rgb", "FaceLeds", 0.0, 0.0, 1.0, 0.3)]


def test_ear_led_rejects_non_blue_colors():
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "set_led", "arguments": {"group": "EarLeds", "color": "red"}}
    )
    assert result == {"status": "rejected", "reason": "invalid_ear_led_color"}
    assert facade.calls == []


def test_facade_failure_is_not_reported_as_completed():
    facade = FakeFacade()
    facade.say = lambda text: False

    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "say", "arguments": {"text": "Hola"}}
    )

    assert result == {"status": "rejected", "reason": "facade_failed"}


def test_async_facade_action_is_reported_as_accepted():
    facade = FakeFacade()
    facade.go_to_posture = lambda posture, speed: "accepted"

    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "set_posture", "arguments": {"posture": "Stand", "speed": 0.3}}
    )

    assert result == {"status": "accepted", "action": "set_posture"}


def test_posture_speed_defaults_to_035_and_clamps_to_050():
    facade = FakeFacade()
    executor = ActionExecutor(facade, REGISTRY)
    assert executor.execute({"action": "set_posture", "arguments": {"posture": "Stand"}}) == {
        "status": "completed", "action": "set_posture",
    }
    assert facade.calls[-1] == ("go_to_posture", "Stand", 0.35)
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "set_posture", "arguments": {"posture": "Stand", "speed": 0.9}}
    )
    assert result["status"] == "completed"
    assert facade.calls[-1] == ("go_to_posture", "Stand", 0.5)


def test_posture_speed_rejects_invalid_values_before_facade():
    for speed in (-0.1, 0, float("nan"), float("inf"), float("-inf"), "fast"):
        facade = FakeFacade()
        result = ActionExecutor(facade, REGISTRY).execute(
            {"action": "set_posture", "arguments": {"posture": "Stand", "speed": speed}}
        )
        assert result == {"status": "rejected", "reason": "invalid_posture_speed"}
        assert facade.calls == []


def test_look_rejects_angle_outside_registry_range():
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "look", "arguments": {"yaw": 2.0, "pitch": 0.0}}
    )
    assert result["status"] == "rejected"
    assert facade.calls == []


def test_look_moves_only_head_with_bounded_speed():
    facade = FakeFacade()
    result = ActionExecutor(facade, REGISTRY).execute(
        {"action": "look", "arguments": {"yaw": 0.4, "pitch": -0.2, "speed": 0.9}}
    )
    assert result["status"] == "completed"
    assert facade.calls == [
        ("set_angles", "HeadYaw", 0.4, 0.15),
        ("set_angles", "HeadPitch", -0.2, 0.15),
    ]
