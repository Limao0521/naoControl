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
