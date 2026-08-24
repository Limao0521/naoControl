import pytest

from nao.scripts.runtime.interaction_state import InteractionStateStore


def test_store_persists_only_the_latest_bounded_turn(tmp_path):
    store = InteractionStateStore(str(tmp_path / "interaction.json"), now_ms=lambda: 1234)

    saved = store.save({
        "interaction_id": "turn-1",
        "phase": "ready",
        "transcript": "¿Qué ves?",
        "response": "Veo un Pikachu.",
        "actions": [{"name": "set_led", "status": "completed", "reason": None}],
    })

    assert saved == {
        "interaction_id": "turn-1", "phase": "ready",
        "transcript": "¿Qué ves?", "response": "Veo un Pikachu.",
        "actions": [{"name": "set_led", "status": "completed", "reason": None}],
        "updated_at_ms": 1234,
    }
    assert store.load() == saved


def test_store_rejects_unbounded_or_unknown_interaction_data(tmp_path):
    store = InteractionStateStore(str(tmp_path / "interaction.json"))

    with pytest.raises(ValueError):
        store.save({
            "interaction_id": "turn-1", "phase": "unknown",
            "transcript": "", "response": "", "actions": [],
        })
    with pytest.raises(ValueError):
        store.save({
            "interaction_id": "turn-1", "phase": "ready",
            "transcript": "x" * 2001, "response": "", "actions": [],
        })


def test_store_accepts_python2_byte_string_identifiers(tmp_path):
    """A uuid str from Python 2 must not kill the physical bumper loop."""
    store = InteractionStateStore(str(tmp_path / "interaction.json"), now_ms=lambda: 99)

    saved = store.save({
        "interaction_id": b"turn-from-python2",
        "phase": "listening",
        "transcript": "", "response": "", "actions": [],
    })

    assert saved["interaction_id"] == "turn-from-python2"
    assert store.load()["phase"] == "listening"
