# -*- coding: utf-8 -*-
"""Serialize intelligent-mode indicators and temporary model LED actions."""
from __future__ import absolute_import

import threading


MODE_COLORS = {
    "WEB_CONTROL": (1.0, 1.0, 1.0),
    "NEMOTRON_READY": (0.0, 0.0, 1.0),
    "CAPTURING": (0.0, 1.0, 0.0),
    "PROCESSING": (1.0, 0.5, 0.0),
    "RESPONDING": (1.0, 0.5, 0.0),
    "ERROR": (1.0, 0.0, 0.0),
    "EMERGENCY": (1.0, 0.0, 0.0),
}


def _timer_factory(delay, callback):
    timer = threading.Timer(delay, callback)
    timer.daemon = True
    return timer


class IntelligenceLedController(object):
    FACE_OVERRIDE_SECONDS = 3.0

    def __init__(self, facade, timer_factory=None):
        self.facade = facade
        self.timer_factory = timer_factory or _timer_factory
        self.mode = "WEB_CONTROL"
        self._timer = None
        self._generation = 0
        self._lock = threading.RLock()

    def _cancel_override_locked(self):
        self._generation += 1
        timer = self._timer
        self._timer = None
        if timer is not None:
            timer.cancel()

    def _write_mode_locked(self):
        color = MODE_COLORS.get(self.mode, MODE_COLORS["NEMOTRON_READY"])
        return self.facade.set_led_rgb(
            "FaceLeds", color[0], color[1], color[2], 0.3
        )

    def set_mode(self, mode, preserve_override=False):
        with self._lock:
            self.mode = str(mode)
            if preserve_override and self._timer is not None:
                return True
            self._cancel_override_locked()
            return self._write_mode_locked()

    def _restore(self, generation):
        with self._lock:
            if generation != self._generation:
                return
            self._timer = None
            self._write_mode_locked()

    def show_action(self, group, red, green, blue, duration=0.3):
        group = str(group)
        if group != "FaceLeds":
            return self.facade.set_led_rgb(
                group, red, green, blue, duration
            )
        with self._lock:
            self._cancel_override_locked()
            result = self.facade.set_led_rgb(
                group, red, green, blue, duration
            )
            if result is False:
                return False
            generation = self._generation
            timer = self.timer_factory(
                self.FACE_OVERRIDE_SECONDS,
                lambda: self._restore(generation),
            )
            self._timer = timer
            timer.start()
            return result
