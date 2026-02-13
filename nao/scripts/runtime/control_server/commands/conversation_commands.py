#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
conversation_commands.py - Conversation system commands

Implements commands to start/stop/query the LLM conversation system
(Whisper STT + Groq LLM + NAO TTS) via WebSocket actions.

Actions:
    startConversation  - Start a conversation session (runs in background thread)
    stopConversation   - Stop the active conversation session
    getConversationStatus - Get current conversation status
"""

from __future__ import print_function
import sys
import os
import json
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand

# Path to nao_conversation module (runtime directory)
_runtime_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _runtime_dir not in sys.path:
    sys.path.insert(0, _runtime_dir)


class ConversationManager(object):
    """
    Singleton manager for the conversation system.
    Handles lifecycle of NaoConversationWhisper in a background thread.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConversationManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.conversation = None
        self.thread = None
        self.is_running = False
        self.start_time = None
        self.error = None
        self.logger = None

    def start(self, nao_ip, nao_port, provider, logger):
        """
        Start conversation in a background thread.

        Args:
            nao_ip: NAO robot IP
            nao_port: NAOqi port
            provider: LLM provider name ('groq', 'gemini', etc.)
            logger: Logger instance

        Returns:
            bool: True if started, False if already running or error
        """
        self.logger = logger

        if self.is_running:
            logger.warning("Conversation already running")
            return False

        self.error = None

        try:
            from nao_conversation import NaoConversationWhisper

            self.conversation = NaoConversationWhisper(
                nao_ip=nao_ip,
                nao_port=nao_port,
                provider=provider
            )

            self.is_running = True
            self.start_time = time.time()

            self.thread = threading.Thread(target=self._run_conversation)
            self.thread.daemon = True
            self.thread.start()

            logger.info("Conversation started in background thread")
            return True

        except Exception as e:
            logger.error("Failed to start conversation: {}".format(e))
            self.error = str(e)
            self.is_running = False
            return False

    def _run_conversation(self):
        """Run conversation loop in background thread."""
        try:
            if self.conversation:
                self.conversation.run()
        except Exception as e:
            if self.logger:
                self.logger.error("Conversation thread error: {}".format(e))
            self.error = str(e)
        finally:
            self.is_running = False
            self.start_time = None
            if self.logger:
                self.logger.info("Conversation thread finished")

    def stop(self):
        """Stop the active conversation."""
        if not self.is_running:
            return False

        if self.conversation:
            self.conversation.conversation_active = False

        # Wait for thread to finish (max 3 seconds)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

        self.is_running = False
        self.start_time = None
        self.conversation = None
        self.thread = None

        if self.logger:
            self.logger.info("Conversation stopped")

        return True

    def get_status(self):
        """Get current conversation status."""
        status = {
            "is_running": self.is_running,
            "error": self.error,
        }
        if self.is_running and self.start_time:
            status["elapsed_seconds"] = int(time.time() - self.start_time)
        if self.conversation:
            status["provider"] = self.conversation.provider_name
            status["whisper_available"] = self.conversation.whisper is not None
        return status


# Global conversation manager instance
_conversation_manager = ConversationManager()


class StartConversationCommand(BaseCommand):
    """Command to start a conversation session."""

    def execute(self, message, websocket):
        """Start conversation in background thread."""
        action = self.get_action_name()

        try:
            # Optional parameters from message
            provider = message.get("provider", "groq")

            # Get NAO connection info from facade
            nao_ip = self.nao.nao_ip if hasattr(self.nao, 'nao_ip') else "127.0.0.1"
            nao_port = self.nao.nao_port if hasattr(self.nao, 'nao_port') else 9559

            success = _conversation_manager.start(nao_ip, nao_port, provider, self.logger)

            if success:
                self.send_success_response(websocket, action, {
                    "message": "Conversation started",
                    "provider": provider
                })
            else:
                status = _conversation_manager.get_status()
                if status["is_running"]:
                    self.send_error_response(websocket, action,
                        "Conversation is already running",
                        {"status": status})
                else:
                    self.send_error_response(websocket, action,
                        "Failed to start conversation: {}".format(
                            status.get("error", "Unknown error")))

            return success

        except Exception as e:
            self.send_error_response(websocket, action, str(e))
            return False

    def get_action_name(self):
        return "startConversation"


class StopConversationCommand(BaseCommand):
    """Command to stop the active conversation session."""

    def execute(self, message, websocket):
        """Stop the conversation."""
        action = self.get_action_name()

        try:
            success = _conversation_manager.stop()

            if success:
                self.send_success_response(websocket, action, {
                    "message": "Conversation stopped"
                })
            else:
                self.send_error_response(websocket, action,
                    "No conversation is currently running")

            return success

        except Exception as e:
            self.send_error_response(websocket, action, str(e))
            return False

    def get_action_name(self):
        return "stopConversation"


class GetConversationStatusCommand(BaseCommand):
    """Command to get conversation status."""

    def execute(self, message, websocket):
        """Return conversation status."""
        action = self.get_action_name()

        try:
            status = _conversation_manager.get_status()
            self.send_success_response(websocket, action, {"status": status})
            return True

        except Exception as e:
            self.send_error_response(websocket, action, str(e))
            return False

    def get_action_name(self):
        return "getConversationStatus"
