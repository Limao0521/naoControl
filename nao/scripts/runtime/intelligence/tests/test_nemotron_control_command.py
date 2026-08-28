import json
import sys
from pathlib import Path

COMMANDS = Path("nao/scripts/runtime/control_server/commands").resolve()
CONTROL = COMMANDS.parent
RUNTIME = CONTROL.parent
for path in (str(RUNTIME), str(CONTROL), str(COMMANDS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from nemotron_commands import NemotronStatusCommand
try:
    from nemotron_commands import (
        IntelligenceProviderStatusCommand,
        SetGemmaEndpointCommand,
        SetIntelligenceLanguageCommand,
        SetIntelligenceProviderCommand,
    )
except ImportError:
    IntelligenceProviderStatusCommand = None
    SetIntelligenceProviderCommand = None
    SetIntelligenceLanguageCommand = None
    SetGemmaEndpointCommand = None
from command_factory import CommandFactory


class FakeLogger(object):
    def info(self, message):
        pass

    def error(self, message):
        pass

    def warning(self, message):
        pass

    def debug(self, message):
        pass


class FakeSocket(object):
    def __init__(self, address=None):
        self.messages = []
        self.address = {"library_specific": True}
        self.client = FakeClient(address or ["::ffff:169.254.151.5", 54321])

    def sendMessage(self, message):
        self.messages.append(json.loads(message))


class FakeClient(object):
    def __init__(self, peer):
        self.peer = peer

    def getpeername(self):
        return self.peer


class FakeStore(object):
    def load(self):
        return {
            "interaction_id": "turn-1", "phase": "ready",
            "transcript": "Hola NAO", "response": "Hola, ¿cómo estás?",
            "actions": [], "updated_at_ms": 1234,
        }


class FakeTargetStore(object):
    def __init__(self, pc_ip="169.254.151.5"):
        self.pc_ip = pc_ip

    def load(self):
        return {"pc_ip": self.pc_ip}

    def save(self, pc_ip):
        self.pc_ip = pc_ip
        return {"pc_ip": pc_ip}


def test_status_command_returns_last_nemotron_turn_to_web_client():
    socket = FakeSocket()
    command = NemotronStatusCommand(
        None, FakeLogger(), state_store=FakeStore(),
        target_store=FakeTargetStore(),
    )

    success = command.execute({"action": "nemotronStatus"}, socket)

    assert success is True
    assert socket.messages == [{
        "nemotronStatus": {
            "success": True,
            "interaction_id": "turn-1", "phase": "ready",
            "transcript": "Hola NAO", "response": "Hola, ¿cómo estás?",
            "actions": [], "updated_at_ms": 1234,
        }
    }]


def test_status_command_rejects_clients_other_than_configured_pc_without_text():
    socket = FakeSocket(address=("::ffff:169.254.151.99", 54321))
    command = NemotronStatusCommand(
        None, FakeLogger(), state_store=FakeStore(),
        target_store=FakeTargetStore(),
    )

    success = command.execute({"action": "nemotronStatus"}, socket)

    assert success is False
    assert socket.messages == [{
        "nemotronStatus": {"success": False, "error": "forbidden"}
    }]
    assert "transcript" not in json.dumps(socket.messages)


def test_command_factory_exposes_nemotron_status_to_websocket_clients():
    command = CommandFactory(None, FakeLogger()).create_command("nemotronStatus")

    assert isinstance(command, NemotronStatusCommand)


class FakeProviderStore(object):
    def __init__(self):
        self.state = {
            "selected": "nemotron", "active": "nemotron", "healthy": True,
            "error": "", "language": "es", "updated_at_ms": 1234,
            "gemma_base_url": "", "gemma_endpoint_version": 0,
        }

    def load(self):
        return dict(self.state)

    def save_selected(self, selected):
        self.state["selected"] = selected
        return dict(self.state)

    def save_language(self, language):
        self.state["language"] = language
        return dict(self.state)

    def save_gemma_base_url(self, endpoint):
        self.state["gemma_base_url"] = endpoint
        return dict(self.state)


def test_provider_status_exposes_only_bounded_nonsecret_state_to_configured_pc():
    assert IntelligenceProviderStatusCommand is not None, "provider status command is missing"
    socket = FakeSocket()
    command = IntelligenceProviderStatusCommand(
        None, FakeLogger(), provider_store=FakeProviderStore(),
        target_store=FakeTargetStore(),
    )

    assert command.execute({"action": "intelligenceProviderStatus"}, socket) is True
    assert socket.messages == [{"intelligenceProviderStatus": {
        "success": True, "selected": "nemotron", "active": "nemotron",
        "healthy": True, "error": "", "language": "es", "updated_at_ms": 1234,
        "gemma_base_url": "", "gemma_endpoint_version": 0,
    }}]
    assert "key" not in json.dumps(socket.messages).lower()
    assert "api_key" not in json.dumps(socket.messages).lower()


def test_provider_selection_persists_allowlisted_value_from_configured_pc():
    assert SetIntelligenceProviderCommand is not None, "provider selection command is missing"
    socket = FakeSocket()
    provider_store = FakeProviderStore()
    command = SetIntelligenceProviderCommand(
        None, FakeLogger(), provider_store=provider_store,
        target_store=FakeTargetStore(),
    )

    assert command.execute({
        "action": "setIntelligenceProvider", "provider": "gemma_local",
    }, socket) is True
    assert provider_store.state["selected"] == "gemma_local"
    assert socket.messages[0]["setIntelligenceProvider"]["selected"] == "gemma_local"


def test_gemma_endpoint_is_configured_from_the_allowed_pc_without_a_key():
    assert SetGemmaEndpointCommand is not None, "Gemma endpoint command is missing"
    socket = FakeSocket()
    provider_store = FakeProviderStore()
    command = SetGemmaEndpointCommand(
        None, FakeLogger(), provider_store=provider_store,
        target_store=FakeTargetStore(),
    )

    assert command.execute({
        "action": "setGemmaEndpoint",
        "gemma_ip": "192.168.23.1",
    }, socket) is True
    assert provider_store.state["gemma_base_url"] == "http://192.168.23.1:8080/v1"
    assert "key" not in json.dumps(socket.messages).lower()


def test_gemma_configuration_separates_browser_gateway_ip_from_model_ip():
    socket = FakeSocket(address=("192.168.23.233", 5555))
    target_store = FakeTargetStore("192.168.23.99")
    provider_store = FakeProviderStore()
    command = SetGemmaEndpointCommand(
        None, FakeLogger(), provider_store=provider_store,
        target_store=target_store,
    )

    assert command.execute({
        "action": "setGemmaEndpoint", "gemma_ip": "192.168.23.1",
    }, socket) is True
    assert target_store.pc_ip == "192.168.23.233"
    assert provider_store.state["gemma_base_url"] == "http://192.168.23.1:8080/v1"


def test_provider_selection_infers_gateway_target_from_private_browser_peer():
    assert SetIntelligenceProviderCommand is not None, "provider selection command is missing"
    socket = FakeSocket(address=("169.254.151.99", 5555))
    provider_store = FakeProviderStore()
    command = SetIntelligenceProviderCommand(
        None, FakeLogger(), provider_store=provider_store,
        target_store=FakeTargetStore(),
    )

    assert command.execute({
        "action": "setIntelligenceProvider", "provider": "gemma_local",
    }, socket) is True
    assert provider_store.state["selected"] == "gemma_local"
    assert command.target_store.pc_ip == "169.254.151.99"


def test_command_factory_exposes_provider_status_and_selection_commands():
    factory = CommandFactory(None, FakeLogger())

    assert isinstance(
        factory.create_command("intelligenceProviderStatus"),
        IntelligenceProviderStatusCommand,
    )
    assert isinstance(
        factory.create_command("setIntelligenceProvider"),
        SetIntelligenceProviderCommand,
    )
    assert isinstance(
        factory.create_command("setIntelligenceLanguage"),
        SetIntelligenceLanguageCommand,
    )
    assert isinstance(factory.create_command("setGemmaEndpoint"), SetGemmaEndpointCommand)


def test_intelligence_language_updates_tts_and_persisted_agent_language():
    class Facade(object):
        def __init__(self):
            self.languages = []

        def set_language(self, language):
            self.languages.append(language)
            return True

    socket = FakeSocket()
    facade = Facade()
    provider_store = FakeProviderStore()
    command = SetIntelligenceLanguageCommand(
        facade, FakeLogger(), provider_store=provider_store,
        target_store=FakeTargetStore(),
    )

    assert command.execute({
        "action": "setIntelligenceLanguage", "language": "en",
    }, socket) is True
    assert facade.languages == ["English"]
    assert provider_store.state["language"] == "en"
    assert socket.messages[0]["setIntelligenceLanguage"]["language"] == "en"
