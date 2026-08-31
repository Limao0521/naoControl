#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Bounded latest-turn state shared by Nemotron and the local web control."""
from __future__ import absolute_import

import json
import os
import re
import time


DEFAULT_STATE_PATH = "/home/nao/run/naoControl/interaction_state.json"
ALLOWED_PHASES = set(("idle", "listening", "processing", "responding", "ready", "error"))
ALLOWED_ACTION_STATUSES = set(("pending", "accepted", "completed", "rejected", "failed", "unknown"))
IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]{0,64}$")

try:
    text_type = unicode
    binary_type = str
except NameError:
    text_type = str
    binary_type = bytes

replace_file = getattr(os, "replace", os.rename)


def _text(value, field, maximum):
    if isinstance(value, binary_type) and not isinstance(value, text_type):
        value = value.decode("utf-8")
    if not isinstance(value, text_type):
        raise ValueError("{} must be text".format(field))
    if len(value) > maximum:
        raise ValueError("{} is too long".format(field))
    return value


class InteractionStateStore(object):
    def __init__(self, path=DEFAULT_STATE_PATH, now_ms=None):
        self.path = path
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

    def _default(self):
        return {
            "interaction_id": "", "phase": "idle", "transcript": "",
            "response": "", "actions": [], "capture_finished_at_ms": 0,
            "response_started_at_ms": 0, "response_latency_ms": 0,
            "updated_at_ms": 0,
        }

    def _timestamp(self, value, field):
        if value is None:
            return 0
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("{} must be a timestamp".format(field))
        value = int(value)
        if value < 0 or value > 32503680000000:
            raise ValueError("{} is out of range".format(field))
        return value

    def _duration(self, value, field):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("{} must be a duration".format(field))
        value = int(value)
        if value < 0 or value > 86400000:
            raise ValueError("{} is out of range".format(field))
        return value

    def normalize(self, payload, previous=None, measure_latency=False):
        if not isinstance(payload, dict):
            raise ValueError("interaction state must be an object")
        interaction_id = _text(payload.get("interaction_id", ""), "interaction_id", 64)
        if not IDENTIFIER.match(interaction_id):
            raise ValueError("invalid interaction_id")
        phase = _text(payload.get("phase", ""), "phase", 16)
        if phase not in ALLOWED_PHASES:
            raise ValueError("invalid phase")
        transcript = _text(payload.get("transcript", ""), "transcript", 2000)
        response = _text(payload.get("response", ""), "response", 2000)
        raw_actions = payload.get("actions", [])
        if not isinstance(raw_actions, list) or len(raw_actions) > 16:
            raise ValueError("invalid actions")
        actions = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                raise ValueError("invalid action")
            name = _text(raw.get("name", ""), "action name", 64)
            if not IDENTIFIER.match(name):
                raise ValueError("invalid action name")
            status = _text(raw.get("status", "unknown"), "action status", 16)
            if status not in ALLOWED_ACTION_STATUSES:
                raise ValueError("invalid action status")
            reason = raw.get("reason")
            if reason is not None:
                reason = _text(reason, "action reason", 160)
            actions.append({"name": name, "status": status, "reason": reason})
        previous = previous or self._default()
        capture_finished_at_ms = self._timestamp(
            payload.get("capture_finished_at_ms", 0), "capture_finished_at_ms"
        )
        if not capture_finished_at_ms and previous.get("interaction_id") == interaction_id:
            capture_finished_at_ms = previous.get("capture_finished_at_ms", 0)
        now = self.now_ms()
        response_started_at_ms = self._timestamp(
            payload.get("response_started_at_ms", 0), "response_started_at_ms"
        )
        response_latency_ms = self._duration(
            payload.get("response_latency_ms", 0), "response_latency_ms"
        )
        if measure_latency and phase == "ready" and response and capture_finished_at_ms:
            response_started_at_ms = now
            response_latency_ms = max(0, now - capture_finished_at_ms)
        return {
            "interaction_id": interaction_id, "phase": phase,
            "transcript": transcript, "response": response,
            "actions": actions,
            "capture_finished_at_ms": capture_finished_at_ms,
            "response_started_at_ms": response_started_at_ms,
            "response_latency_ms": response_latency_ms,
            "updated_at_ms": now,
        }

    def save(self, payload):
        state = self.normalize(
            payload, previous=self.load(), measure_latency=True
        )
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        temporary = self.path + ".tmp"
        with open(temporary, "w") as output:
            json.dump(state, output, ensure_ascii=True, separators=(",", ":"))
        os.chmod(temporary, 0o600)
        replace_file(temporary, self.path)
        return state

    def load(self):
        try:
            with open(self.path, "r") as source:
                data = json.load(source)
            updated_at_ms = data.get("updated_at_ms", 0)
            normalized = self.normalize(data)
            normalized["updated_at_ms"] = updated_at_ms
            return normalized
        except (IOError, OSError, ValueError, TypeError):
            return self._default()
