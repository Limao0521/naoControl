# -*- coding: utf-8 -*-
"""Bounded push-to-talk recording using NAOqi's audio recorder."""
from __future__ import absolute_import

import base64
import os


class _Files(object):
    def read(self, path):
        with open(path, "rb") as audio_file:
            return audio_file.read()

    def remove(self, path):
        if os.path.exists(path):
            os.remove(path)


class AudioCapture(object):
    MAX_DURATION_MS = 20000
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, recorder, files=None, path="/tmp/nao_nemotron.wav"):
        self.recorder = recorder
        self.files = files or _Files()
        self.path = path
        self.interaction_id = None
        self.started_at_ms = None

    def start(self, interaction_id, now_ms):
        if self.interaction_id is not None:
            raise RuntimeError("audio capture already active")
        self.files.remove(self.path)
        self.recorder.startMicrophonesRecording(
            self.path, "wav", 16000, (1, 0, 0, 0)
        )
        self.interaction_id = interaction_id
        self.started_at_ms = now_ms

    def stop(self, now_ms):
        if self.interaction_id is None:
            raise RuntimeError("audio capture is not active")
        self.recorder.stopMicrophonesRecording()
        duration = min(now_ms - self.started_at_ms, self.MAX_DURATION_MS)
        audio = self.files.read(self.path)
        if len(audio) > self.MAX_BYTES:
            self.files.remove(self.path)
            self.interaction_id = None
            raise ValueError("audio payload exceeds limit")
        result = {
            "interaction_id": self.interaction_id,
            "duration_ms": duration,
            "audio_b64": base64.b64encode(audio).decode("ascii"),
        }
        self.files.remove(self.path)
        self.interaction_id = None
        self.started_at_ms = None
        return result

    def cancel(self):
        try:
            self.recorder.stopMicrophonesRecording()
        except Exception:
            pass
        self.files.remove(self.path)
        self.interaction_id = None
        self.started_at_ms = None
