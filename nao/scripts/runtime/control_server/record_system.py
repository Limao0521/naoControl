#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
record_system.py - Sistema de grabación de movimientos con soporte de bumper

Sistema singleton que gestiona grabación de datos de sensores para entrenamiento
de modelos de marcha. Incluye monitoreo del bumper derecho para iniciar/pausar
grabación cuando el modo de grabación está activo.

Uso desde control server:
    from record_system import get_record_system, toggle_record_mode, get_record_status

    # Activar modo grabación (habilita bumper)
    toggle_record_mode()
    
    # O iniciar/detener manualmente
    start_recording()
    stop_recording()
"""

from __future__ import print_function
import os
import sys
import time
import threading
import json
from datetime import datetime

# Path setup
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except ImportError:
    NAOQI_AVAILABLE = False

# Python 2/3 compatibility for unicode
try:
    unicode
except NameError:
    unicode = str

# Import DataLogger
try:
    from data_logger import DataLogger, SensorReader
except ImportError:
    DataLogger = None
    SensorReader = None


class RecordSystem(object):
    """
    Sistema singleton para grabación de datos de sensores con soporte de bumper.
    
    Cuando el modo de grabación está activo, el bumper derecho del pie inicia/pausa
    la grabación de datos.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RecordSystem, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, nao_ip="127.0.0.1", nao_port=9559, logger=None):
        if self._initialized:
            return
        
        self._initialized = True
        self.nao_ip = nao_ip
        self.nao_port = nao_port
        self.logger = logger
        
        # Estado
        self.mode_active = False
        self.is_recording = False
        self.current_file = None
        self.samples_count = 0
        
        # Componentes
        self.memory = None
        self.leds = None
        self.tts = None
        self.sensor_reader = None
        self.data_logger = None
        
        # Thread de bumper
        self.bumper_thread = None
        self.bumper_running = False
        self.bumper_cooldown = 0
        self.last_bumper_state = False
        
        # Thread de grabación
        self.recording_thread = None
        self.recording_running = False
        self.recording_frequency = 10  # Hz
        
        # Directorio de grabaciones
        self.recordings_dir = os.path.join(
            os.path.dirname(os.path.dirname(_current_dir)),
            'data', 'recordings'
        )
        
        # Inicializar conexiones NAO
        self._init_nao_proxies()
        
        # Crear directorio si no existe
        if not os.path.exists(self.recordings_dir):
            try:
                os.makedirs(self.recordings_dir)
                self._log("Directorio de grabaciones creado: {}".format(self.recordings_dir))
            except Exception as e:
                self._log("Error creando directorio: {}".format(e), level="error")
    
    def _log(self, msg, level="info"):
        """Log con logger o print fallback"""
        if self.logger:
            if level == "error":
                self.logger.error(msg)
            elif level == "warning":
                self.logger.warning(msg)
            else:
                self.logger.info(msg)
        else:
            print("[RECORD_SYSTEM] {}".format(msg))
    
    def _init_nao_proxies(self):
        """Inicializar proxies NAOqi"""
        if not NAOQI_AVAILABLE:
            self._log("NAOqi no disponible", level="warning")
            return
        
        try:
            self.memory = ALProxy("ALMemory", self.nao_ip, self.nao_port)
            self._log("ALMemory conectado")
        except Exception as e:
            self._log("Error conectando ALMemory: {}".format(e), level="error")
        
        try:
            self.leds = ALProxy("ALLeds", self.nao_ip, self.nao_port)
        except Exception as e:
            self._log("ALLeds no disponible: {}".format(e), level="warning")
        
        try:
            self.tts = ALProxy("ALTextToSpeech", self.nao_ip, self.nao_port)
        except Exception as e:
            self._log("ALTextToSpeech no disponible: {}".format(e), level="warning")
        
        # SensorReader para datos
        if SensorReader:
            try:
                self.sensor_reader = SensorReader(self.nao_ip, self.nao_port)
                self._log("SensorReader inicializado")
            except Exception as e:
                self._log("Error inicializando SensorReader: {}".format(e), level="error")
    
    def _set_led_indicator(self, state):
        """Configurar LED indicador de estado"""
        if not self.leds:
            return
        
        try:
            if state == "mode_active":
                # Modo activo pero no grabando - LED derecho azul
                self.leds.fadeRGB("RightFaceLeds", 0x000000FF, 0.3)
            elif state == "recording":
                # Grabando - LED derecho verde parpadeante
                self.leds.fadeRGB("RightFaceLeds", 0x0000FF00, 0.3)
            elif state == "off":
                # Apagar LED
                self.leds.fadeRGB("RightFaceLeds", 0x00000000, 0.3)
        except Exception as e:
            self._log("Error configurando LED: {}".format(e), level="warning")
    
    def _speak(self, text):
        """Hacer que el robot hable"""
        if not self.tts:
            return
        try:
            if isinstance(text, unicode):
                text = text.encode('utf-8')
            self.tts.say(text)
        except Exception as e:
            self._log("Error en TTS: {}".format(e), level="warning")
    
    def _check_bumper(self):
        """Verificar estado del bumper derecho"""
        if not self.memory:
            return False

    def _web_control_owns_bumpers(self):
        """Avoid competing with the intelligent-mode physical controller."""
        mode_path = os.environ.get('NAO_CONTROL_MODE_FILE', '/tmp/nao_control_mode.json')
        try:
            with open(mode_path, 'r') as mode_file:
                state = json.load(mode_file)
            return state.get('mode', 'WEB_CONTROL') == 'WEB_CONTROL'
        except (IOError, OSError, ValueError):
            return True
        try:
            value = self.memory.getData("RightBumperPressed")
            return value == 1.0
        except Exception:
            return False
    
    def _bumper_monitor_loop(self):
        """Loop de monitoreo del bumper (corre en thread separado)"""
        self._log("Monitor de bumper iniciado")
        
        while self.bumper_running and self.mode_active:
            try:
                if not self._web_control_owns_bumpers():
                    if self.is_recording:
                        self.stop_recording()
                    time.sleep(0.1)
                    continue
                # Cooldown para evitar rebotes
                if self.bumper_cooldown > 0:
                    self.bumper_cooldown -= 1
                else:
                    current_state = self._check_bumper()
                    
                    # Detectar flanco de subida (presión del botón)
                    if current_state and not self.last_bumper_state:
                        self._log("Bumper derecho presionado")
                        
                        if self.is_recording:
                            self.stop_recording()
                        else:
                            self.start_recording()
                        
                        # Cooldown de 500ms (10 ciclos a 20Hz)
                        self.bumper_cooldown = 10
                    
                    self.last_bumper_state = current_state
                
                time.sleep(0.05)  # 20Hz polling
                
            except Exception as e:
                self._log("Error en monitor bumper: {}".format(e), level="error")
                time.sleep(0.1)
        
        self._log("Monitor de bumper detenido")
    
    def _recording_loop(self):
        """Loop de grabación de datos (corre en thread separado)"""
        self._log("Loop de grabación iniciado - {} Hz".format(self.recording_frequency))
        
        interval = 1.0 / self.recording_frequency
        
        while self.recording_running and self.is_recording:
            try:
                if self.sensor_reader and self.data_logger:
                    self.data_logger.log_sample()
                    self.samples_count += 1
                    
                    # Log cada 100 muestras
                    if self.samples_count % 100 == 0:
                        self._log("Muestras grabadas: {}".format(self.samples_count))
                
                time.sleep(interval)
                
            except Exception as e:
                self._log("Error grabando muestra: {}".format(e), level="error")
                time.sleep(interval)
        
        self._log("Loop de grabación detenido")
    
    def toggle_mode(self):
        """Alternar modo de grabación (activa/desactiva monitoreo de bumper)"""
        if not self.mode_active and not self._web_control_owns_bumpers():
            self._log("Bumper reservado por modo Nemotron", level="warning")
            return False
        if self.mode_active:
            # Desactivar modo
            self.mode_active = False
            self.bumper_running = False
            
            # Detener grabación si está activa
            if self.is_recording:
                self.stop_recording()
            
            # Esperar a que termine el thread
            if self.bumper_thread and self.bumper_thread.is_alive():
                self.bumper_thread.join(timeout=2)
            
            self._set_led_indicator("off")
            self._speak("Modo grabación desactivado")
            self._log("Modo de grabación DESACTIVADO")
            
        else:
            # Activar modo
            self.mode_active = True
            self.bumper_running = True
            self.last_bumper_state = self._check_bumper()  # Estado inicial
            
            # Iniciar thread de monitoreo de bumper
            self.bumper_thread = threading.Thread(target=self._bumper_monitor_loop)
            self.bumper_thread.daemon = True
            self.bumper_thread.start()
            
            self._set_led_indicator("mode_active")
            self._speak("Modo grabación activado. Presione el bumper derecho para grabar.")
            self._log("Modo de grabación ACTIVADO - Bumper habilitado")
        
        return True
    
    def start_recording(self, filename=None):
        """Iniciar grabación de datos"""
        if self.is_recording:
            self._log("Ya hay una grabación en curso", level="warning")
            return False
        
        if not self.sensor_reader:
            self._log("SensorReader no disponible", level="error")
            return False
        
        if not DataLogger:
            self._log("DataLogger no disponible", level="error")
            return False
        
        # Generar nombre de archivo
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = "recording_{}.csv".format(timestamp)
        
        self.current_file = os.path.join(self.recordings_dir, filename)
        
        try:
            # Crear DataLogger
            self.data_logger = DataLogger(self.current_file, self.sensor_reader)
            self.data_logger.start_logging()
            
            self.is_recording = True
            self.samples_count = 0
            self.recording_running = True
            
            # Iniciar thread de grabación
            self.recording_thread = threading.Thread(target=self._recording_loop)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            self._set_led_indicator("recording")
            self._speak("Grabación iniciada")
            self._log("Grabación iniciada: {}".format(self.current_file))
            
            return True
            
        except Exception as e:
            self._log("Error iniciando grabación: {}".format(e), level="error")
            self.is_recording = False
            return False
    
    def stop_recording(self):
        """Detener grabación de datos"""
        if not self.is_recording:
            self._log("No hay grabación en curso", level="warning")
            return {"file": None, "samples": 0}
        
        # Detener thread de grabación
        self.recording_running = False
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2)
        
        # Cerrar DataLogger
        if self.data_logger:
            try:
                self.data_logger.stop_logging()
            except Exception as e:
                self._log("Error cerrando DataLogger: {}".format(e), level="error")
        
        result = {
            "file": self.current_file,
            "samples": self.samples_count
        }
        
        self.is_recording = False
        self._set_led_indicator("mode_active" if self.mode_active else "off")
        self._speak("Grabación detenida. {} muestras guardadas.".format(self.samples_count))
        self._log("Grabación detenida: {} muestras en {}".format(
            self.samples_count, self.current_file))
        
        self.current_file = None
        self.samples_count = 0
        self.data_logger = None
        
        return result
    
    def get_status(self):
        """Obtener estado actual del sistema"""
        return {
            "mode_active": self.mode_active,
            "recording": self.is_recording,
            "current_file": self.current_file,
            "samples": self.samples_count,
            "recordings_dir": self.recordings_dir,
            "bumper_enabled": self.mode_active and self.bumper_running
        }
    
    def cleanup(self):
        """Limpiar recursos"""
        if self.is_recording:
            self.stop_recording()
        
        if self.mode_active:
            self.mode_active = False
            self.bumper_running = False
        
        self._set_led_indicator("off")
        self._log("RecordSystem cleanup completado")


# === Funciones de módulo para fácil acceso ===

_record_system = None

def get_record_system(nao_ip="127.0.0.1", nao_port=9559, logger=None):
    """Obtener instancia singleton del sistema de grabación"""
    global _record_system
    if _record_system is None:
        _record_system = RecordSystem(nao_ip, nao_port, logger)
    return _record_system

def toggle_record_mode():
    """Alternar modo de grabación"""
    system = get_record_system()
    return system.toggle_mode()

def get_record_status():
    """Obtener estado del sistema"""
    system = get_record_system()
    return system.get_status()

def start_recording(filename=None):
    """Iniciar grabación"""
    system = get_record_system()
    return system.start_recording(filename)

def stop_recording():
    """Detener grabación"""
    system = get_record_system()
    return system.stop_recording()

def cleanup_record_system():
    """Limpiar sistema de grabación"""
    global _record_system
    if _record_system:
        _record_system.cleanup()
        _record_system = None
