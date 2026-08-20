# -*- coding: utf-8 -*-
"""Python-2-compatible lifecycle adapter for deployed NAO Control services."""
from __future__ import absolute_import

import os
import subprocess


class NemotronServiceSupervisor(object):
    SERVICE_NAMES = ("control", "web", "camera", "intelligence")

    def __init__(self, base="/home/nao/naoControl", runner=None,
                 read_file=None, is_alive=None):
        self.base = base
        self.pid_dir = os.path.join(os.path.dirname(base), "run", "naoControl")
        runtime = os.path.join(base, "nao", "scripts", "runtime")
        self.start_script = os.path.join(runtime, "start_nemotron.sh")
        self.stop_script = os.path.join(runtime, "stop_nemotron.sh")
        self.runner = runner or subprocess.call
        self.read_file = read_file or self._read_file
        self.is_alive = is_alive or self._is_alive

    def _read_file(self, path):
        with open(path, "r") as source:
            return source.read()

    def _is_alive(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def is_running(self):
        for name in self.SERVICE_NAMES:
            try:
                pid = int(self.read_file(os.path.join(self.pid_dir, name + ".pid")).strip())
            except (IOError, OSError, ValueError, KeyError):
                return False
            if not self.is_alive(pid):
                return False
        return True

    def start(self):
        return self.runner(["sh", self.start_script]) == 0

    def stop(self):
        return self.runner(["sh", self.stop_script]) == 0
