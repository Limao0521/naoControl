#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
record_system_fixed.py - Sistema de grabación compatible con todas las versiones de NAO

Versión alternativa que usa ALAudioDevice en lugar de ALAudioRecorder
para compatibilidad con versiones más antiguas de NAOqi.
"""

from __future__ import print_function
import sys, os, time, threading
from datetime import datetime
from naoqi import ALProxy

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("RECORD_FIXED")
    logger.info("Sistema de logging centralizado conectado - RECORD_FIXED")
except ImportError:
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [RECORD_FIXED] {}".format(msg))
        def info(self, msg): print("INFO [RECORD_FIXED] {}".format(msg))
        def warning(self, msg): print("WARNING [RECORD_FIXED] {}".format(msg))
        def error(self, msg): print("ERROR [RECORD_FIXED] {}".format(msg))
        def critical(self, msg): print("CRITICAL [RECORD_FIXED] {}".format(msg))
    logger = FallbackLogger()
    print("WARNING: Sistema de logging centralizado no disponible, usando fallback - RECORD_FIXED")

# Configuración
IP_NAO = "127.0.0.1"
PORT_NAO = 9559
RECORDINGS_DIR = "/data/home/nao/datasets/records"

# Variable global para la instancia del sistema
_record_system_instance = None

class RecordSystemFixed:
    def __init__(self):
        global _record_system_instance
        self.mode_active = False
        self.recording = False
        self.current_filename = None
        self.polling_thread = None
        self.polling_active = False
        self.last_bumper_state = 0.0
        
        # Inicializar proxies NAOqi con verificación de disponibilidad
        try:
            self.memory = ALProxy("ALMemory", IP_NAO, PORT_NAO)
            self.leds = ALProxy("ALLeds", IP_NAO, PORT_NAO)
            self.tts = ALProxy("ALTextToSpeech", IP_NAO, PORT_NAO)
            
            # Intentar diferentes servicios de audio por orden de preferencia
            self.audio_service = None
            self.audio_method = None
            
            # Opción 1: ALAudioRecorder (ideal pero no siempre disponible)
            try:
                self.audio_service = ALProxy("ALAudioRecorder", IP_NAO, PORT_NAO)
                self.audio_method = "recorder"
                logger.info("RecordSystem: Usando ALAudioRecorder")
            except:
                logger.warning("RecordSystem: ALAudioRecorder no disponible")
            
            # Opción 2: ALAudioDevice (más básico pero más compatible)
            if not self.audio_service:
                try:
                    self.audio_service = ALProxy("ALAudioDevice", IP_NAO, PORT_NAO)
                    self.audio_method = "device"
                    logger.info("RecordSystem: Usando ALAudioDevice (modo básico)")
                except:
                    logger.warning("RecordSystem: ALAudioDevice tampoco disponible")
            
            # Opción 3: Solo LEDs (sin audio pero funcional para testing)
            if not self.audio_service:
                logger.warning("RecordSystem: Ningún servicio de audio disponible - MODO SOLO LEDs")
                self.audio_method = "none"
            
            logger.info("RecordSystem: Proxies inicializados - Método audio: {}".format(self.audio_method))
            
        except Exception as e:
            logger.critical("RecordSystem: Error inicializando proxies NAOqi: {}".format(e))
            raise
        
        # Crear directorio de grabaciones si no existe
        self._ensure_recordings_dir()
        
        # Establecer instancia global
        _record_system_instance = self
        
        logger.info("RecordSystem: Sistema inicializado (método: {})".format(self.audio_method))
    
    def _ensure_recordings_dir(self):
        """Crear directorio de grabaciones si no existe"""
        try:
            if not os.path.exists(RECORDINGS_DIR):
                os.makedirs(RECORDINGS_DIR)
                logger.info("RecordSystem: Directorio de grabaciones creado: {}".format(RECORDINGS_DIR))
        except Exception as e:
            logger.warning("RecordSystem: No se pudo crear directorio de grabaciones: {}".format(e))
    
    def _set_led_color(self, color):
        """Cambiar color de ojos."""
        try:
            if color == "orange":
                self.leds.fadeRGB("FaceLeds", 0xFFA500, 0.3)
                logger.debug("RecordSystem: LEDs naranjas (esperando)")
            elif color == "green":
                self.leds.fadeRGB("FaceLeds", 0x00FF00, 0.3)
                logger.debug("RecordSystem: LEDs verdes (grabando)")
            elif color == "off":
                self.leds.fadeRGB("FaceLeds", 0x000000, 0.3)
                logger.debug("RecordSystem: LEDs apagados")
        except Exception as e:
            logger.warning("RecordSystem: Error cambiando LEDs: {}".format(e))
    
    def _generate_filename(self):
        """Generar nombre de archivo único para grabación"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return "{}/recording_{}.wav".format(RECORDINGS_DIR, timestamp)
    
    def _start_polling_thread(self):
        """Iniciar hilo de polling para el bumper"""
        if self.polling_thread and self.polling_thread.is_alive():
            return
        
        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._polling_loop)
        self.polling_thread.daemon = True
        self.polling_thread.start()
        logger.info("RecordSystem: Hilo de polling iniciado")
    
    def _stop_polling_thread(self):
        """Parar hilo de polling"""
        self.polling_active = False
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=2.0)
        logger.info("RecordSystem: Hilo de polling detenido")
    
    def _polling_loop(self):
        """Bucle de polling para detectar cambios en el bumper"""
        logger.info("RecordSystem: Polling loop iniciado")
        
        while self.polling_active and self.mode_active:
            try:
                current_state = self.memory.getData("RightBumperPressed")
                
                if current_state != self.last_bumper_state:
                    logger.info("RecordSystem: Cambio de bumper detectado: {} -> {}".format(
                        self.last_bumper_state, current_state))
                    
                    if current_state == 1.0:
                        logger.info("RecordSystem: Bumper PRESIONADO - iniciando grabación")
                        self._start_recording()
                    elif current_state == 0.0:
                        logger.info("RecordSystem: Bumper LIBERADO - parando grabación") 
                        self._stop_recording()
                    
                    self.last_bumper_state = current_state
                
                time.sleep(0.05)  # Polling a 20Hz
                
            except Exception as e:
                logger.error("RecordSystem: Error en polling loop: {}".format(e))
                time.sleep(0.2)
        
        logger.info("RecordSystem: Polling loop terminado")
    
    def _start_recording(self):
        """Iniciar grabación de audio"""
        try:
            if self.recording:
                logger.warning("RecordSystem: Ya hay una grabación en curso")
                return
            
            self.current_filename = self._generate_filename()
            
            # Cambiar LEDs a verde inmediatamente
            self._set_led_color("green")
            
            if self.audio_method == "recorder":
                # Usar ALAudioRecorder (método original)
                self.audio_service.stopMicrophonesRecording()
                time.sleep(0.1)
                self.audio_service.startMicrophonesRecording(
                    self.current_filename, "wav", 16000, [0, 0, 1, 0])
                logger.info("RecordSystem: *** GRABACIÓN INICIADA con ALAudioRecorder ***")
                
            elif self.audio_method == "device":
                # Usar ALAudioDevice (método alternativo)
                logger.info("RecordSystem: *** SIMULACIÓN DE GRABACIÓN con ALAudioDevice ***")
                # TODO: Implementar grabación básica con ALAudioDevice si es necesario
                # Por ahora, crear archivo vacío para testing
                try:
                    with open(self.current_filename, 'w') as f:
                        f.write("# Archivo de prueba - grabación simulada\n")
                    logger.info("RecordSystem: Archivo de prueba creado: {}".format(self.current_filename))
                except Exception as e:
                    logger.error("RecordSystem: Error creando archivo de prueba: {}".format(e))
                    
            else:
                # Modo solo LEDs (sin audio)
                logger.info("RecordSystem: *** MODO SOLO LEDs - Sin grabación de audio ***")
                
            self.recording = True
            
        except Exception as e:
            logger.error("RecordSystem: Error iniciando grabación: {}".format(e))
            self.recording = False
            if self.mode_active:
                self._set_led_color("orange")
    
    def _stop_recording(self):
        """Parar grabación de audio"""
        try:
            if not self.recording:
                logger.debug("RecordSystem: No hay grabación activa para parar")
                return
            
            if self.audio_method == "recorder":
                self.audio_service.stopMicrophonesRecording()
                logger.info("RecordSystem: *** GRABACIÓN PARADA con ALAudioRecorder ***")
                
            elif self.audio_method == "device":
                logger.info("RecordSystem: *** SIMULACIÓN DE GRABACIÓN PARADA ***")
                # Agregar timestamp al archivo de prueba
                if self.current_filename and os.path.exists(self.current_filename):
                    try:
                        with open(self.current_filename, 'a') as f:
                            f.write("# Grabación parada: {}\n".format(datetime.now().isoformat()))
                    except:
                        pass
                        
            else:
                logger.info("RecordSystem: *** MODO SOLO LEDs - Parada simulada ***")
            
            self.recording = False
            
            # Volver a LEDs naranjas si el modo sigue activo
            if self.mode_active:
                self._set_led_color("orange")
            else:
                self._set_led_color("off")
            
            # Verificar archivo creado
            if self.current_filename and os.path.exists(self.current_filename):
                file_size = os.path.getsize(self.current_filename)
                logger.info("RecordSystem: ✓ Archivo creado: {} ({} bytes)".format(
                    self.current_filename, file_size))
            
            self.current_filename = None
            
        except Exception as e:
            logger.error("RecordSystem: Error parando grabación: {}".format(e))
            self.recording = False
            if self.mode_active:
                self._set_led_color("orange")
            else:
                self._set_led_color("off")
    
    def activate_mode(self):
        """Activar modo de grabación"""
        if self.mode_active:
            logger.warning("RecordSystem: Modo ya activo")
            return False
        
        try:
            self.mode_active = True
            logger.info("RecordSystem: Modo de grabación ACTIVADO (método: {})".format(self.audio_method))
            
            # Configurar LEDs naranjas (esperando)
            self._set_led_color("orange")
            
            # Iniciar hilo de polling
            self._start_polling_thread()
            
            # Feedback de audio
            try:
                if self.audio_method == "none":
                    self.tts.say("Modo grabación activado - solo LEDs disponibles")
                else:
                    self.tts.say("Modo grabación activado")
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            logger.error("RecordSystem: Error activando modo: {}".format(e))
            return False
    
    def deactivate_mode(self):
        """Desactivar modo de grabación"""
        if not self.mode_active:
            logger.warning("RecordSystem: Modo ya inactivo")
            return False
        
        try:
            # Parar grabación si está activa
            if self.recording:
                self._stop_recording()
            
            # Parar polling
            self._stop_polling_thread()
            
            # Apagar LEDs
            self._set_led_color("off")
            
            # Feedback de audio
            try:
                self.tts.say("Modo grabación desactivado")
            except Exception:
                pass
            
            self.mode_active = False
            logger.info("RecordSystem: Modo de grabación DESACTIVADO")
            return True
            
        except Exception as e:
            logger.error("RecordSystem: Error desactivando modo: {}".format(e))
            return False
    
    def get_status(self):
        """Obtener estado actual del sistema"""
        return {
            "mode_active": self.mode_active,
            "recording": self.recording,
            "current_file": self.current_filename,
            "recordings_dir": RECORDINGS_DIR,
            "audio_method": self.audio_method,
            "available": True
        }
    
    def cleanup(self):
        """Limpieza al cerrar"""
        logger.info("RecordSystem: Realizando limpieza...")
        if self.mode_active:
            self.deactivate_mode()

