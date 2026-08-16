from nao.scripts.runtime.intelligence.mode_manager import ModeManager


def test_left_hold_enters_nemotron_after_1500_ms():
    manager = ModeManager(initial_mode="WEB_CONTROL")
    assert manager.handle_bumper(True, False, 0) == []

    events = manager.handle_bumper(True, False, 1500)

    assert [event.name for event in events] == ["MODE_ENTER_REQUESTED"]
    assert manager.mode == "NEMOTRON_READY"


def test_left_hold_requires_release_before_second_toggle():
    manager = ModeManager(initial_mode="WEB_CONTROL")
    manager.handle_bumper(True, False, 0)
    manager.handle_bumper(True, False, 1500)

    assert manager.handle_bumper(True, False, 4000) == []
    manager.handle_bumper(False, False, 4100)
    manager.handle_bumper(True, False, 5000)
    events = manager.handle_bumper(True, False, 6500)

    assert [event.name for event in events] == ["MODE_EXIT_REQUESTED"]
    assert manager.mode == "WEB_CONTROL"


def test_right_release_finishes_capture():
    manager = ModeManager(initial_mode="NEMOTRON_READY")

    assert manager.handle_bumper(False, True, 100)[0].name == "CAPTURE_STARTED"
    assert manager.handle_bumper(False, False, 900)[0].name == "CAPTURE_FINISHED"
    assert manager.mode == "PROCESSING"


def test_both_bumpers_preempt_every_state():
    manager = ModeManager(initial_mode="ACTING")

    events = manager.handle_bumper(True, True, 500)

    assert manager.mode == "EMERGENCY"
    assert events[0].name == "EMERGENCY_REQUESTED"


def test_failed_entry_check_keeps_web_control():
    manager = ModeManager(initial_mode="WEB_CONTROL", entry_check=lambda: False)
    manager.handle_bumper(True, False, 0)

    events = manager.handle_bumper(True, False, 1500)

    assert [event.name for event in events] == ["MODE_ENTRY_REJECTED"]
    assert manager.mode == "WEB_CONTROL"
