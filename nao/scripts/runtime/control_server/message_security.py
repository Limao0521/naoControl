#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Bounded metadata logging for untrusted WebSocket messages."""
from __future__ import absolute_import

import re

try:
    basestring
except NameError:  # pragma: no cover - Python 3 test runtime
    basestring = str


_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_token(value, maximum):
    if not isinstance(value, basestring):
        return "invalid"
    if not value or len(value) > maximum or not _TOKEN_PATTERN.match(value):
        return "invalid"
    return value


def safe_message_summary(message):
    """Return only bounded non-sensitive routing metadata."""
    if not isinstance(message, dict):
        return "action=invalid operation=invalid request_id=invalid"
    return "action={} operation={} request_id={}".format(
        _safe_token(message.get("action"), 64),
        _safe_token(message.get("operation"), 32),
        _safe_token(message.get("request_id"), 64),
    )


def valid_request_id(value):
    return _safe_token(value, 64) != "invalid"
