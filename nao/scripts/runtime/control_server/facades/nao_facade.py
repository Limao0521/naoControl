#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
nao_facade.py - Facade Pattern para NAOqi

Proporciona una interfaz simplificada y segura para interactuar con NAOqi.
Maneja la inicialización de proxies, manejo de errores y operaciones comunes.
"""

from __future__ import print_function
import time
import math
from naoqi import ALProxy

class NAOFacade(object):
    """
    Facade para simplificar el acceso a los servicios de NAOqi.
    Maneja proxies, errores y operaciones comunes de forma centralizada.
    """
    
    def __init__(self, ip="127.0.0.1", port=9559, logger=None):
        """
        Inicializar el facade con conexión a NAOqi.
        
        Args:
            ip (str): IP del robot NAO
            port (int): Puerto de NAOqi
            logger: Logger para registro de eventos
        """
        self.ip = ip
        self.port = port
        self.logger = logger or self._create_fallback_logger()
        
        # Proxies NAOqi
        self.motion = None
        self.posture = None
        self.life = None
        self.leds = None
        self.tts = None
        self.battery = None
        self.memory = None
        self.audio = None
        self.behavior = None
        
        self._initialize_proxies()
        self._setup_initial_state()
    
    def _create_fallback_logger(self):
        """Crear logger de fallback si no se proporciona uno."""
        class FallbackLogger:
            def debug(self, msg): print("DEBUG [NAO_FACADE] {}".format(msg))
            def info(self, msg): print("INFO [NAO_FACADE] {}".format(msg))
            def warning(self, msg): print("WARNING [NAO_FACADE] {}".format(msg))
            def error(self, msg): print("ERROR [NAO_FACADE] {}".format(msg))
            def critical(self, msg): print("CRITICAL [NAO_FACADE] {}".format(msg))
        return FallbackLogger()
    
    def _initialize_proxies(self):
        """Inicializar todos los proxies de NAOqi."""
        proxies = {
            'motion': 'ALMotion',
            'posture': 'ALRobotPosture', 
            'life': 'ALAutonomousLife',
            'leds': 'ALLeds',
            'tts': 'ALTextToSpeech',
            'battery': 'ALBattery',
            'memory': 'ALMemory',
            'audio': 'ALAudioDevice',
            'behavior': 'ALBehaviorManager'
        }
        
        for attr_name, service_name in proxies.items():
            try:
                proxy = ALProxy(service_name, self.ip, self.port)
                setattr(self, attr_name, proxy)
                self.logger.debug("Proxy {} inicializado correctamente".format(service_name))
            except Exception as e:
                self.logger.error("Error inicializando proxy {}: {}".format(service_name, e))
                setattr(self, attr_name, None)
        
        self.logger.info("Proxies NAOqi inicializados")
    
    def _setup_initial_state(self):
        """Configurar estado inicial del robot."""
        try:
            # Fall manager activado para auto-recovery
            if self.motion:
                self.motion.setFallManagerEnabled(True)
                self.logger.info("Fall manager activado")
            
            # Autonomous Life desactivado para control directo
            if self.life:
                self.life.setState("disabled")
                self.logger.info("Autonomous Life desactivado")
            
            # Rigidez corporal activada
            if self.motion:
                self.motion.setStiffnesses("Body", 1.0)
                self.logger.info("Rigidez corporal activada")
            
            # Activar movimiento de brazos durante caminata
            if self.motion:
                self.safe_call(self.motion.setMoveArmsEnabled, True, True)
                
            # Protección de contacto de pie activada
            if self.motion:
                self.safe_call(self.motion.setMotionConfig, 
                              [["ENABLE_FOOT_CONTACT_PROTECTION", True]])
                
        except Exception as e:
            self.logger.error("Error configurando estado inicial: {}".format(e))
    
    def safe_call(self, func, *args, **kwargs):
        """
        Ejecutar llamada a NAOqi de forma segura con manejo de errores.
        
        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos nombrados
            
        Returns:
            Resultado de la función o None si hay error
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = getattr(func, '__name__', str(func))
            self.logger.warning("Error en {}: {}".format(func_name, e))
            return None
    
    # === MOTION METHODS ===
    def move_toward(self, vx, vy, wz, config=None):
        """Mover robot con velocidades especificadas."""
        if not self.motion:
            return False
        
        try:
            if config:
                self.motion.moveToward(vx, vy, wz, config)
            else:
                self.motion.moveToward(vx, vy, wz)
            return True
        except Exception as e:
            self.logger.warning("moveToward falló con config, reintentando sin config: {}".format(e))
            try:
                self.motion.moveToward(vx, vy, wz)
                return True
            except Exception as e2:
                self.logger.error("moveToward falló completamente: {}".format(e2))
                return False
    
    def move_to(self, x, y, theta, config=None):
        """Mover robot a posición específica."""
        if not self.motion:
            return False
            
        try:
            if config:
                self.motion.moveTo(x, y, theta, config)
            else:
                self.motion.moveTo(x, y, theta)
            return True
        except Exception as e:
            self.logger.error("moveTo falló: {}".format(e))
            return False
    
    def stop_move(self):
        """Detener movimiento del robot."""
        return self.safe_call(self.motion.stopMove) is not None
    
    def set_angles(self, joint, angle, speed=0.1):
        """Configurar ángulo de articulación."""
        if not self.motion:
            return False
        return self.safe_call(self.motion.setAngles, str(joint), angle, speed) is not None
    
    def set_stiffnesses(self, names, stiffness):
        """Configurar rigidez de articulaciones."""
        if not self.motion:
            return False
        return self.safe_call(self.motion.setStiffnesses, names, stiffness) is not None
    
    # === POSTURE METHODS ===
    def go_to_posture(self, posture_name, speed=0.7):
        """Ir a postura específica."""
        if not self.posture:
            return False
        return self.safe_call(self.posture.goToPosture, str(posture_name), speed) is not None
    
    # === LED METHODS ===
    def set_led_rgb(self, group, r, g, b, duration=0.3):
        """Configurar LEDs RGB."""
        if not self.leds:
            return False
        
        rgb_int = (int(r*255) << 16) | (int(g*255) << 8) | int(b*255)
        
        if group in ("LeftEarLeds", "RightEarLeds"):
            intensity = (rgb_int & 0xFF) / 255.0
            return self.safe_call(self.leds.fade, group, intensity, duration) is not None
        else:
            return self.safe_call(self.leds.fadeRGB, group, rgb_int, duration) is not None
    
    # === TTS METHODS ===
    def say(self, text):
        """Hacer hablar al robot."""
        if not self.tts:
            return False
        return self.safe_call(self.tts.say, str(text)) is not None
    
    def set_language(self, language):
        """Configurar idioma TTS."""
        if not self.tts:
            return False
        return self.safe_call(self.tts.setLanguage, str(language)) is not None
    
    # === AUTONOMOUS LIFE METHODS ===
    def set_autonomous_life(self, enable):
        """Configurar Autonomous Life."""
        if not self.life:
            return False
        state = "interactive" if enable else "disabled"
        return self.safe_call(self.life.setState, state) is not None
    
    def get_autonomous_life_state(self):
        """Obtener estado de Autonomous Life."""
        if not self.life:
            return "unknown"
        return self.safe_call(self.life.getState) or "unknown"
    
    # === BEHAVIOR METHODS ===
    def run_behavior(self, behavior_name):
        """Ejecutar behavior."""
        if not self.behavior:
            return False
        
        try:
            # Detener behaviors en ejecución
            running = self.behavior.getRunningBehaviors()
            for bhv in running:
                self.behavior.stopBehavior(bhv)
            
            # Ejecutar nuevo behavior
            if self.behavior.isBehaviorInstalled(behavior_name):
                self.behavior.runBehavior(behavior_name)
                return True
            else:
                self.logger.warning("Behavior no instalado: {}".format(behavior_name))
                return False
        except Exception as e:
            self.logger.error("Error ejecutando behavior {}: {}".format(behavior_name, e))
            return False
    
    # === AUDIO METHODS ===
    def set_volume(self, volume):
        """Configurar volumen de audio."""
        if not self.audio:
            return False
        return self.safe_call(self.audio.setOutputVolume, volume) is not None
    
    # === BATTERY METHODS ===
    def get_battery_level(self):
        """Obtener nivel de batería."""
        if not self.battery:
            return 100
        return self.safe_call(self.battery.getBatteryCharge) or 100
    
    # === MEMORY METHODS ===
    def get_memory_data(self, key):
        """Obtener datos de memoria."""
        if not self.memory:
            return None
        return self.safe_call(self.memory.getData, key)
    
    def subscribe_to_event(self, event, subscriber, callback):
        """Suscribirse a evento de memoria."""
        if not self.memory:
            return False
        return self.safe_call(self.memory.subscribeToEvent, event, subscriber, callback) is not None
    
    def unsubscribe_from_event(self, event, subscriber):
        """Desuscribirse de evento de memoria."""
        if not self.memory:
            return False
        return self.safe_call(self.memory.unsubscribeToEvent, event, subscriber) is not None
    
    # === UTILITY METHODS ===
    def is_proxy_available(self, proxy_name):
        """Verificar si un proxy está disponible."""
        return getattr(self, proxy_name, None) is not None
    
    def get_available_proxies(self):
        """Obtener lista de proxies disponibles."""
        proxies = ['motion', 'posture', 'life', 'leds', 'tts', 
                  'battery', 'memory', 'audio', 'behavior']
        return [proxy for proxy in proxies if self.is_proxy_available(proxy)]
    
    def health_check(self):
        """Realizar chequeo de salud de conexiones."""
        available = self.get_available_proxies()
        total = 9  # Total de proxies esperados
        health_score = len(available) / float(total) * 100
        
        return {
            "health_score": health_score,
            "available_proxies": available,
            "total_proxies": total,
            "is_healthy": health_score >= 80
        }