# -*- coding: utf-8 -*-
"""Deterministic physical-mode state machine without NAOqi dependencies."""
from __future__ import absolute_import


WEB_CONTROL = "WEB_CONTROL"
NEMOTRON_READY = "NEMOTRON_READY"
CAPTURING = "CAPTURING"
PROCESSING = "PROCESSING"
ACTING = "ACTING"
SPEAKING = "SPEAKING"
EMERGENCY = "EMERGENCY"


class ModeEvent(object):
    def __init__(self, name, occurred_at_ms, previous_mode, mode):
        self.name = name
        self.occurred_at_ms = occurred_at_ms
        self.previous_mode = previous_mode
        self.mode = mode

    def as_dict(self):
        return {
            "name": self.name,
            "occurred_at_ms": self.occurred_at_ms,
            "previous_mode": self.previous_mode,
            "mode": self.mode,
        }


class ModeManager(object):
    HOLD_MS = 1500

    def __init__(self, initial_mode=WEB_CONTROL, entry_check=None):
        self.mode = initial_mode
        self.entry_check = entry_check or (lambda: True)
        self._left_started_ms = None
        self._left_consumed = False
        self._right_pressed = False
        self._both_pressed = False

    def _transition(self, name, next_mode, now_ms):
        previous = self.mode
        self.mode = next_mode
        return ModeEvent(name, now_ms, previous, next_mode)

    def handle_bumper(self, left, right, now_ms):
        left = bool(left)
        right = bool(right)

        if left and right:
            self._left_started_ms = None
            self._right_pressed = right
            if not self._both_pressed:
                self._both_pressed = True
                return [self._transition("EMERGENCY_REQUESTED", EMERGENCY, now_ms)]
            return []
        self._both_pressed = False

        if not left:
            self._left_started_ms = None
            self._left_consumed = False
        elif not self._left_consumed:
            if self._left_started_ms is None:
                self._left_started_ms = now_ms
            elif now_ms - self._left_started_ms >= self.HOLD_MS:
                self._left_consumed = True
                if self.mode == WEB_CONTROL:
                    try:
                        allowed = bool(self.entry_check())
                    except Exception:
                        allowed = False
                    if not allowed:
                        return [self._transition("MODE_ENTRY_REJECTED", WEB_CONTROL, now_ms)]
                    return [self._transition("MODE_ENTER_REQUESTED", NEMOTRON_READY, now_ms)]
                return [self._transition("MODE_EXIT_REQUESTED", WEB_CONTROL, now_ms)]

        if right and not self._right_pressed and self.mode == NEMOTRON_READY:
            self._right_pressed = True
            return [self._transition("CAPTURE_STARTED", CAPTURING, now_ms)]
        if not right and self._right_pressed:
            self._right_pressed = False
            if self.mode == CAPTURING:
                return [self._transition("CAPTURE_FINISHED", PROCESSING, now_ms)]
        else:
            self._right_pressed = right
        return []

    def handle_system(self, event_name, now_ms):
        transitions = {
            "ACTING_STARTED": ("ACTING_STARTED", ACTING),
            "SPEAKING_STARTED": ("SPEAKING_STARTED", SPEAKING),
            "TURN_FINISHED": ("TURN_FINISHED", NEMOTRON_READY),
            "INTERACTION_CANCELLED": ("INTERACTION_CANCELLED", NEMOTRON_READY),
            "MODE_EXIT_REQUESTED": ("MODE_EXIT_REQUESTED", WEB_CONTROL),
            "EMERGENCY_RESET": ("EMERGENCY_RESET", WEB_CONTROL),
        }
        transition = transitions.get(event_name)
        if transition is None:
            return []
        return [self._transition(transition[0], transition[1], now_ms)]
