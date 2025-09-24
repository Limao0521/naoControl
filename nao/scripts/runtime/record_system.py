#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
record_system.py - Sistema de grabación por voz con control por bumper

Funcionalidad:
- Modo grabación activado/desactivado por WebSocket action
- Ojos naranjas: esperando órdenes (modo activo)
- Bumper derecho del pie: inicia grabación mientras se mantiene presionado
- Ojos verdes: grabando activamente (solo mientras se presiona bumper)
- Ojos naranjas: vuelve al estado de espera al soltar bumper
- Archivos guardados en: /data/home/nao/datasets/records/

Dependencias: NAOqi ALAudioRecorder, ALMemory, ALLeds, ALTextToSpeech
"""

from __future__ import print_function
import sys, os, time, threading, json
from datetime import datetime
from naoqi import ALProxy

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("RECORD")
    logger.info("Sistema de logging centralizado conectado - RECORD")
except ImportError:
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [RECORD] {}".format(msg))
        def info(self, msg): print("INFO [RECORD] {}".format(msg))
        def warning(self, msg): print("WARNING [RECORD] {}".format(msg))
        def error(self, msg): print("ERROR [RECORD] {}".format(msg))
        def critical(self, msg): print("CRITICAL [RECORD] {}".format(msg))
    logger = FallbackLogger()
    print("WARNING: Sistema de logging centralizado no disponible, usando fallback - RECORD")

# Configuración
IP_NAO = "127.0.0.1"
PORT_NAO = 9559
AUDIO_FORMAT = "wav"  # Formato de audio
SAMPLE_RATE = 16000   # Frecuencia de muestreo
CHANNELS = 1          # Canales (mono)
RECORDINGS_DIR = "/data/home/nao/datasets/records"  # Directorio de grabaciones

# Variable global para la instancia del sistema
_record_system_instance = None

# CALLBACK GLOBAL PARA NAOQI - DEBE ESTAR EN EL NIVEL DEL MÓDULO
def onRightBumperPressed(key, value, message):
    """Callback global para eventos de bumper derecho - PARA NAOQI"""
    global _record_system_instance
    print("*** CALLBACK BUMPER ACTIVADO ***")
    print("Key: {}, Value: {}, Message: {}".format(key, value, message))
    
    if _record_system_instance:
        _record_system_instance._handle_bumper_event(key, value, message)
    else:
        print("WARNING: _record_system_instance es None en callback")

class RecordSystem:
    def __init__(self):
        global _record_system_instance
        self.mode_active = False
        self.recording = False
        self.current_filename = None
        self.polling_thread = None
        self.polling_active = False
        self.last_bumper_state = 0.0
        
        # Inicializar proxies NAOqi
        try:
            self.memory = ALProxy("ALMemory", IP_NAO, PORT_NAO)
            self.leds = ALProxy("ALLeds", IP_NAO, PORT_NAO)
            self.tts = ALProxy("ALTextToSpeech", IP_NAO, PORT_NAO)
            self.audio_recorder = ALProxy("ALAudioRecorder", IP_NAO, PORT_NAO)
            logger.info("RecordSystem: Proxies NAOqi inicializados correctamente")
        except Exception as e:
            logger.critical("RecordSystem: Error inicializando proxies NAOqi: {}".format(e))
            raise
        
        # Crear directorio de grabaciones si no existe
        self._ensure_recordings_dir()
        
        # Establecer instancia global
        _record_system_instance = self
        
        logger.info("RecordSystem: Sistema inicializado")
    
    def _ensure_recordings_dir(self):
        """Crear directorio de grabaciones si no existe"""
        try:
            if not os.path.exists(RECORDINGS_DIR):
                os.makedirs(RECORDINGS_DIR)
                logger.info("RecordSystem: Directorio de grabaciones creado: {}".format(RECORDINGS_DIR))
        except Exception as e:
            logger.warning("RecordSystem: No se pudo crear directorio de grabaciones: {}".format(e))
    
    def _set_led_color(self, color):
        """Cambiar color de ojos. color: 'orange', 'green', 'off'"""
        try:
            if color == "orange":
                # Naranja: RGB(255, 165, 0) = 0xFFA500
                self.leds.fadeRGB("FaceLeds", 0xFFA500, 0.3)
                logger.debug("RecordSystem: LEDs naranjas (esperando)")
            elif color == "green":
                # Verde: RGB(0, 255, 0) = 0x00FF00
                self.leds.fadeRGB("FaceLeds", 0x00FF00, 0.3)
                logger.debug("RecordSystem: LEDs verdes (grabando)")
            elif color == "off":
                # Apagar LEDs
                self.leds.fadeRGB("FaceLeds", 0x000000, 0.3)
                logger.debug("RecordSystem: LEDs apagados")
        except Exception as e:
            logger.warning("RecordSystem: Error cambiando LEDs: {}".format(e))
    
    def _generate_filename(self):
        """Generar nombre de archivo único para grabación"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return "{}/recording_{}.{}".format(RECORDINGS_DIR, timestamp, AUDIO_FORMAT)
    
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
                # Leer estado actual del bumper derecho
                current_state = self.memory.getData("RightBumperPressed")
                
                # Detectar cambios de estado
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
            
            # Asegurar que el directorio existe
            self._ensure_recordings_dir()
            
            # Verificar que el directorio sea escribible
            test_file = "{}/test_write.tmp".format(RECORDINGS_DIR)
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.info("RecordSystem: ✓ Directorio es escribible: {}".format(RECORDINGS_DIR))
            except Exception as e:
                logger.error("RecordSystem: ✗ Directorio NO es escribible: {} - Error: {}".format(RECORDINGS_DIR, e))
                return
            
            # Generar nombre de archivo
            self.current_filename = self._generate_filename()
            logger.info("RecordSystem: Archivo de grabación: {}".format(self.current_filename))
            
            # Configurar y iniciar grabación
            try:
                self.audio_recorder.stopMicrophonesRecording()  # Asegurar que no hay grabación previa
                time.sleep(0.2)
                logger.debug("RecordSystem: stopMicrophonesRecording ejecutado")
            except Exception as e:
                logger.debug("RecordSystem: stopMicrophonesRecording error (expected): {}".format(e))
            
            # Verificar parámetros de grabación
            logger.info("RecordSystem: Iniciando grabación con parámetros:")
            logger.info("  - Archivo: {}".format(self.current_filename))
            logger.info("  - Formato: {}".format(AUDIO_FORMAT))
            logger.info("  - Sample Rate: {}".format(SAMPLE_RATE))
            logger.info("  - Canales: [0, 0, 1, 0] (micrófono frontal)")
            
            # Iniciar grabación
            self.audio_recorder.startMicrophonesRecording(
                self.current_filename,
                AUDIO_FORMAT,
                SAMPLE_RATE,
                [0, 0, 1, 0]  # Solo micrófono frontal
            )
            
            self.recording = True
            
            # Cambiar LEDs a verde inmediatamente
            self._set_led_color("green")
            
            logger.info("RecordSystem: *** GRABACIÓN INICIADA *** Archivo: {}".format(self.current_filename))
            
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
            
            logger.info("RecordSystem: Parando grabación de: {}".format(self.current_filename))
            
            # Parar grabación
            self.audio_recorder.stopMicrophonesRecording()
            self.recording = False
            
            # Volver a LEDs naranjas si el modo sigue activo
            if self.mode_active:
                self._set_led_color("orange")
            else:
                self._set_led_color("off")
            
            logger.info("RecordSystem: *** GRABACIÓN PARADA *** Archivo: {}".format(self.current_filename))
            
            # Verificar si el archivo fue creado (con múltiples intentos)
            if self.current_filename:
                logger.info("RecordSystem: Verificando archivo creado...")
                
                # Intentar múltiples veces con delays
                for attempt in range(5):
                    time.sleep(0.5)  # Dar tiempo para que el archivo se escriba
                    
                    if os.path.exists(self.current_filename):
                        file_size = os.path.getsize(self.current_filename)
                        logger.info("RecordSystem: ✓ Archivo creado correctamente: {} ({} bytes)".format(
                            self.current_filename, file_size))
                        
                        # Verificar contenido del directorio
                        try:
                            files_in_dir = os.listdir(RECORDINGS_DIR)
                            logger.info("RecordSystem: Archivos en directorio: {}".format(files_in_dir))
                        except Exception as e:
                            logger.warning("RecordSystem: Error listando directorio: {}".format(e))
                        
                        break
                    else:
                        logger.warning("RecordSystem: Intento {}/5 - Archivo aún no existe: {}".format(
                            attempt + 1, self.current_filename))
                else:
                    # Si no se creó después de todos los intentos
                    logger.error("RecordSystem: ✗ El archivo de grabación NO fue creado: {}".format(
                        self.current_filename))
                    
                    # Listar contenido del directorio para debug
                    try:
                        files_in_dir = os.listdir(RECORDINGS_DIR)
                        logger.error("RecordSystem: Archivos en directorio: {}".format(files_in_dir))
                        
                        # Verificar permisos del directorio
                        import stat
                        dir_stat = os.stat(RECORDINGS_DIR)
                        logger.error("RecordSystem: Permisos directorio: {}".format(oct(dir_stat.st_mode)))
                    except Exception as e:
                        logger.error("RecordSystem: Error verificando directorio: {}".format(e))
            
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
            # SOLUCIÓN: Usar polling en lugar de callbacks
            # El callback de NAOqi es problemático, usaremos polling de la memoria
            self.mode_active = True
            logger.info("RecordSystem: Modo de grabación ACTIVADO (usando polling)")
            
            # Configurar LEDs naranjas (esperando)
            self._set_led_color("orange")
            
            # Iniciar hilo de polling
            self._start_polling_thread()
            
            # Feedback de audio
            try:
                self.tts.say("Modo grabación activado. Presione bumper derecho para grabar.")
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
    
    def test_bumpers(self):
        """Método de prueba para verificar que los eventos de bumper funcionan"""
        try:
            # Test simple: suscribirse a TODOS los eventos de bumper para ver cuáles están disponibles
            def test_callback(key, value, message):
                logger.info("TEST: Evento detectado - key: {}, value: {}, message: {}".format(key, value, message))
            
            # Suscribirse a múltiples eventos para encontrar el correcto
            events_to_test = [
                "RightBumperPressed",
                "LeftBumperPressed", 
                "FrontTactilTouched",
                "MiddleTactilTouched",
                "RearTactilTouched"
            ]
            
            for event in events_to_test:
                try:
                    self.memory.subscribeToEvent(event, "TestBumper_{}".format(event), "test_callback")
                    logger.info("TEST: Suscrito a evento: {}".format(event))
                except Exception as e:
                    logger.warning("TEST: No se pudo suscribir a {}: {}".format(event, e))
            
            logger.info("TEST: Prueba todos los sensores táctiles ahora...")
            time.sleep(10)
            
            # Desuscribirse
            for event in events_to_test:
                try:
                    self.memory.unsubscribeToEvent(event, "TestBumper_{}".format(event))
                except Exception:
                    pass
            
        except Exception as e:
            logger.error("TEST: Error en test de bumpers: {}".format(e))
    
    def get_status(self):
        """Obtener estado actual del sistema"""
        return {
            "mode_active": self.mode_active,
            "recording": self.recording,
            "current_file": self.current_filename,
            "recordings_dir": RECORDINGS_DIR
        }
    
    def cleanup(self):
        """Limpieza al cerrar"""
        logger.info("RecordSystem: Realizando limpieza...")
        if self.mode_active:
            self.deactivate_mode()

