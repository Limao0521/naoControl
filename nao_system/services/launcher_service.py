#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
services.launcher_service

Launcher que controla el inicio y la alternancia de modos del sistema usando
sensores táctiles. Este encabezado es informativo y no modifica la lógica.
Fecha: 2025-09-08
"""

import time
import threading

class TouchLauncher(object):
    """Launcher que usa sensores táctiles para controlar el sistema"""
    
    def __init__(self):
        # Importar aquí para evitar dependencias circulares
        from ..core.system_manager import get_system_manager
        from ..services.adaptive_walk_service import AdaptiveWalkService
        from ..services.websocket_service import WebSocketService
        
        self.system_manager = get_system_manager()
        self.logger = self.system_manager.logger
        self.running = False
        self.services_active = False
        
        # Estado de sensores táctiles
        self.last_touch_state = {'middle': False, 'front': False, 'rear': False}
        self.touch_start_time = None
        self.required_hold_time = 3.0  # segundos
        
        # Registrar servicios adicionales
        self._register_additional_services()
        
        self.logger.info("TouchLauncher inicializado")
    
    def _register_additional_services(self):
        """Registrar servicios adicionales al sistema"""
        try:
            from ..services.adaptive_walk_service import AdaptiveWalkService
            from ..services.websocket_service import WebSocketService
            
            # Servicio de caminata adaptiva
            sensor_service = self.system_manager.get_service('sensors')
            adaptive_walk = AdaptiveWalkService(
                self.system_manager.nao_adapter, 
                sensor_service, 
                self.logger, 
                mode="production"
            )
            self.system_manager.register_service('adaptive_walk', adaptive_walk)
            
            # Servicio WebSocket
            websocket_service = WebSocketService(self.system_manager, self.logger)
            self.system_manager.register_service('websocket', websocket_service)
            
            self.logger.info("Servicios adicionales registrados")
            
        except Exception as e:
            self.logger.error("Error registrando servicios: {}".format(e))
    
    def _check_touch_sensors(self):
        """Verificar estado de sensores táctiles"""
        try:
            sensor_service = self.system_manager.get_service('sensors')
            if sensor_service:
                return sensor_service.get_touch_sensors()
            return {'middle': False, 'front': False, 'rear': False}
        except Exception as e:
            self.logger.error("Error leyendo sensores táctiles: {}".format(e))
            return {'middle': False, 'front': False, 'rear': False}
    
    def _handle_long_press(self):
        """Manejar presión larga del sensor táctil"""
        try:
            if self.services_active:
                self.logger.info("Preparando para Choregraphe...")
                self._prepare_for_choreographe()
            else:
                self.logger.info("Restaurando control del sistema...")
                self._restore_control_mode()
        except Exception as e:
            self.logger.error("Error manejando presión larga: {}".format(e))
    
    def _prepare_for_choreographe(self):
        """Preparar robot para Choregraphe"""
        try:
            # Detener caminata
            self.system_manager.stop_walk()
            
            # Detener servicios WebSocket y adaptivo
            for service_name in ['websocket', 'adaptive_walk']:
                service = self.system_manager.get_service(service_name)
                if service and hasattr(service, 'stop'):
                    service.stop()
            
            # Configurar robot
            if self.system_manager.nao_adapter.is_connected():
                self.system_manager.nao_adapter.safe_call('motion', 'setStiffnesses', 'Body', 1.0)
                self.system_manager.say("Listo para Choregraphe")
            
            self.services_active = False
            self.logger.info("Robot preparado para Choregraphe")
            
        except Exception as e:
            self.logger.error("Error preparando para Choregraphe: {}".format(e))
    
    def _restore_control_mode(self):
        """Restaurar modo de control"""
        try:
            # Configurar robot
            if self.system_manager.nao_adapter.is_connected():
                self.system_manager.set_posture("Stand")
                self.system_manager.nao_adapter.safe_call('motion', 'setMoveArmsEnabled', True, True)
            
            # Iniciar servicios
            for service_name in ['websocket', 'adaptive_walk']:
                service = self.system_manager.get_service(service_name)
                if service and hasattr(service, 'start'):
                    try:
                        service.start()
                        self.logger.info("Servicio '{}' iniciado".format(service_name))
                    except Exception as e:
                        self.logger.warning("Error iniciando '{}': {}".format(service_name, e))
            
            if self.system_manager.nao_adapter.is_connected():
                self.system_manager.say("Control del sistema restaurado")
            
            self.services_active = True
            self.logger.info("Control del sistema restaurado")
            
        except Exception as e:
            self.logger.error("Error restaurando control: {}".format(e))
    
    def _monitoring_loop(self):
        """Bucle principal de monitoreo"""
        self.logger.info("Iniciando monitoreo de sensores táctiles")
        
        while self.running:
            try:
                current_touch = self._check_touch_sensors()
                current_time = time.time()
                
                # Detectar inicio de presión
                if current_touch['middle'] and not self.last_touch_state['middle']:
                    self.touch_start_time = current_time
                    self.logger.debug("Inicio de presión detectado")
                
                # Detectar fin de presión
                elif not current_touch['middle'] and self.last_touch_state['middle']:
                    if self.touch_start_time:
                        duration = current_time - self.touch_start_time
                        if duration >= self.required_hold_time:
                            self.logger.info("Presión larga detectada ({:.1f}s)".format(duration))
                            self._handle_long_press()
                        else:
                            self.logger.debug("Presión corta ignorada ({:.1f}s)".format(duration))
                    
                    self.touch_start_time = None
                
                self.last_touch_state = current_touch
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error("Error en bucle de monitoreo: {}".format(e))
                time.sleep(1.0)
        
        self.logger.info("Monitoreo de sensores detenido")
    
    def start(self):
        """Iniciar el launcher"""
        try:
            if self.running:
                self.logger.warning("Launcher ya está ejecutándose")
                return
            
            self.running = True
            self.services_active = True
            
            # Inicializar servicios principales
            if not self.system_manager.start_services():
                self.logger.error("Error iniciando servicios del sistema")
                return
            
            # Iniciar servicios adicionales
            self._restore_control_mode()
            
            # Mensaje inicial
            if self.system_manager.nao_adapter.is_connected():
                self.system_manager.say("Sistema NAO modular iniciado")
            else:
                self.logger.info("Sistema iniciado en modo simulación")
            
            # Iniciar hilo de monitoreo
            self.monitor_thread = threading.Thread(target=self._monitoring_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            self.logger.info("TouchLauncher iniciado exitosamente")
            
            # Bucle principal
            try:
                while self.running:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                self.logger.info("Interrupción de usuario detectada")
            
        except Exception as e:
            self.logger.error("Error iniciando launcher: {}".format(e))
        finally:
            self.stop()
    
    def stop(self):
        """Detener el launcher"""
        try:
            self.running = False
            
            # Esperar a que termine el hilo de monitoreo
            if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            # Detener servicios del sistema
            self.system_manager.stop_services()
            
            self.logger.info("TouchLauncher detenido")
            
        except Exception as e:
            self.logger.error("Error deteniendo launcher: {}".format(e))
            
        except Exception as e:
            self.logger.error("Error registrando servicios adicionales: {}".format(e))
    
    def start(self):
        """Iniciar el launcher"""
        try:
            self.running = True
            
            # Mensaje inicial
            self.system_manager.say("Launcher iniciado")
            
            self.logger.info("TouchLauncher iniciado - Presiona cabeza 3 segundos para alternar")
            
            # Bucle principal
            self._main_loop()
            
        except KeyboardInterrupt:
            self.logger.info("Interrupción de usuario detectada")
        except Exception as e:
            self.logger.error("Error en TouchLauncher: {}".format(e))
        finally:
            self.cleanup()
    
    def _main_loop(self):
        """Bucle principal del launcher"""
        while self.running:
            try:
                # Leer sensores táctiles
                sensor_data = self.system_manager.get_sensor_data()
                
                if sensor_data and sensor_data.get('touch'):
                    touch_sensors = sensor_data['touch']
                    self._process_touch_sensors(touch_sensors)
                
                time.sleep(0.1)  # 100ms
                
            except Exception as e:
                self.logger.error("Error en main loop: {}".format(e))
                time.sleep(1.0)
    
    def _process_touch_sensors(self, touch_sensors):
        """Procesar estado de sensores táctiles"""
        try:
            middle_pressed = touch_sensors.get('middle', False)
            
            # Detectar inicio de pulsación
            if middle_pressed and not self.last_touch_state['middle']:
                self.touch_start_time = time.time()
                self.logger.debug("Sensor medio presionado")
            
            # Detectar fin de pulsación
            elif not middle_pressed and self.last_touch_state['middle']:
                if self.touch_start_time:
                    hold_duration = time.time() - self.touch_start_time
                    
                    if hold_duration >= self.required_hold_time:
                        self.logger.info("Pulsación larga detectada ({:.1f}s) - Alternando servicios".format(hold_duration))
                        self._toggle_services()
                    else:
                        self.logger.debug("Pulsación corta ({:.1f}s) - Ignorada".format(hold_duration))
                
                self.touch_start_time = None
            
            # Actualizar estado
            self.last_touch_state = touch_sensors.copy()
            
        except Exception as e:
            self.logger.error("Error procesando sensores táctiles: {}".format(e))
    
    def _toggle_services(self):
        """Alternar entre servicios activos y modo Choregraphe"""
        try:
            if self.services_active:
                # Detener servicios para Choregraphe
                self._stop_services()
                self.system_manager.say("Servicios detenidos. Listo para Choregraphe")
                self.logger.info("Servicios detenidos - Modo Choregraphe")
            else:
                # Iniciar servicios
                self._start_services()
                self.system_manager.say("Servicios iniciados. Control activo")
                self.logger.info("Servicios iniciados - Modo Control")
            
        except Exception as e:
            self.logger.error("Error alternando servicios: {}".format(e))
    
    def _start_services(self):
        """Iniciar servicios del sistema"""
        try:
            # Iniciar servicios adicionales
            websocket_service = self.system_manager.get_service('websocket')
            if websocket_service:
                websocket_service.start_server()
            
            # Marcar como activo
            self.services_active = True
            
            self.logger.info("Servicios iniciados exitosamente")
            
        except Exception as e:
            self.logger.error("Error iniciando servicios: {}".format(e))
            self.services_active = False
    
    def _stop_services(self):
        """Detener servicios del sistema"""
        try:
            # Detener caminata adaptiva si está activa
            adaptive_walk = self.system_manager.get_service('adaptive_walk')
            if adaptive_walk:
                adaptive_walk.stop_adaptive_walk()
            
            # Detener movimiento
            self.system_manager.stop_walk()
            
            # Detener WebSocket
            websocket_service = self.system_manager.get_service('websocket')
            if websocket_service:
                websocket_service.stop_server()
            
            # Configurar rigidez para Choregraphe
            if self.system_manager.nao_adapter.is_connected():
                self.system_manager.nao_adapter.safe_call('motion', 'setStiffnesses', "Body", 1.0)
            
            # Marcar como inactivo
            self.services_active = False
            
            self.logger.info("Servicios detenidos exitosamente")
            
        except Exception as e:
            self.logger.error("Error deteniendo servicios: {}".format(e))
    
    def stop(self):
        """Detener el launcher"""
        self.running = False
        self.logger.info("TouchLauncher detenido")
    
    def cleanup(self):
        """Limpiar recursos"""
        try:
            self.stop()
            if self.services_active:
                self._stop_services()
            
            self.logger.info("TouchLauncher limpiado")
            
        except Exception as e:
            self.logger.error("Error limpiando TouchLauncher: {}".format(e))

def main():
    """Función principal del launcher"""
    launcher = TouchLauncher()
    
    try:
        launcher.start()
    except KeyboardInterrupt:
        print("\nInterrupción de usuario")
    finally:
        launcher.cleanup()

if __name__ == "__main__":
    main()
