try:
    from nao.scripts.runtime.intelligence.led_controller import IntelligenceLedController
except ImportError:
    IntelligenceLedController = None


class FakeFacade(object):
    def __init__(self):
        self.calls = []

    def set_led_rgb(self, group, red, green, blue, duration=0.3):
        self.calls.append((group, red, green, blue, duration))
        return True


class FakeTimer(object):
    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.cancelled = False
        self.started = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.callback()


class TimerFactory(object):
    def __init__(self):
        self.timers = []

    def __call__(self, delay, callback):
        timer = FakeTimer(delay, callback)
        self.timers.append(timer)
        return timer


def controller(facade, timers):
    assert IntelligenceLedController is not None, "intelligent LED controller is missing"
    return IntelligenceLedController(facade, timer_factory=timers)


def test_face_action_remains_visible_across_turn_finish_then_restores_ready_color():
    """Restoring ready immediately would hide the user-requested eye color."""
    facade = FakeFacade()
    timers = TimerFactory()
    leds = controller(facade, timers)
    leds.set_mode("NEMOTRON_READY")
    facade.calls[:] = []

    assert leds.show_action("FaceLeds", 1.0, 0.0, 0.0, 0.3) is True
    leds.set_mode("NEMOTRON_READY", preserve_override=True)

    assert facade.calls == [("FaceLeds", 1.0, 0.0, 0.0, 0.3)]
    assert timers.timers[0].delay == 3.0
    assert timers.timers[0].started is True

    timers.timers[0].fire()
    assert facade.calls[-1] == ("FaceLeds", 0.0, 0.0, 1.0, 0.3)


def test_new_mode_cancels_override_and_stale_timer_cannot_overwrite_capture_color():
    """A stale three-second timer must not turn green capture eyes back to blue."""
    facade = FakeFacade()
    timers = TimerFactory()
    leds = controller(facade, timers)
    leds.set_mode("NEMOTRON_READY")
    leds.show_action("FaceLeds", 1.0, 0.0, 0.0)
    timer = timers.timers[0]

    leds.set_mode("CAPTURING")
    assert timer.cancelled is True
    assert facade.calls[-1] == ("FaceLeds", 0.0, 1.0, 0.0, 0.3)

    timer.fire()
    assert facade.calls[-1] == ("FaceLeds", 0.0, 1.0, 0.0, 0.3)


def test_chest_and_ear_actions_remain_persistent_without_restore_timer():
    facade = FakeFacade()
    timers = TimerFactory()
    leds = controller(facade, timers)

    assert leds.show_action("ChestLeds", 1.0, 1.0, 0.0) is True
    assert leds.show_action("EarLeds", 0.0, 0.0, 1.0) is True

    assert facade.calls == [
        ("ChestLeds", 1.0, 1.0, 0.0, 0.3),
        ("EarLeds", 0.0, 0.0, 1.0, 0.3),
    ]
    assert timers.timers == []
