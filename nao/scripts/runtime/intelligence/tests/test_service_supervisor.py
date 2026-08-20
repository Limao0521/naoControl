from nao.scripts.runtime.intelligence.service_supervisor import NemotronServiceSupervisor
from nao.scripts.runtime import launcher


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


def test_launcher_delegates_the_touch_transition_to_deployed_supervisor():
    class FakeSupervisor(object):
        def __init__(self):
            self.running = False
            self.calls = []

        def is_running(self):
            return self.running

        def start(self):
            self.calls.append("start")
            self.running = True
            return True

        def stop(self):
            self.calls.append("stop")
            self.running = False
            return True

    target = launcher.RobustLauncher.__new__(launcher.RobustLauncher)
    target.service_supervisor = FakeSupervisor()
    target.services_running = False

    assert target.start_services() is True
    assert target.services_running is True
    assert target.stop_services() is True
    assert target.service_supervisor.calls == ["start", "stop"]


def test_launcher_declares_naoqi_site_packages_for_standalone_execution():
    assert launcher.NAOQI_SITE_PACKAGES == "/opt/aldebaran/lib/python2.7/site-packages"
