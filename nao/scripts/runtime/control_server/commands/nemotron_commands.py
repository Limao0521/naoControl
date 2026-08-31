#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Read-only Nemotron observability commands for the local web UI."""
from __future__ import absolute_import

import json
import os
import socket

from base_command import BaseCommand
from interaction_state import InteractionStateStore
from intelligence.provider_config import (
    ALLOWED_LANGUAGES,
    ALLOWED_PROVIDERS,
    ProviderConfigError,
    ProviderConfigStore,
)


DEFAULT_TARGET_PATH = "/home/nao/naoControl/config/pc_gateway_target.json"

try:
    STRING_TYPES = (basestring,)
except NameError:  # pragma: no cover - Python 3 tests
    STRING_TYPES = (str,)


class PcTargetStore(object):
    """Persist the gateway PC inferred from the web client's network peer."""

    def __init__(self, path=DEFAULT_TARGET_PATH):
        self.path = path

    def load(self):
        try:
            with open(self.path, "rb") as source:
                data = json.loads(source.read().decode("utf-8"))
            pc_ip = data.get("pc_ip", "") if isinstance(data, dict) else ""
            return {"pc_ip": pc_ip if isinstance(pc_ip, STRING_TYPES) else ""}
        except (IOError, OSError, TypeError, ValueError):
            return {"pc_ip": ""}

    def save(self, pc_ip):
        if not _private_peer_ip(pc_ip):
            raise ValueError("invalid PC target")
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        temporary = self.path + ".tmp"
        with open(temporary, "wb") as target:
            target.write(json.dumps(
                {"pc_ip": pc_ip}, separators=(",", ":")
            ).encode("utf-8"))
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        replace = getattr(os, "replace", os.rename)
        replace(temporary, self.path)
        return {"pc_ip": pc_ip}


def _peer_ip(websocket):
    """Read the peer from the accepted socket, not a library-specific wrapper."""
    try:
        address = websocket.client.getpeername()
    except (AttributeError, IOError, OSError):
        address = getattr(websocket, "address", None)
    if isinstance(address, (tuple, list)) and address:
        address = address[0]
    if not isinstance(address, STRING_TYPES):
        return ""
    if address.lower().startswith("::ffff:"):
        return address[7:]
    return address


def _private_peer_ip(value):
    """Accept RFC1918 and link-local IPv4 peers used by the robot control LAN."""
    if not isinstance(value, STRING_TYPES):
        return False
    try:
        packed = socket.inet_aton(value)
        if socket.inet_ntoa(packed) != value:
            return False
        parts = [int(part) for part in value.split(".")]
        return (
            parts[0] == 10
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
            or (parts[0] == 192 and parts[1] == 168)
            or (parts[0] == 169 and parts[1] == 254)
        )
    except (ValueError, socket.error):
        return False


class NemotronStatusCommand(BaseCommand):
    def __init__(self, nao_facade, logger, state_store=None, target_store=None):
        BaseCommand.__init__(self, nao_facade, logger)
        self.state_store = state_store or InteractionStateStore()
        self.target_store = target_store or PcTargetStore()

    def get_action_name(self):
        return "nemotronStatus"

    def execute(self, message, websocket):
        try:
            configured_pc = self.target_store.load().get("pc_ip", "")
            peer_ip = _peer_ip(websocket)
            if not configured_pc or peer_ip != configured_pc:
                self.logger.warning(
                    "nemotronStatus denied for peer {}".format(peer_ip or "unknown")
                )
                websocket.sendMessage(json.dumps({
                    "nemotronStatus": {"success": False, "error": "forbidden"}
                }))
                return False
            response = {"success": True}
            response.update(self.state_store.load())
            websocket.sendMessage(json.dumps({"nemotronStatus": response}))
            return True
        except Exception as error:
            self.logger.error("nemotronStatus failed: {}".format(error))
            websocket.sendMessage(json.dumps({
                "nemotronStatus": {"success": False, "error": "status_unavailable"}
            }))
            return False


