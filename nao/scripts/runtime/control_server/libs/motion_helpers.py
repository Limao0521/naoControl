#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
motion_helpers.py - Helpers seguros para operaciones NAOqi

Wrappers y utilidades para operaciones de movimiento con
manejo robusto de errores y timeouts.
"""

from __future__ import print_function
import time
import threading


def safe_nao_call(func, success_msg=None, error_prefix="NAO", *args, **kwargs):
    """
    Ejecutar una función NAO con manejo seguro de excepciones.
    
    Args:
        func: Función a ejecutar
        success_msg: Mensaje a loguear si tiene éxito (opcional)
        error_prefix: Prefijo para mensajes de error
        *args, **kwargs: Argumentos para la función
        
    Returns:
        Resultado de la función o None si hay error
    """
    try:
        result = func(*args, **kwargs)
        if success_msg:
            print("{}: {}".format(error_prefix, success_msg))
        return result
    except Exception as e:
        print("{}: Error - {}".format(error_prefix, e))
        return None


class MotionHelper(object):
    """
    Helper para operaciones de movimiento con manejo robusto.
    """
    
    def __init__(self, motion_proxy, logger=None):
        """
        Inicializar helper de movimiento.
        
        Args:
            motion_proxy: Proxy ALMotion
            logger: Logger opcional
        """
        self.motion = motion_proxy
        self.logger = logger or self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Crear logger de fallback."""
        class FallbackLogger:
            def debug(self, msg): print("DEBUG [MOTION] {}".format(msg))
            def info(self, msg): print("INFO [MOTION] {}".format(msg))
            def warning(self, msg): print("WARNING [MOTION] {}".format(msg))
            def error(self, msg): print("ERROR [MOTION] {}".format(msg))
        return FallbackLogger()
    
    def move_toward_safe(self, vx, vy, wz, config=None):
        """
        Ejecutar moveToward con manejo de errores.
        
        Si falla con config, reintenta sin config.
        
        Args:
            vx: Velocidad X
            vy: Velocidad Y
            wz: Velocidad angular
            config: Configuración de gait opcional
            
        Returns:
            bool: True si tuvo éxito
        """
        if not self.motion:
            return False
        
        try:
            if config:
                self.motion.moveToward(vx, vy, wz, config)
            else:
                self.motion.moveToward(vx, vy, wz)
            return True
        except Exception as e:
            if config:
                self.logger.warning("moveToward con config falló: {} - reintentando sin config".format(e))
                try:
                    self.motion.moveToward(vx, vy, wz)
                    return True
                except Exception as e2:
                    self.logger.error("moveToward falló completamente: {}".format(e2))
                    return False
            else:
                self.logger.error("moveToward falló: {}".format(e))
                return False
    
    def move_to_safe(self, x, y, theta, config=None, timeout=30.0):
        """
        Ejecutar moveTo con timeout y manejo de errores.
        
        Args:
            x: Posición X
            y: Posición Y
            theta: Rotación
            config: Configuración de gait opcional
            timeout: Timeout en segundos
            
        Returns:
            bool: True si tuvo éxito
        """
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
    
    def stop_safe(self):
        """Detener movimiento de forma segura."""
        if not self.motion:
            return False
        
        try:
            self.motion.stopMove()
            return True
        except Exception as e:
            self.logger.error("stopMove falló: {}".format(e))
            return False
    
    def wait_until_finished(self, timeout=30.0):
        """
        Esperar hasta que el movimiento termine.
        
        Args:
            timeout: Timeout en segundos
            
        Returns:
            bool: True si terminó, False si timeout
        """
        if not self.motion:
            return False
        
        start = time.time()
        try:
            while self.motion.moveIsActive():
                if time.time() - start > timeout:
                    self.logger.warning("Timeout esperando fin de movimiento")
                    return False
                time.sleep(0.1)
            return True
        except Exception as e:
            self.logger.error("Error esperando fin de movimiento: {}".format(e))
            return False
    
    def set_stiffness_safe(self, names, stiffness):
        """
        Configurar rigidez de forma segura.
        
        Args:
            names: Nombres de articulaciones o "Body"
            stiffness: Valor de rigidez (0.0 a 1.0)
            
        Returns:
            bool: True si tuvo éxito
        """
        if not self.motion:
            return False
        
        try:
            self.motion.setStiffnesses(names, stiffness)
            return True
        except Exception as e:
            self.logger.error("setStiffnesses falló: {}".format(e))
            return False
    
    def set_angles_safe(self, names, angles, speed=0.1):
        """
        Configurar ángulos de articulaciones de forma segura.
        
        Args:
            names: Nombres de articulaciones
            angles: Ángulos objetivo
            speed: Velocidad de movimiento
            
        Returns:
            bool: True si tuvo éxito
        """
        if not self.motion:
            return False
        
        try:
            self.motion.setAngles(names, angles, speed)
            return True
        except Exception as e:
            self.logger.error("setAngles falló: {}".format(e))
            return False