# Instancia global del sistema de grabación
_record_system = None

def get_record_system():
    """Obtener instancia singleton del sistema de grabación"""
    global _record_system
    if _record_system is None:
        _record_system = RecordSystem()
    return _record_system

def activate_record_mode():
    """Función de conveniencia para activar modo"""
    return get_record_system().activate_mode()

def deactivate_record_mode():
    """Función de conveniencia para desactivar modo"""
    return get_record_system().deactivate_mode()

def toggle_record_mode():
    """Función de conveniencia para alternar modo"""
    system = get_record_system()
    if system.mode_active:
        return system.deactivate_mode()
    else:
        return system.activate_mode()

def get_record_status():
    """Función de conveniencia para obtener estado"""
    return get_record_system().get_status()

def cleanup_record_system():
    """Función de conveniencia para limpieza"""
    global _record_system
    if _record_system:
        _record_system.cleanup()
        _record_system = None

# Test básico si se ejecuta directamente
if __name__ == "__main__":
    logger.info("RecordSystem: Test básico iniciado")
    
    # Hacer que las funciones callback sean accesibles globalmente para NAOqi
    import sys
    current_module = sys.modules[__name__]
    globals().update({
        'onRightBumperPressed': onRightBumperPressed
    })
    
    try:
        system = RecordSystem()
        logger.info("RecordSystem: Sistema inicializado correctamente")
        
        # Añadir opción de test de eventos
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            logger.info("RecordSystem: Ejecutando test de sensores...")
            system.test_bumpers()
            logger.info("RecordSystem: Test de sensores completado")
            system.cleanup()
            sys.exit(0)
        
        # Test de activación/desactivación
        logger.info("RecordSystem: Activando modo...")
        if system.activate_mode():
            logger.info("RecordSystem: Modo activado, presiona bumper derecho o Ctrl+C para salir")
            
            # Mantener activo
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("RecordSystem: Interrupción detectada")
            
            logger.info("RecordSystem: Desactivando modo...")
            system.deactivate_mode()
        else:
            logger.error("RecordSystem: No se pudo activar el modo")
        
        system.cleanup()
        logger.info("RecordSystem: Test completado")
        
    except Exception as e:
        logger.error("RecordSystem: Error en test: {}".format(e))