#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Read-only Nemotron observability commands for the local web UI."""
from __future__ import absolute_import

import json

from base_command import BaseCommand
from interaction_state import InteractionStateStore


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
