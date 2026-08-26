# -*- coding: utf-8 -*-
"""Persist and publish the non-secret intelligent provider identifier."""
from __future__ import absolute_import

import json
import os
import time


ALLOWED_PROVIDERS = ("nemotron", "gemma_local")
DEFAULT_PATH = "/home/nao/naoControl/config/intelligence_provider.json"

try:
    STRING_TYPES = (basestring,)
except NameError:  # pragma: no cover - Python 3 tests
    STRING_TYPES = (str,)


class ProviderConfigError(ValueError):
    pass


class ProviderConfigStore(object):
    def __init__(self, path=DEFAULT_PATH, now_ms=None):
        self.path = path
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

    def _default(self):
        return {
            "selected": "nemotron",
            "active": "",
            "healthy": False,
            "error": "",
            "selection_version": 0,
            "updated_at_ms": 0,
        }

    def _valid(self, data):
        if not isinstance(data, dict):
            return False
        if set(data) != set(self._default()):
            return False
        return (
            data.get("selected") in ALLOWED_PROVIDERS
            and data.get("active") in ("",) + ALLOWED_PROVIDERS
            and isinstance(data.get("healthy"), bool)
            and isinstance(data.get("error"), STRING_TYPES)
            and len(data.get("error")) <= 200
            and isinstance(data.get("selection_version"), int)
            and not isinstance(data.get("selection_version"), bool)
            and data.get("selection_version") >= 0
            and isinstance(data.get("updated_at_ms"), (int, float))
        )

    def load(self):
        try:
            with open(self.path, "rb") as source:
                raw = source.read().decode("utf-8")
            data = json.loads(raw)
            if self._valid(data):
                return dict(data)
        except (IOError, OSError, TypeError, ValueError, UnicodeError):
            pass
        return self._default()

    def _save(self, data):
        if not self._valid(data):
            raise ProviderConfigError("invalid provider state")
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        temporary = self.path + ".tmp"
        with open(temporary, "wb") as output:
            output.write(json.dumps(
                data, separators=(",", ":"), sort_keys=True
            ).encode("utf-8"))
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        replace = getattr(os, "replace", os.rename)
        replace(temporary, self.path)
        return dict(data)

    def save_selected(self, selected):
        if selected not in ALLOWED_PROVIDERS:
            raise ProviderConfigError("unsupported provider")
        data = self.load()
        data["selected"] = selected
        data["selection_version"] += 1
        data["updated_at_ms"] = self.now_ms()
        return self._save(data)

    def save_status(self, status):
        if not isinstance(status, dict) or set(status) != {
            "active", "healthy", "error"
        }:
            raise ProviderConfigError("invalid provider status")
        active = status.get("active")
        healthy = status.get("healthy")
        error = status.get("error")
        if (
            active not in ("",) + ALLOWED_PROVIDERS
            or not isinstance(healthy, bool)
            or not isinstance(error, STRING_TYPES)
            or len(error) > 200
        ):
            raise ProviderConfigError("invalid provider status")
        data = self.load()
        data.update({
            "active": active,
            "healthy": healthy,
            "error": error,
            "updated_at_ms": self.now_ms(),
        })
        return self._save(data)


class ProviderConfigBroadcaster(object):
    def __init__(self, store, send_all):
        self.store = store
        self.send_all = send_all
        self.last_selection = None

    def sync(self, force=False):
        state = self.store.load()
        selected = state["selected"]
        selection = (selected, state["selection_version"])
        if not force and selection == self.last_selection:
            return False
        self.last_selection = selection
        self.send_all("provider_config", {"selected": selected})
        return True
