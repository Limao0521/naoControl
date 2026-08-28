# -*- coding: utf-8 -*-
"""Persist and publish the non-secret intelligent provider identifier."""
from __future__ import absolute_import

import json
import os
import socket
import time
try:
    from urlparse import urlparse
except ImportError:  # pragma: no cover - Python 3 tests
    from urllib.parse import urlparse


ALLOWED_PROVIDERS = ("nemotron", "gemma_local")
ALLOWED_LANGUAGES = ("es", "en")
DEFAULT_PATH = "/home/nao/naoControl/config/intelligence_provider.json"
MAX_GEMMA_ENDPOINT_LENGTH = 120

try:
    STRING_TYPES = (basestring,)
except NameError:  # pragma: no cover - Python 3 tests
    STRING_TYPES = (str,)


class ProviderConfigError(ValueError):
    pass


def valid_gemma_base_url(value):
    """Allow only a private, credential-free OpenAI-compatible LAN endpoint."""
    if not isinstance(value, STRING_TYPES) or len(value) > MAX_GEMMA_ENDPOINT_LENGTH:
        return False
    if not value:
        return True
    try:
        parsed = urlparse(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or
                parsed.username is not None or parsed.password is not None or
                parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/v1"):
            return False
        host = parsed.hostname
        packed = socket.inet_aton(host)
        if socket.inet_ntoa(packed) != host:
            return False
        parts = [int(part) for part in host.split(".")]
        if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
            return False
        private = (parts[0] == 10 or
                   (parts[0] == 172 and 16 <= parts[1] <= 31) or
                   (parts[0] == 192 and parts[1] == 168))
        port = parsed.port
        return private and (port is None or 1 <= port <= 65535)
    except (AttributeError, TypeError, ValueError, socket.error):
        return False


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
            "language": "es",
            "language_version": 0,
            "gemma_base_url": "",
            "gemma_endpoint_version": 0,
            "updated_at_ms": 0,
        }

    def _migrate(self, data):
        if not isinstance(data, dict):
            return data
        defaults = self._default()
        if not set(data).issubset(set(defaults)):
            return data
        migrated = dict(data)
        for key, value in defaults.items():
            if key not in migrated:
                migrated[key] = value
        return migrated

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
            and data.get("language") in ALLOWED_LANGUAGES
            and isinstance(data.get("language_version"), int)
            and not isinstance(data.get("language_version"), bool)
            and data.get("language_version") >= 0
            and valid_gemma_base_url(data.get("gemma_base_url"))
            and isinstance(data.get("gemma_endpoint_version"), int)
            and not isinstance(data.get("gemma_endpoint_version"), bool)
            and data.get("gemma_endpoint_version") >= 0
            and isinstance(data.get("updated_at_ms"), (int, float))
        )

    def load(self):
        try:
            with open(self.path, "rb") as source:
                raw = source.read().decode("utf-8")
            data = self._migrate(json.loads(raw))
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

    def save_language(self, language):
        if language not in ALLOWED_LANGUAGES:
            raise ProviderConfigError("unsupported language")
        data = self.load()
        data["language"] = language
        data["language_version"] += 1
        data["updated_at_ms"] = self.now_ms()
        return self._save(data)

    def save_gemma_base_url(self, gemma_base_url):
        if not valid_gemma_base_url(gemma_base_url):
            raise ProviderConfigError("invalid Gemma endpoint")
        data = self.load()
        data["gemma_base_url"] = gemma_base_url.rstrip("/")
        data["gemma_endpoint_version"] += 1
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
        language = state["language"]
        selection = (
            selected, state["selection_version"],
            language, state["language_version"],
            state["gemma_base_url"], state["gemma_endpoint_version"],
        )
        if not force and selection == self.last_selection:
            return False
        self.last_selection = selection
        self.send_all("provider_config", {
            "selected": selected, "language": language,
            "gemma_base_url": state["gemma_base_url"],
        })
        return True