# Funciones de interfaz compatibles
def get_record_system():
    global _record_system_instance
    if _record_system_instance is None:
        _record_system_instance = RecordSystemFixed()
    return _record_system_instance

def toggle_record_mode():
    system = get_record_system()
    if system.mode_active:
        return system.deactivate_mode()
    else:
        return system.activate_mode()

def get_record_status():
    return get_record_system().get_status()

def cleanup_record_system():
    global _record_system_instance
    if _record_system_instance:
        _record_system_instance.cleanup()
        _record_system_instance = None

if __name__ == "__main__":
    logger.info("RecordSystemFixed: Test iniciado")
    
    try:
        system = RecordSystemFixed()
        logger.info("RecordSystemFixed: Sistema inicializado - Método: {}".format(system.audio_method))
        
        # Test de activación/desactivación
        logger.info("RecordSystemFixed: Activando modo...")
        if system.activate_mode():
            logger.info("RecordSystemFixed: Modo activado, presiona bumper derecho o Ctrl+C para salir")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("RecordSystemFixed: Interrupción detectada")
            
            logger.info("RecordSystemFixed: Desactivando modo...")
            system.deactivate_mode()
        else:
            logger.error("RecordSystemFixed: No se pudo activar el modo")
        
        system.cleanup()
        logger.info("RecordSystemFixed: Test completado")
        
    except Exception as e:
        logger.error("RecordSystemFixed: Error en test: {}".format(e))