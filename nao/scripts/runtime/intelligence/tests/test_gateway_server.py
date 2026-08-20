import base64

from nao.scripts.runtime.intelligence.audio_capture import AudioCapture
from nao.scripts.runtime.intelligence.gateway_server import GatewayCore
from nao.scripts.runtime.intelligence.protocol import ReplayGuard, sign_envelope


class FakeRecorder(object):
    def __init__(self, files):
        self.calls = []
        self.files = files

    def startMicrophonesRecording(self, path, kind, rate, channels):
        self.calls.append(("start", path, kind, rate, channels))

    def stopMicrophonesRecording(self):
        self.calls.append(("stop",))
        self.files.data = b"RIFF-test-wav"


class FakeFiles(object):
    def __init__(self):
        self.data = None

    def read(self, path):
        return self.data

    def remove(self, path):
        self.data = None


class FakeExecutor(object):
    def __init__(self):
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return {"status": "completed", "action": command["action"]}


def unsigned(message_type, message_id, payload):
    return {
        "protocol_version": 1,
        "message_type": message_type,
        "message_id": message_id,
        "issued_at_ms": 1000,
        "expires_at_ms": 6000,
        "payload": payload,
    }


def test_audio_capture_returns_bounded_wav_bytes():
    files = FakeFiles()
    recorder = FakeRecorder(files)
    capture = AudioCapture(recorder, files=files, path="/tmp/test.wav")
    capture.start("interaction-1", now_ms=100)

    result = capture.stop(now_ms=900)

    assert result["interaction_id"] == "interaction-1"
    assert result["duration_ms"] == 800
    assert base64.b64decode(result["audio_b64"]) == b"RIFF-test-wav"
    assert files.data is None


def test_unsigned_command_is_rejected_without_execution():
    executor = FakeExecutor()
    core = GatewayCore(b"shared-secret", executor, now_ms=lambda: 1000)

    result = core.handle_message({"message_type": "command"})

    assert result["payload"]["status"] == "rejected"
    assert executor.commands == []


def test_signed_command_executes_allowlisted_action():
    executor = FakeExecutor()
    core = GatewayCore(b"shared-secret", executor, now_ms=lambda: 1000)
    envelope = sign_envelope(
        unsigned("command", "message-1", {"action": "say", "arguments": {"text": "Hola"}}),
        b"shared-secret",
    )

    result = core.handle_message(envelope)

    assert result["payload"]["status"] == "completed"
    assert executor.commands == [{"action": "say", "arguments": {"text": "Hola"}}]
