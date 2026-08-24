#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Allowlisted network administration command for the control WebSocket."""
from __future__ import absolute_import

import json
import os
import sys

_commands_dir = os.path.dirname(os.path.abspath(__file__))
_control_dir = os.path.dirname(_commands_dir)
_runtime_dir = os.path.dirname(_control_dir)
for _path in (_control_dir, _runtime_dir):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from base_command import BaseCommand
from message_security import valid_request_id
from network_admin import NetworkAdminError, _redact


ACTION = "networkAdmin"
ALLOWED_MESSAGE_FIELDS = frozenset((
    "action", "request_id", "operation", "service_id", "ssid", "passphrase",
))
SERVICE_FIELDS = ("operation", "service_id", "ssid", "passphrase")


class NetworkAdminCommand(BaseCommand):
    def __init__(self, nao_facade, logger, network_service=None):
        BaseCommand.__init__(self, nao_facade, logger)
        self.network_service = network_service

    def get_action_name(self):
        return ACTION

    def _send(self, websocket, request_id, result):
        response = {
            "request_id": request_id,
            "status": result.get("status", "failed"),
            "operation": result.get("operation", "unknown"),
            "data": _redact(result.get("data", {})),
        }
        if result.get("reason"):
            response["reason"] = result["reason"]
        websocket.sendMessage(json.dumps({ACTION: response}, separators=(",", ":")))

    def execute(self, message, websocket):
        request_id = message.get("request_id") if isinstance(message, dict) else None
        safe_request_id = request_id if valid_request_id(request_id) else "invalid"
        operation = message.get("operation", "unknown") if isinstance(message, dict) else "unknown"

        if (
            not isinstance(message, dict)
            or set(message) - ALLOWED_MESSAGE_FIELDS
            or message.get("action") != ACTION
            or not valid_request_id(request_id)
        ):
            self._send(websocket, safe_request_id, {
                "status": "rejected", "operation": "unknown", "data": {},
                "reason": "invalid_request",
            })
            self.logger.warning("networkAdmin rejected invalid request metadata")
            return False

        if self.network_service is None:
            self._send(websocket, safe_request_id, {
                "status": "failed", "operation": operation, "data": {},
                "reason": "unavailable",
            })
            self.logger.warning("networkAdmin service unavailable")
            return False

        request = dict(
            (field, message[field]) for field in SERVICE_FIELDS if field in message
        )
        try:
            result = self.network_service.execute(request)
        except NetworkAdminError:
            result = {
                "status": "rejected", "operation": "unknown", "data": {},
                "reason": "invalid_request",
            }
        except Exception:
            result = {
                "status": "failed", "operation": operation, "data": {},
                "reason": "operation_failed",
            }

        self._send(websocket, safe_request_id, result)
        completed = result.get("status") == "completed"
        if completed:
            self.logger.info("networkAdmin operation completed: {}".format(operation))
        else:
            self.logger.warning("networkAdmin operation ended: {}".format(
                result.get("status", "failed")
            ))
        return completed
