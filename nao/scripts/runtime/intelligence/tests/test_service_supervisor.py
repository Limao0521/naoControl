from nao.scripts.runtime.intelligence.service_supervisor import NemotronServiceSupervisor


def test_service_supervisor_requires_every_deployed_service_pid():
    pids = {
        "/robot/run/naoControl/control.pid": "11",
        "/robot/run/naoControl/web.pid": "12",
        "/robot/run/naoControl/camera.pid": "13",
        "/robot/run/naoControl/intelligence.pid": "14",
    }
    supervisor = NemotronServiceSupervisor(
        base="/robot/naoControl", read_file=lambda path: pids[path],
        is_alive=lambda pid: pid in (11, 12, 13, 14),
    )

    assert supervisor.is_running() is True

    del pids["/robot/run/naoControl/intelligence.pid"]

    assert supervisor.is_running() is False


def test_service_supervisor_delegates_start_and_stop_to_deployed_scripts():
    calls = []
    supervisor = NemotronServiceSupervisor(
        base="/robot/naoControl", runner=lambda args: calls.append(args) or 0,
    )

    assert supervisor.start() is True
    assert supervisor.stop() is True
    assert calls == [
        ["sh", "/robot/naoControl/nao/scripts/runtime/start_nemotron.sh"],
        ["sh", "/robot/naoControl/nao/scripts/runtime/stop_nemotron.sh"],
    ]
