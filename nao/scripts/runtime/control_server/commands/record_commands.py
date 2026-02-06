#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
record_commands.py - Comandos de sistema de grabación

Implementa comandos para controlar el sistema de grabación de movimientos
usando bumper del pie usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class RecordModeCommand(BaseCommand):
    """Comando para alternar modo de grabación."""
    
    def __init__(self, nao_facade, logger, record_system_funcs=None):
        """
        Inicializar comando con funciones del sistema de grabación.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            record_system_funcs: Dict con funciones toggle_record_mode, get_record_status
        """
        super(RecordModeCommand, self).__init__(nao_facade, logger)
        self.record_funcs = record_system_funcs or {}
    
    def execute(self, message, websocket):
        """Ejecutar comando recordMode."""
        try:
            toggle_func = self.record_funcs.get("toggle")
            status_func = self.record_funcs.get("status")
            
            if not toggle_func or not status_func:
                websocket.sendMessage(json.dumps({
                    "recordMode": {
                        "success": False,
                        "error": "Sistema de grabación no disponible"
                    }
                }))
                return False
            
            # Alternar modo de grabación
            success = toggle_func()
            status = status_func()
            
            response = {
                "recordMode": {
                    "success": success,
                    "mode_active": status.get("mode_active", False),
                    "recording": status.get("recording", False),
                    "current_file": status.get("current_file"),
                    "recordings_dir": status.get("recordings_dir"),
                    "help": "Presione bumper derecho del pie para grabar (mantener presionado)"
                }
            }
            websocket.sendMessage(json.dumps(response))
            
            mode_str = "ACTIVADO" if status.get("mode_active") else "DESACTIVADO"
            self.logger.info("RecordMode: Modo de grabación {} - Recording: {}".format(
                mode_str, status.get("recording")))
            
            return success
            
        except Exception as e:
            self.logger.error("Error controlando modo grabación: {}".format(e))
            websocket.sendMessage(json.dumps({
                "recordMode": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "recordMode"


class GetRecordStatusCommand(BaseCommand):
    """Comando para obtener estado del sistema de grabación."""
    
    def __init__(self, nao_facade, logger, record_system_funcs=None, available=False):
        super(GetRecordStatusCommand, self).__init__(nao_facade, logger)
        self.record_funcs = record_system_funcs or {}
        self.available = available
    
    def execute(self, message, websocket):
        """Ejecutar comando getRecordStatus."""
        try:
            status_func = self.record_funcs.get("status")
            
            if not status_func or not self.available:
                websocket.sendMessage(json.dumps({
                    "getRecordStatus": {
                        "available": False,
                        "error": "Sistema de grabación no disponible"
                    }
                }))
                return False
            
            status = status_func()
            
            response = {
                "getRecordStatus": {
                    "available": True,
                    "mode_active": status.get("mode_active", False),
                    "recording": status.get("recording", False),
                    "current_file": status.get("current_file"),
                    "recordings_dir": status.get("recordings_dir")
                }
            }
            websocket.sendMessage(json.dumps(response))
            return True
            
        except Exception as e:
            self.logger.error("Error obteniendo estado grabación: {}".format(e))
            websocket.sendMessage(json.dumps({
                "getRecordStatus": {"available": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "getRecordStatus"


class StartRecordingCommand(BaseCommand):
    """Comando para iniciar grabación manualmente."""
    
    def __init__(self, nao_facade, logger, record_system_funcs=None):
        super(StartRecordingCommand, self).__init__(nao_facade, logger)
        self.record_funcs = record_system_funcs or {}
    
    def execute(self, message, websocket):
        """Ejecutar comando startRecording."""
        try:
            start_func = self.record_funcs.get("start")
            
            if not start_func:
                websocket.sendMessage(json.dumps({
                    "startRecording": {
                        "success": False,
                        "error": "Sistema de grabación no disponible"
                    }
                }))
                return False
            
            filename = message.get("filename", None)
            success = start_func(filename)
            
            status_func = self.record_funcs.get("status")
            status = status_func() if status_func else {}
            
            response = {
                "startRecording": {
                    "success": success,
                    "recording": status.get("recording", False),
                    "current_file": status.get("current_file")
                }
            }
            websocket.sendMessage(json.dumps(response))
            
            if success:
                self.logger.info("Recording iniciado: {}".format(status.get("current_file")))
            
            return success
            
        except Exception as e:
            self.logger.error("Error iniciando grabación: {}".format(e))
            websocket.sendMessage(json.dumps({
                "startRecording": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "startRecording"


class StopRecordingCommand(BaseCommand):
    """Comando para detener grabación manualmente."""
    
    def __init__(self, nao_facade, logger, record_system_funcs=None):
        super(StopRecordingCommand, self).__init__(nao_facade, logger)
        self.record_funcs = record_system_funcs or {}
    
    def execute(self, message, websocket):
        """Ejecutar comando stopRecording."""
        try:
            stop_func = self.record_funcs.get("stop")
            
            if not stop_func:
                websocket.sendMessage(json.dumps({
                    "stopRecording": {
                        "success": False,
                        "error": "Sistema de grabación no disponible"
                    }
                }))
                return False
            
            result = stop_func()
            
            response = {
                "stopRecording": {
                    "success": True,
                    "file": result.get("file") if isinstance(result, dict) else None,
                    "samples": result.get("samples", 0) if isinstance(result, dict) else 0
                }
            }
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Recording detenido")
            return True
            
        except Exception as e:
            self.logger.error("Error deteniendo grabación: {}".format(e))
            websocket.sendMessage(json.dumps({
                "stopRecording": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "stopRecording"


class ListRecordingsCommand(BaseCommand):
    """Comando para listar grabaciones disponibles."""
    
    def __init__(self, nao_facade, logger, recordings_dir="/home/nao/recordings"):
        super(ListRecordingsCommand, self).__init__(nao_facade, logger)
        self.recordings_dir = recordings_dir
    
    def execute(self, message, websocket):
        """Ejecutar comando listRecordings."""
        try:
            recordings = []
            
            if os.path.exists(self.recordings_dir):
                for filename in os.listdir(self.recordings_dir):
                    if filename.endswith('.csv'):
                        filepath = os.path.join(self.recordings_dir, filename)
                        stat = os.stat(filepath)
                        recordings.append({
                            "name": filename,
                            "path": filepath,
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        })
            
            # Ordenar por fecha de modificación (más reciente primero)
            recordings.sort(key=lambda x: x["modified"], reverse=True)
            
            response = {
                "listRecordings": {
                    "success": True,
                    "recordings": recordings,
                    "count": len(recordings),
                    "directory": self.recordings_dir
                }
            }
            websocket.sendMessage(json.dumps(response))
            return True
            
        except Exception as e:
            self.logger.error("Error listando grabaciones: {}".format(e))
            websocket.sendMessage(json.dumps({
                "listRecordings": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "listRecordings"
