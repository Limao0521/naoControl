import pytest
import asyncio

from nao_gateway import main as main_module


class BrokenHost(object):
    async def handle_audio(self, payload):
        raise TimeoutError("model timeout")


class FragileRobot(object):
    def __init__(self):
        self.calls = []

    async def execute(self, action, arguments):
        self.calls.append((action, arguments))
        raise ConnectionError("robot disconnected")

    async def complete_turn(self):
        self.calls.append(("complete_turn", {}))
        raise ConnectionError("robot disconnected")


@pytest.mark.asyncio
async def test_failed_interaction_does_not_crash_when_robot_disconnects(caplog):
    robot = FragileRobot()

    await main_module.handle_audio_result(robot, BrokenHost(), {"audio_b64": ""})

    assert robot.calls == [
        ("say", {"text": "No pude procesar la solicitud."}),
        ("complete_turn", {}),
    ]
    assert "Interaction failed: TimeoutError" in caplog.text
    assert "Fallback speech failed: ConnectionError" in caplog.text
    assert "Turn completion failed: ConnectionError" in caplog.text


@pytest.mark.asyncio
async def test_connection_manager_reconnects_after_robot_session_is_lost():
    class StopAfterReconnect(BaseException):
        pass

    class ReconnectingRobot(object):
        def __init__(self):
            self.events = asyncio.Queue()
            self.connect_count = 0
            self.close_count = 0

        async def connect(self):
            self.connect_count += 1
            if self.connect_count == 2:
                raise StopAfterReconnect()

        async def receive_forever(self):
            await self.events.put(("connection_lost", {"reason": "test disconnect"}))

        async def heartbeat_forever(self):
            await asyncio.Future()

        async def close(self):
            self.close_count += 1

    robot = ReconnectingRobot()

    with pytest.raises(StopAfterReconnect):
        await main_module.maintain_robot_connection(
            robot, object(), retry_delay=0, sleep=lambda delay: asyncio.sleep(0)
        )

    assert robot.connect_count == 2
    assert robot.close_count == 2
