#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Read-only Nemotron observability commands for the local web UI."""
from __future__ import absolute_import

import json

from base_command import BaseCommand
from interaction_state import InteractionStateStore
from intelligence.provider_config import ProviderConfigError, ProviderConfigStore


DEFAULT_TARGET_PATH = "/home/nao/naoControl/config/pc_gateway_target.json"

try:
    STRING_TYPES = (basestring,)
except NameError:  # pragma: no cover - Python 3 tests
    STRING_TYPES = (str,)


class PcTargetStore(object):
    """Minimal read-only target store to keep web control gateway-independent."""

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

    def _send(self, websocket, action, payload):
        websocket.sendMessage(json.dumps({action: payload}, separators=(",", ":")))


class IntelligenceProviderStatusCommand(_ProviderCommand):
    ACTION = "intelligenceProviderStatus"

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        if not self._authorized(websocket):
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
        if not self._authorized(websocket):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
        if not isinstance(message, dict) or set(message) != {"action", "provider"}:
            self._send(websocket, self.ACTION, {
                "success": False, "error": "invalid_request",
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


class SetIntelligenceLanguageCommand(_ProviderCommand):
    ACTION = "setIntelligenceLanguage"
    TTS_LANGUAGES = {"es": "Spanish", "en": "English"}

    def get_action_name(self):
        return self.ACTION

    def execute(self, message, websocket):
        if not self._authorized(websocket):
            self._send(websocket, self.ACTION, {
                "success": False, "error": "forbidden",
            })
            return False
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