class _ProviderCommand(BaseCommand):
    def __init__(self, nao_facade, logger, provider_store=None, target_store=None):
        BaseCommand.__init__(self, nao_facade, logger)
        self.provider_store = provider_store or ProviderConfigStore()
        self.target_store = target_store or PcTargetStore()

    def _authorized(self, websocket):
        configured_pc = self.target_store.load().get("pc_ip", "")
        return bool(configured_pc and _peer_ip(websocket) == configured_pc)

    def _bind_requesting_pc(self, websocket):
        """Use the private browser peer as the gateway target for this session."""
        peer_ip = _peer_ip(websocket)
        if not _private_peer_ip(peer_ip):
            return False
        try:
            self.target_store.save(peer_ip)
            return True
        except (IOError, OSError, TypeError, ValueError):
            return False

    def _send(self, websocket, action, payload):
        websocket.sendMessage(json.dumps({action: payload}, separators=(",", ":")))


class IntelligenceProviderStatusCommand(_ProviderCommand):
    ACTION = "intelligenceProviderStatus"

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        if not _private_peer_ip(_peer_ip(websocket)):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
        state = self.provider_store.load()
        state["success"] = True
        self._send(websocket, self.ACTION, state)
        return True


class SetIntelligenceProviderCommand(_ProviderCommand):
    ACTION = "setIntelligenceProvider"

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        if not isinstance(message, dict) or set(message) != {"action", "provider"}:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        if message.get("provider") not in ALLOWED_PROVIDERS:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "unsupported_provider",
            })
            return False
        if not self._bind_requesting_pc(websocket):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
        try:
            state = self.provider_store.save_selected(message.get("provider"))
        except ProviderConfigError:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "unsupported_provider",
            })
            return False
        state["success"] = True
        self._send(websocket, self.ACTION, state)
        return True


class SetGemmaEndpointCommand(_ProviderCommand):
    """Store a non-secret private-LAN Gemma endpoint for the PC gateway."""
    ACTION = "setGemmaEndpoint"

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        if not isinstance(message, dict) or set(message) != {
            "action", "gemma_ip"
        }:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        gemma_ip = message.get("gemma_ip")
        if not _private_peer_ip(gemma_ip):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_gemma_endpoint",
            })
            return False
        if not self._bind_requesting_pc(websocket):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
        try:
            state = self.provider_store.save_gemma_base_url(
                "http://{}:8080/v1".format(gemma_ip)
            )
        except ProviderConfigError:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_gemma_endpoint",
            })
            return False
        state["success"] = True
        self._send(websocket, self.ACTION, state)
        return True


class SetIntelligenceLanguageCommand(_ProviderCommand):
    ACTION = "setIntelligenceLanguage"
    TTS_LANGUAGES = {"es": "Spanish", "en": "English"}

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        if not isinstance(message, dict) or set(message) != {"action", "language"}:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        language = message.get("language")
        tts_language = self.TTS_LANGUAGES.get(language)
        if tts_language is None:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "unsupported_language",
            })
            return False
        if not self._bind_requesting_pc(websocket):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
        if not self.nao.set_language(tts_language):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "tts_language_failed",
            })
            return False
        try:
            state = self.provider_store.save_language(language)
        except ProviderConfigError:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "unsupported_language",
            })
            return False
        state["success"] = True
        self._send(websocket, self.ACTION, state)
        return True


class ConfigureIntelligenceCommand(_ProviderCommand):
    """Apply provider, model LAN endpoint, and response language together."""
    ACTION = "configureIntelligence"
    TTS_LANGUAGES = {"es": "Spanish", "en": "English"}

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        expected = set(("action", "provider", "language"))
        if not isinstance(message, dict) or set(message) not in (
                expected, expected | set(("gemma_ip",))):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        selected = message.get("provider")
        language = message.get("language")
        gemma_ip = message.get("gemma_ip")
        if selected not in ALLOWED_PROVIDERS or language not in ALLOWED_LANGUAGES:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        if selected == "gemma_local" and not _private_peer_ip(gemma_ip):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_gemma_endpoint",
            })
            return False
        if selected == "nemotron" and gemma_ip:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        if not self._bind_requesting_pc(websocket):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
        endpoint = None
        if selected == "gemma_local":
            endpoint = "http://{}:8080/v1".format(gemma_ip)
        if not self.nao.set_language(self.TTS_LANGUAGES[language]):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "tts_language_failed",
            })
            return False
        try:
            state = self.provider_store.save_configuration(selected, language, endpoint)
        except ProviderConfigError:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
            })
            return False
        state["success"] = True
        self._send(websocket, self.ACTION, state)
        return True