class WatchdogTimer(object):
    """
    Timer watchdog para detener movimiento si no hay comandos.
    """
    
    def __init__(self, motion_proxy, timeout=0.6, logger=None):
        """
        Inicializar watchdog.
        
        Args:
            motion_proxy: Proxy ALMotion
            timeout: Tiempo sin comandos antes de detener (segundos)
            logger: Logger opcional
        """
        self.motion = motion_proxy
        self.timeout = timeout
        self.logger = logger or self._create_fallback_logger()
        
        self._last_command = time.time()
        self._running = False
        self._thread = None
    
    def _create_fallback_logger(self):
        """Crear logger de fallback."""
        class FallbackLogger:
            def info(self, msg): print("INFO [WATCHDOG] {}".format(msg))
            def warning(self, msg): print("WARNING [WATCHDOG] {}".format(msg))
        return FallbackLogger()
    
    def start(self):
        """Iniciar el watchdog."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._watchdog_loop)
        self._thread.setDaemon(True)
        self._thread.start()
        self.logger.info("Watchdog iniciado (timeout={}s)".format(self.timeout))
    
    def stop(self):
        """Detener el watchdog."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
    
    def feed(self):
        """
        'Alimentar' el watchdog (resetear timer).
        Llamar esto cada vez que se recibe un comando de movimiento.
        """
        self._last_command = time.time()
    
    def _watchdog_loop(self):
        """Loop principal del watchdog."""
        while self._running:
            time.sleep(0.05)  # Check cada 50ms
            
            if time.time() - self._last_command > self.timeout:
                try:
                    self.motion.stopMove()
                    self._last_command = time.time()
                except Exception as e:
                    pass  # Ignorar errores del watchdog


class PostureHelper(object):
    """
    Helper para operaciones de postura.
    """
    
    def __init__(self, posture_proxy, logger=None):
        """
        Inicializar helper de postura.
        
        Args:
            posture_proxy: Proxy ALRobotPosture
            logger: Logger opcional
        """
        self.posture = posture_proxy
        self.logger = logger or self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Crear logger de fallback."""
        class FallbackLogger:
            def info(self, msg): print("INFO [POSTURE] {}".format(msg))
            def error(self, msg): print("ERROR [POSTURE] {}".format(msg))
        return FallbackLogger()
    
    # Posturas válidas en NAO
    VALID_POSTURES = [
        "Stand", "StandInit", "StandZero",
        "Sit", "SitRelax",
        "Crouch",
        "LyingBelly", "LyingBack"
    ]
    
    def go_to_posture_safe(self, posture_name, speed=0.7):
        """
        Ir a postura de forma segura.
        
        Args:
            posture_name: Nombre de la postura
            speed: Velocidad (0.0 a 1.0)
            
        Returns:
            bool: True si tuvo éxito
        """
        if not self.posture:
            return False
        
        try:
            result = self.posture.goToPosture(str(posture_name), speed)
            self.logger.info("Postura '{}' alcanzada".format(posture_name))
            return result
        except Exception as e:
            self.logger.error("goToPosture '{}' falló: {}".format(posture_name, e))
            return False
    
    def get_current_posture(self):
        """
        Obtener postura actual.
        
        Returns:
            str: Nombre de la postura o "Unknown"
        """
        if not self.posture:
            return "Unknown"
        
        try:
            return self.posture.getPosture()
        except Exception:
            return "Unknown"
    
    def is_valid_posture(self, posture_name):
        """
        Verificar si una postura es válida.
        
        Args:
            posture_name: Nombre de la postura
            
        Returns:
            bool: True si es válida
        """
        return posture_name in self.VALID_POSTURES


class FallRecovery(object):
    """
    Helper para recuperación de caídas.
    """
    
    def __init__(self, motion_proxy, posture_proxy, memory_proxy, logger=None):
        """
        Inicializar helper de recuperación.
        
        Args:
            motion_proxy: Proxy ALMotion
            posture_proxy: Proxy ALRobotPosture
            memory_proxy: Proxy ALMemory
            logger: Logger opcional
        """
        self.motion = motion_proxy
        self.posture = posture_proxy
        self.memory = memory_proxy
        self.logger = logger or self._create_fallback_logger()
        self._subscribed = False
    
    def _create_fallback_logger(self):
        """Crear logger de fallback."""
        class FallbackLogger:
            def info(self, msg): print("INFO [FALL] {}".format(msg))
            def warning(self, msg): print("WARNING [FALL] {}".format(msg))
            def error(self, msg): print("ERROR [FALL] {}".format(msg))
        return FallbackLogger()
    
    def enable_fall_manager(self, enable=True):
        """
        Habilitar/deshabilitar fall manager de NAOqi.
        
        Args:
            enable: True para habilitar
            
        Returns:
            bool: True si tuvo éxito
        """
        if not self.motion:
            return False
        
        try:
            self.motion.setFallManagerEnabled(enable)
            self.logger.info("Fall Manager {}".format("ENABLED" if enable else "DISABLED"))
            return True
        except Exception as e:
            self.logger.error("Error configurando Fall Manager: {}".format(e))
            return False
    
    def get_fall_manager_state(self):
        """
        Obtener estado del fall manager.
        
        Returns:
            bool: True si está habilitado
        """
        if not self.motion:
            return False
        
        try:
            return self.motion.getFallManagerEnabled()
        except Exception:
            return False
    
    def recover_from_fall(self, speed=0.7):
        """
        Intentar recuperarse de una caída.
        
        Args:
            speed: Velocidad de recuperación
            
        Returns:
            bool: True si tuvo éxito
        """
        if not self.posture:
            return False
        
        try:
            self.logger.info("Intentando recuperación de caída...")
            result = self.posture.goToPosture("Stand", speed)
            if result:
                self.logger.info("Recuperación exitosa")
            else:
                self.logger.warning("Recuperación falló")
            return result
        except Exception as e:
            self.logger.error("Error en recuperación: {}".format(e))
            return False
