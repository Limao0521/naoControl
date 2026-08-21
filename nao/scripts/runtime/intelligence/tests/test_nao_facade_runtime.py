import importlib
import sys
import types


class FakeLogger(object):
    def __init__(self):
        self.messages = []

    def debug(self, message): self.messages.append(("debug", message))
    def info(self, message): self.messages.append(("info", message))
    def warning(self, message): self.messages.append(("warning", message))
    def error(self, message): self.messages.append(("error", message))


class FakePost(object):
    def __init__(self):
        self.calls = []

    def say(self, text):
        self.calls.append(("say", text))
        return 11

    def goToPosture(self, posture, speed):
        self.calls.append(("goToPosture", posture, speed))
        return 12

    def runBehavior(self, behavior):
        self.calls.append(("runBehavior", behavior))
        return 13


class FakeProxy(object):
    def __init__(self):
        self.post = FakePost()
        self.calls = []

    def setLanguage(self, language):
        self.calls.append(("setLanguage", language))

    def fadeRGB(self, group, rgb, duration):
        self.calls.append(("fadeRGB", group, rgb, duration))

    def getRunningBehaviors(self):
        return []

    def isBehaviorInstalled(self, behavior):
        return True


def load_facade(monkeypatch):
    fake_naoqi = types.ModuleType("naoqi")
    fake_naoqi.ALProxy = lambda *args: None
    monkeypatch.setitem(sys.modules, "naoqi", fake_naoqi)
    module_name = "nao.scripts.runtime.control_server.facades.nao_facade"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name).NAOFacade


def bare_facade(nao_facade):
    facade = nao_facade.__new__(nao_facade)
    facade.logger = FakeLogger()
    for name in ("motion", "posture", "life", "leds", "tts", "battery", "memory", "audio", "behavior"):
        setattr(facade, name, None)
    return facade


def test_long_running_naoqi_actions_are_posted_without_blocking(monkeypatch):
    nao_facade = load_facade(monkeypatch)
    facade = bare_facade(nao_facade)
    facade.tts = FakeProxy()
    facade.posture = FakeProxy()
    facade.behavior = FakeProxy()

    assert facade.say("Hola") == "accepted"
    assert facade.go_to_posture("Stand", 0.3) == "accepted"
    assert facade.run_behavior("dance/behavior_1") == "accepted"
    assert facade.tts.post.calls == [("say", "Hola")]
    assert facade.posture.post.calls == [("goToPosture", "Stand", 0.3)]
    assert facade.behavior.post.calls == [("runBehavior", "dance/behavior_1")]


def test_led_group_is_native_string_before_naoqi_call(monkeypatch):
    nao_facade = load_facade(monkeypatch)
    facade = bare_facade(nao_facade)
    facade.leds = FakeProxy()

    class StringLike(object):
        def __str__(self):
            return "FaceLeds"

    assert facade.set_led_rgb(StringLike(), 1.0, 0.0, 0.0) is True
    group = facade.leds.calls[0][1]
    assert type(group) is str
    assert group == "FaceLeds"


def test_initial_state_selects_spanish_tts(monkeypatch):
    nao_facade = load_facade(monkeypatch)
    facade = bare_facade(nao_facade)
    facade.tts = FakeProxy()

    facade._setup_initial_state()

    assert ("setLanguage", "Spanish") in facade.tts.calls
