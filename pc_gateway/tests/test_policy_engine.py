import pytest

from nao_gateway.policy_engine import PolicyEngine, PolicyViolation


REGISTRY = {
    "actions": {
        "say": {"max_text_length": 500, "risk": "low"},
        "set_led": {"risk": "low", "groups": ["FaceLeds"], "colors": ["blue"]},
        "look": {"risk": "body", "yaw_range": [-1.0, 1.0], "pitch_range": [-0.5, 0.5]},
    }
}


def test_unknown_model_tool_is_rejected():
    with pytest.raises(PolicyViolation):
        PolicyEngine(REGISTRY).authorize("move", {})


def test_disabled_tool_is_rejected():
    registry = {"actions": {"play_sound": {"risk": "low", "enabled": False}}}
    with pytest.raises(PolicyViolation):
        PolicyEngine(registry).authorize("play_sound", {})


def test_turn_allows_at_most_one_body_action():
    policy = PolicyEngine(REGISTRY)
    policy.authorize("look", {"yaw": 0.1, "pitch": 0.0})
    with pytest.raises(PolicyViolation):
        policy.authorize("look", {"yaw": 0.2, "pitch": 0.0})


def test_led_arguments_must_match_registry():
    with pytest.raises(PolicyViolation):
        PolicyEngine(REGISTRY).authorize("set_led", {"group": "FaceLeds", "color": "purple"})
