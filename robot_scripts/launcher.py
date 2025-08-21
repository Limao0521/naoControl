#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
launcher.py – Arranca/Detiene control_server.py + HTTP server
   con un long-press (>=3 s) del sensor táctil medio de la cabeza.
   Usa modelo basado en eventos con fallback a polling para máxima compatibilidad.
   Gestiona automáticamente modo Choregraphe vs modo WebSocket.
"""

import time
import subprocess
import signal
import os
import socket
import sys
from datetime import datetime

# Compatibilidad con Python 2 para TimeoutExpired
try:
    from subprocess import TimeoutExpired
except ImportError:
    # Python 2 no tiene TimeoutExpired, creamos una clase equivalente
    class TimeoutExpired(Exception):
        def __init__(self, cmd, timeout, output=None, stderr=None):
            self.cmd = cmd
            self.timeout = timeout
            self.output = output
            self.stderr = stderr

def wait_with_timeout(proc, timeout=5):
    """Función helper para wait con timeout compatible con Python 2."""
    import time
    start_time = time.time()
    while proc.poll() is None:
        if time.time() - start_time > timeout:
            raise TimeoutExpired(proc.args if hasattr(proc, 'args') else 'unknown', timeout)
        time.sleep(0.1)
    return proc.returncode

# Importaciones de NAOqi con manejo de errores
try:
    from naoqi import ALProxy
    NAOQI_BASIC = True
except ImportError:
    print("Error: NAOqi ALProxy no disponible")
    NAOQI_BASIC = False

try:
    import qi
    NAOQI_QI = True
except ImportError:
    NAOQI_QI = False

try:
    from naoqi import ALModule, ALBroker
    NAOQI_ADVANCED = True
except ImportError:
    NAOQI_ADVANCED = False

def log(level, message, module="LAUNCHER"):
    """Sistema de logging profesional."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Milisegundos
    level_colors = {
        "INFO": "",
        "WARN": "",
        "ERROR": "",
        "SUCCESS": "",
        "DEBUG": "",
        "TOUCH": "",
        "SYSTEM": ""
    }
    color = level_colors.get(level, "")
    print("[{}] [{}] [{}] {}{}".format(timestamp, level, module, color, message))

# — Configuración —
IP_NAO     = "127.0.0.1"
PORT_NAO   = 9559
PRESS_HOLD = 3.0            # segundos mínimos de pulsación (3 o más)
# Ajusta estas rutas según dónde tengas los scripts
CONTROL_PY = "/home/nao/scripts/control_server.py"
WEB_DIR    = "/home/nao/Webs/ControllerWebServer"
CAMERA_PY  = "/home/nao/scripts/video_stream.py"
HTTP_PORT  = "8000"

def get_server_ip():
    """Obtiene automáticamente la IP del servidor (gateway de la red local)."""
    try:
        # Crear un socket para obtener la IP local del NAO
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Conectar a una IP externa (no se envía tráfico real)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Obtener la IP del gateway (asumiendo que es la .1 de la red)
        ip_parts = local_ip.split('.')
        gateway_ip = '.'.join(ip_parts[:3]) + '.1'
        
        # Intentar hacer ping al gateway para verificar conectividad
        response = os.system("ping -c 1 " + gateway_ip + " > /dev/null 2>&1")
        if response == 0:
            return gateway_ip
        else:
            # Si el gateway no responde, usar la IP base de la red + .100
            return '.'.join(ip_parts[:3]) + '.100'
    except Exception:
        # IP por defecto si hay algún error
        return "192.168.1.100"

class RobustLauncher:
    """Launcher robusto que funciona con cualquier versión de NAOqi."""
    
    def __init__(self):
        self.services_running = False
        self.balancer_was_enabled = False
        self.pressed = False
        self.press_start = 0.0
        
        # Procesos
        self.server_proc = None
        self.http_proc = None
        self.camera_proc = None
        
        # Proxies NAOqi
        self.memory = None
        self.tts = None
        self.motion = None
        
        # Modo de funcionamiento
        self.use_events = False
        self.event_handler = None
        
        # Debug para sensores táctiles
        self.debug_sensors = True
        self.last_sensor_state = {"middle": 0.0, "front": 0.0, "rear": 0.0}
        
        log("SYSTEM", "Iniciando NAO Control Launcher...")
        self.initialize()
    
    def initialize(self):
        """Inicializa el launcher con el mejor método disponible."""
        if not NAOQI_BASIC:
            log("ERROR", "NAOqi no disponible - no se puede continuar", "LAUNCHER")
            return False
        
        # Paso 1: Crear proxies básicos
        try:
            log("INFO", "Conectando a NAOqi...", "LAUNCHER")
            self.memory = ALProxy("ALMemory", IP_NAO, PORT_NAO)
            self.tts = ALProxy("ALTextToSpeech", IP_NAO, PORT_NAO)
            self.motion = ALProxy("ALMotion", IP_NAO, PORT_NAO)
            log("SUCCESS", "Conexión básica a NAOqi establecida", "LAUNCHER")
            
            # Test inicial de sensores táctiles
            self.test_touch_sensors()
            
        except Exception as e:
            log("ERROR", "Error conectando a NAOqi: " + str(e), "LAUNCHER")
            return False
        
        # Paso 2: Intentar sistema de eventos (comentado para usar solo polling por ahora)
        log("INFO", "Usando modo polling para máxima compatibilidad", "LAUNCHER")
        self.use_events = False
        
        # Mensaje inicial
        try:
            self.tts.say("Launcher iniciado. Pulsa mi cabeza tres segundos para alternar modos")
            log("SUCCESS", "Mensaje inicial enviado", "LAUNCHER")
        except Exception as e:
            log("WARN", "No se pudo enviar mensaje inicial: " + str(e), "LAUNCHER")
        
        return True
    
    def test_touch_sensors(self):
        """Prueba inicial de los sensores táctiles."""
        try:
            log("DEBUG", "Probando sensores táctiles...", "LAUNCHER")
            middle = self.memory.getData("MiddleTactilTouched")
            front = self.memory.getData("FrontTactilTouched")
            rear = self.memory.getData("RearTactilTouched")
            
            # Convertir None a 0.0 para compatibilidad
            middle = 0.0 if middle is None else float(middle)
            front = 0.0 if front is None else float(front)
            rear = 0.0 if rear is None else float(rear)
            
            log("DEBUG", "Estados sensores - Medio: {}, Frontal: {}, Trasero: {}".format(middle, front, rear), "LAUNCHER")
            
            # Actualizar estado base
            self.last_sensor_state = {
                "middle": middle,
                "front": front,
                "rear": rear
            }
            
            log("SUCCESS", "Sensores táctiles funcionando correctamente", "LAUNCHER")
            return True
            
        except Exception as e:
            log("ERROR", "Error probando sensores táctiles: " + str(e), "LAUNCHER")
            return False
    
    def setup_event_system(self):
        """Configura el sistema de eventos si es posible."""
        if not (NAOQI_QI and NAOQI_ADVANCED):
            raise Exception("Módulos qi/ALModule no disponibles")
        
        # Intentar diferentes métodos de conexión
        session = None
        
        # Método 1: qi.Application con parámetros
        try:
            app = qi.Application(["TouchEventHandler", "--qi-url=tcp://" + IP_NAO + ":" + str(PORT_NAO)])
            app.start()
            session = app.session
            print("Conectado con qi.Application")
        except Exception as e1:
            print("qi.Application falló: " + str(e1))
            
            # Método 2: ALBroker tradicional
            try:
                broker = ALBroker("TouchEventBroker", "0.0.0.0", 0, IP_NAO, PORT_NAO)
                session = broker
                print("Conectado con ALBroker")
            except Exception as e2:
                print("ALBroker falló: " + str(e2))
                raise Exception("No se pudo establecer sesión para eventos")
        
        # Crear manejador de eventos
        self.event_handler = TouchEventHandler("TouchEventHandler", session, self)
        print("Manejador de eventos creado")
    
    def prepare_for_choreographe(self):
        """Prepara el robot para usar Choregraphe."""
        log("INFO", "Preparando para modo Choregraphe...", "CHOREOGRAPHE")
        
        errors = []
        success_steps = 0
        total_steps = 4
        
        try:
            # Paso 1: Detener servicios de manera forzada si es necesario
            log("INFO", "Paso 1/4: Deteniendo servicios...", "CHOREOGRAPHE")
            try:
                self.stop_services()
                success_steps += 1
                log("SUCCESS", "Servicios detenidos correctamente", "CHOREOGRAPHE")
            except Exception as e:
                error_msg = "Error deteniendo servicios: " + str(e)
                log("WARN", error_msg, "CHOREOGRAPHE")
                errors.append(error_msg)
            
            # Paso 2: Configurar balancer de manera segura
            log("INFO", "Paso 2/4: Configurando Whole-Body Balancer...", "CHOREOGRAPHE")
            if self.motion:
                try:
                    # Intentar leer estado actual del balancer
                    try:
                        self.balancer_was_enabled = self.motion.wbEnable()
                        log("DEBUG", "Estado del balancer guardado: {}".format(self.balancer_was_enabled), "CHOREOGRAPHE")
                    except Exception as e:
                        log("WARN", "No se pudo leer estado del balancer, usando False por defecto", "CHOREOGRAPHE")
                        self.balancer_was_enabled = False
                    
                    # Habilitar balancer para Choregraphe
                    self.motion.wbEnable(True)
                    success_steps += 1
                    log("SUCCESS", "Whole-Body Balancer habilitado", "CHOREOGRAPHE")
                    
                except Exception as e:
                    error_msg = "Error configurando balancer: " + str(e)
                    log("ERROR", error_msg, "CHOREOGRAPHE")
                    errors.append(error_msg)
            else:
                error_msg = "ALMotion no disponible"
                log("ERROR", error_msg, "CHOREOGRAPHE")
                errors.append(error_msg)
            
            # Paso 3: Asegurar rigidez corporal
            log("INFO", "Paso 3/4: Configurando rigidez...", "CHOREOGRAPHE")
            if self.motion:
                try:
                    self.motion.setStiffnesses("Body", 1.0)
                    success_steps += 1
                    log("SUCCESS", "Rigidez corporal configurada", "CHOREOGRAPHE")
                except Exception as e:
                    error_msg = "Error configurando rigidez: " + str(e)
                    log("WARN", error_msg, "CHOREOGRAPHE")
                    errors.append(error_msg)
            
            # Paso 4: Actualizar estado interno
            log("INFO", "Paso 4/4: Actualizando estado...", "CHOREOGRAPHE")
            try:
                self.services_running = False
                success_steps += 1
                log("SUCCESS", "Estado interno actualizado", "CHOREOGRAPHE")
            except Exception as e:
                error_msg = "Error actualizando estado: " + str(e)
                log("WARN", error_msg, "CHOREOGRAPHE")
                errors.append(error_msg)
            
            # Mensaje final basado en el éxito
            if success_steps >= 3:  # Al menos 3 de 4 pasos exitosos
                if self.tts:
                    if errors:
                        self.tts.say("Robot preparado para Choregraphe con algunas advertencias")
                    else:
                        self.tts.say("Robot preparado para Choregraphe")
                
                log("SUCCESS", "Robot preparado para Choregraphe ({}/{} pasos exitosos)".format(success_steps, total_steps), "CHOREOGRAPHE")
                if errors:
                    log("WARN", "Advertencias encontradas:", "CHOREOGRAPHE")
                    for error in errors:
                        log("WARN", "  - " + error, "CHOREOGRAPHE")
                
                return True
            else:
                # Fallo crítico
                if self.tts:
                    self.tts.say("Error preparando para Choregraphe")
                
                log("ERROR", "Error crítico preparando para Choregraphe ({}/{} pasos fallaron)".format(total_steps - success_steps, total_steps), "CHOREOGRAPHE")
                for error in errors:
                    log("ERROR", "  - " + error, "CHOREOGRAPHE")
                
                return False
            
        except Exception as e:
            error_msg = "Error fatal en prepare_for_choreographe: " + str(e)
            log("ERROR", error_msg, "CHOREOGRAPHE")
            
            if self.tts:
                self.tts.say("Error fatal preparando para Choregraphe")
            
            return False
    
    def restore_control_mode(self):
        """Restaura el modo de control WebSocket."""
        log("INFO", "Restaurando modo control...", "CONTROL")
        
        errors = []
        success_steps = 0
        total_steps = 3
        
        try:
            # Paso 1: Restaurar configuración del balancer
            log("INFO", "Paso 1/3: Restaurando Whole-Body Balancer...", "CONTROL")
            if self.motion:
                try:
                    self.motion.wbEnable(self.balancer_was_enabled)
                    success_steps += 1
                    log("SUCCESS", "Balancer restaurado a: {}".format(self.balancer_was_enabled), "CONTROL")
                except Exception as e:
                    error_msg = "Error restaurando balancer: " + str(e)
                    log("WARN", error_msg, "CONTROL")
                    errors.append(error_msg)
                    # Intentar configuración por defecto
                    try:
                        self.motion.wbEnable(False)  # Configuración típica para control
                        log("SUCCESS", "Balancer configurado con valor por defecto (False)", "CONTROL")
                        success_steps += 1
                    except Exception:
                        log("ERROR", "No se pudo configurar el balancer", "CONTROL")
            else:
                error_msg = "ALMotion no disponible para restaurar balancer"
                log("ERROR", error_msg, "CONTROL")
                errors.append(error_msg)
            
            # Paso 2: Iniciar servicios
            log("INFO", "Paso 2/3: Iniciando servicios...", "CONTROL")
            try:
                service_success = self.start_services()
                if service_success:
                    success_steps += 1
                    log("SUCCESS", "Servicios iniciados correctamente", "CONTROL")
                else:
                    error_msg = "Algunos servicios no pudieron iniciarse"
                    log("WARN", error_msg, "CONTROL")
                    errors.append(error_msg)
            except Exception as e:
                error_msg = "Error iniciando servicios: " + str(e)
                log("ERROR", error_msg, "CONTROL")
                errors.append(error_msg)
            
            # Paso 3: Actualizar estado interno
            log("INFO", "Paso 3/3: Actualizando estado...", "CONTROL")
            try:
                # Solo marcar como running si al menos algunos servicios están activos
                if self.server_proc or self.camera_proc or self.http_proc:
                    self.services_running = True
                    success_steps += 1
                    log("SUCCESS", "Estado actualizado - servicios activos", "CONTROL")
                else:
                    self.services_running = False
                    error_msg = "Ningún servicio está ejecutándose"
                    log("WARN", error_msg, "CONTROL")
                    errors.append(error_msg)
            except Exception as e:
                error_msg = "Error actualizando estado: " + str(e)
                log("ERROR", error_msg, "CONTROL")
                errors.append(error_msg)
            
            # Mensaje final basado en el éxito
            if success_steps >= 2:  # Al menos 2 de 3 pasos exitosos
                if self.tts:
                    if errors:
                        self.tts.say("Modo de control restaurado con algunas advertencias")
                    else:
                        self.tts.say("Modo de control restaurado")
                
                log("SUCCESS", "Modo control restaurado ({}/{} pasos exitosos)".format(success_steps, total_steps), "CONTROL")
                if errors:
                    log("WARN", "Advertencias encontradas:", "CONTROL")
                    for error in errors:
                        log("WARN", "  - " + error, "CONTROL")
                
                return True
            else:
                # Fallo crítico
                if self.tts:
                    self.tts.say("Error restaurando modo de control")
                
                log("ERROR", "Error crítico restaurando modo control ({}/{} pasos fallaron)".format(total_steps - success_steps, total_steps), "CONTROL")
                for error in errors:
                    log("ERROR", "  - " + error, "CONTROL")
                
                return False
            
        except Exception as e:
            error_msg = "Error fatal en restore_control_mode: " + str(e)
            log("ERROR", error_msg, "CONTROL")
            
            if self.tts:
                self.tts.say("Error fatal restaurando modo control")
            
            return False
    
    def handle_long_press(self):
        """Maneja la pulsación larga del sensor táctil."""
        log("INFO", "Alternando modo...", "LAUNCHER")
        
        if self.services_running:
            log("INFO", "Cambiando a modo Choregraphe...", "LAUNCHER")
            if self.tts:
                self.tts.say("Cambiando a modo Choregraphe")
            success = self.prepare_for_choreographe()
            if success:
                log("SUCCESS", "Cambio a modo Choregraphe completado", "LAUNCHER")
            else:
                log("ERROR", "Cambio a modo Choregraphe falló - manteniendo estado actual", "LAUNCHER")
        else:
            log("INFO", "Cambiando a modo control...", "LAUNCHER")
            if self.tts:
                self.tts.say("Iniciando modo control")
            success = self.restore_control_mode()
            if success:
                log("SUCCESS", "Cambio a modo control completado", "LAUNCHER")
            else:
                log("ERROR", "Cambio a modo control falló - manteniendo estado actual", "LAUNCHER")
    
    def start_services(self):
        """Inicia todos los servicios de control."""
        log("INFO", "Iniciando servicios...", "SERVICES")
        services_started = 0
        total_services = 3
        
        # Control server
        if not self.server_proc:
            try:
                self.server_proc = subprocess.Popen(["python2", CONTROL_PY])
                time.sleep(3)
                
                if self.server_proc.poll() is None:
                    services_started += 1
                    log("SUCCESS", "Control server iniciado", "SERVICES")
                else:
                    self.server_proc = None
                    log("ERROR", "Control server falló", "SERVICES")
            except Exception as e:
                log("ERROR", "Error iniciando control server: " + str(e), "SERVICES")
                self.server_proc = None
        else:
            services_started += 1
        
        # Cámara
        if not self.camera_proc:
            try:
                server_ip = get_server_ip()
                self.camera_proc = subprocess.Popen([
                    "python2", CAMERA_PY,
                    "--server_ip", server_ip,
                    "--nao_ip", IP_NAO,
                    "--nao_port", str(PORT_NAO),
                    "--http_port", "8080"
                ])
                time.sleep(2)
                
                if self.camera_proc.poll() is None:
                    services_started += 1
                    log("SUCCESS", "Cámara iniciada", "SERVICES")
                else:
                    self.camera_proc = None
                    log("ERROR", "Cámara falló", "SERVICES")
            except Exception as e:
                log("ERROR", "Error iniciando cámara: " + str(e), "SERVICES")
                self.camera_proc = None
        else:
            services_started += 1
        
        # HTTP server
        if not self.http_proc:
            try:
                self.http_proc = subprocess.Popen(
                    ["python2", "-m", "SimpleHTTPServer", HTTP_PORT],
                    cwd=WEB_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                time.sleep(1)
                
                if self.http_proc.poll() is None:
                    services_started += 1
                    log("SUCCESS", "HTTP server iniciado", "SERVICES")
                else:
                    self.http_proc = None
                    log("ERROR", "HTTP server falló", "SERVICES")
            except Exception as e:
                log("ERROR", "Error iniciando HTTP server: " + str(e), "SERVICES")
                self.http_proc = None
        else:
            services_started += 1
        
        success = (services_started == total_services)
        log("INFO", "Servicios iniciados: {}/{}".format(services_started, total_services), "SERVICES")
        return success
    
    def stop_services(self):
        """Detiene todos los servicios."""
        log("INFO", "Deteniendo servicios...", "SERVICES")
        
        processes = [
            ("HTTP server", self.http_proc),
            ("Cámara", self.camera_proc),
            ("Control server", self.server_proc)
        ]
        
        for name, proc in processes:
            if proc:
                try:
                    log("INFO", "Deteniendo {}...".format(name), "SERVICES")
                    proc.terminate()
                    wait_with_timeout(proc, 5)
                    log("SUCCESS", "{} detenido".format(name), "SERVICES")
                except TimeoutExpired:
                    log("WARN", "Forzando cierre de {}...".format(name), "SERVICES")
                    proc.kill()
                except Exception as e:
                    log("ERROR", "Error deteniendo {}: {}".format(name, str(e)), "SERVICES")
        
        self.http_proc = None
        self.camera_proc = None
        self.server_proc = None
        
        time.sleep(2)
        print("Todos los servicios detenidos")
    
    def run_polling_mode(self):
        """Ejecuta el launcher en modo polling."""
        log("INFO", "Iniciando modo polling...", "LAUNCHER")
        log("INFO", "Presiona sensor táctil medio por 3+ segundos para alternar modos", "LAUNCHER")
        
        sensor_check_counter = 0
        
        while True:
            try:
                # Leer sensores táctiles con manejo de errores
                try:
                    middle_touch = self.memory.getData("MiddleTactilTouched")
                    front_touch = self.memory.getData("FrontTactilTouched")
                    rear_touch = self.memory.getData("RearTactilTouched")
                    
                    # Convertir None a 0.0 para compatibilidad
                    middle_touch = 0.0 if middle_touch is None else float(middle_touch)
                    front_touch = 0.0 if front_touch is None else float(front_touch)
                    rear_touch = 0.0 if rear_touch is None else float(rear_touch)
                    
                except Exception as e:
                    log("ERROR", "Error leyendo sensores: " + str(e), "LAUNCHER")
                    time.sleep(0.5)
                    continue
                
                # Debug cada 50 iteraciones (5 segundos)
                sensor_check_counter += 1
                if sensor_check_counter % 50 == 0:
                    log("DEBUG", "Estados sensores - M:{} F:{} R:{}".format(middle_touch, front_touch, rear_touch), "LAUNCHER")
                
                # Detectar cambios en sensores
                current_state = {
                    "middle": middle_touch,
                    "front": front_touch,
                    "rear": rear_touch
                }
                
                # Reportar cambios de estado
                for sensor, value in current_state.items():
                    if value != self.last_sensor_state[sensor]:
                        if value == 1.0:
                            log("TOUCH", "Sensor {} presionado".format(sensor), "LAUNCHER")
                        else:
                            log("TOUCH", "Sensor {} liberado".format(sensor), "LAUNCHER")
                        self.last_sensor_state[sensor] = value
                
                # Solo sensor medio presionado (otros deben estar en 0)
                only_middle_pressed = (middle_touch == 1.0 and front_touch == 0.0 and rear_touch == 0.0)
                
                # Inicio de pulsación
                if only_middle_pressed and not self.pressed:
                    self.pressed = True
                    self.press_start = time.time()
                    log("TOUCH", "Inicio de pulsación larga detectado", "LAUNCHER")
                
                # Mostrar progreso durante pulsación
                elif self.pressed and only_middle_pressed:
                    elapsed = time.time() - self.press_start
                    if elapsed >= 1.0 and int(elapsed) != int(elapsed - 0.1):  # Cada segundo
                        log("TOUCH", "Pulsación en progreso: {:.1f}s / 3.0s".format(elapsed), "LAUNCHER")
                
                # Fin de pulsación (sensor liberado o otro sensor presionado)
                elif self.pressed and (middle_touch == 0.0 or front_touch == 1.0 or rear_touch == 1.0):
                    elapsed = time.time() - self.press_start
                    self.pressed = False
                    
                    if elapsed >= PRESS_HOLD:
                        log("SUCCESS", "Pulsación larga completada ({:.1f}s)".format(elapsed), "LAUNCHER")
                        self.handle_long_press()
                    else:
                        log("WARN", "Pulsación demasiado corta ({:.1f}s) - se necesitan 3.0s+".format(elapsed), "LAUNCHER")
                
                time.sleep(0.1)  # Polling optimizado
                
            except KeyboardInterrupt:
                log("INFO", "Interrupción detectada", "LAUNCHER")
                break
            except Exception as e:
                log("ERROR", "Error en bucle principal: " + str(e), "LAUNCHER")
                time.sleep(1)
    
    def run_event_mode(self):
        """Ejecuta el launcher en modo eventos."""
        print("Iniciando modo eventos...")
        print("Presiona sensor táctil medio por 5+ segundos para alternar modos")
        
        try:
            # En modo eventos, el loop es manejado por qi
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Interrupción detectada")
    
    def run(self):
        """Ejecuta el launcher usando el mejor método disponible."""
        if not self.memory:
            print("No se puede ejecutar sin conexión a NAOqi")
            return
        
        try:
            if self.use_events:
                self.run_event_mode()
            else:
                self.run_polling_mode()
        except Exception as e:
            print("Error ejecutando launcher: " + str(e))
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpia recursos al salir."""
        print("Limpiando recursos...")
        
        if self.event_handler and hasattr(self.event_handler, 'unsubscribe_from_touch_events'):
            try:
                self.event_handler.unsubscribe_from_touch_events()
            except Exception:
                pass
        
        self.stop_services()

class TouchEventHandler(ALModule):
    """Manejador de eventos táctiles para modo avanzado."""
    
    def __init__(self, name, session, launcher):
        if NAOQI_ADVANCED:
            ALModule.__init__(self, name)
        
        self.name = name
        self.session = session
        self.launcher = launcher
        self.memory = session.service("ALMemory") if hasattr(session, 'service') else ALProxy("ALMemory", IP_NAO, PORT_NAO)
        
        # Suscribirse a eventos
        self.subscribe_to_touch_events()
    
    def subscribe_to_touch_events(self):
        """Suscribe a los eventos de los sensores táctiles."""
        try:
            self.memory.subscribeToEvent("MiddleTactilTouched", self.name, "onMiddleTouch")
            self.memory.subscribeToEvent("FrontTactilTouched", self.name, "onFrontTouch")
            self.memory.subscribeToEvent("RearTactilTouched", self.name, "onRearTouch")
            print("Suscripciones a eventos configuradas")
        except Exception as e:
            print("Error configurando eventos: " + str(e))
            raise
    
    def unsubscribe_from_touch_events(self):
        """Desuscribe de los eventos táctiles."""
        try:
            self.memory.unsubscribeToEvent("MiddleTactilTouched", self.name)
            self.memory.unsubscribeToEvent("FrontTactilTouched", self.name)
            self.memory.unsubscribeToEvent("RearTactilTouched", self.name)
            print("Eventos desuscritos")
        except Exception as e:
            print("Error desuscribiendo eventos: " + str(e))
    
    def onMiddleTouch(self, *_args):
        """Callback para sensor medio."""
        self.handle_touch_event("middle")
    
    def onFrontTouch(self, *_args):
        """Callback para sensor frontal."""
        self.handle_touch_event("front")
    
    def onRearTouch(self, *_args):
        """Callback para sensor trasero."""
        self.handle_touch_event("rear")
    
    def handle_touch_event(self, sensor):
        """Maneja eventos de toque."""
        try:
            # Leer estado de sensores
            middle_touch = self.memory.getData("MiddleTactilTouched")
            front_touch = self.memory.getData("FrontTactilTouched")
            rear_touch = self.memory.getData("RearTactilTouched")
            
            only_middle_pressed = (middle_touch == 1 and front_touch == 0 and rear_touch == 0)
            
            # Inicio de pulsación
            if only_middle_pressed and not self.launcher.pressed:
                self.launcher.pressed = True
                self.launcher.press_start = time.time()
                print("Pulsación iniciada (eventos)...")
            
            # Fin de pulsación
            elif middle_touch == 0 and self.launcher.pressed:
                elapsed = time.time() - self.launcher.press_start
                self.launcher.pressed = False
                
                if elapsed >= PRESS_HOLD:
                    print("Pulsación larga detectada ({:.1f}s)".format(elapsed))
                    self.launcher.handle_long_press()
                else:
                    print("Pulsación corta ({:.1f}s) - se necesitan 3s+".format(elapsed))
            
            # Cancelar por otros sensores
            elif self.launcher.pressed and (front_touch == 1 or rear_touch == 1):
                self.launcher.pressed = False
                print("Pulsación cancelada")
                
        except Exception as e:
            print("Error en handle_touch_event: " + str(e))

# Variable global para el launcher
launcher = None

def cleanup(sig, frame):
    """Manejador de señales para limpiar al cerrar."""
    global launcher
    
    print("Señal de terminación recibida")
    
    if launcher:
        launcher.cleanup()
    
    print("Limpieza completada")
    os._exit(0)

# Captura Ctrl+C, SIGTERM, etc.
signal.signal(signal.SIGINT,  cleanup)
signal.signal(signal.SIGTERM, cleanup)

def main():
    """Función principal robusta con múltiples métodos de inicialización."""
    global launcher
    
    print("=" * 60)
    print("NAO Control Launcher v2.0 - Robusto y Compatible")
    print("=" * 60)
    print("Capacidades detectadas:")
    print("   - NAOqi ALProxy: " + ("SI" if NAOQI_BASIC else "NO"))
    print("   - qi module: " + ("SI" if NAOQI_QI else "NO"))
    print("   - ALModule/ALBroker: " + ("SI" if NAOQI_ADVANCED else "NO"))
    print()
    
    try:
        # Crear el launcher robusto
        launcher = RobustLauncher()
        
        # Verificar que se inicializó correctamente
        if not launcher.memory:
            print("Error: No se pudo establecer conexión con NAOqi")
            print("Verifica que NAOqi esté ejecutándose y la IP sea correcta")
            return
        
        # Mostrar modo de operación
        if launcher.use_events:
            print("Modo: Eventos (óptimo - cero CPU cuando inactivo)")
        else:
            print("Modo: Polling (compatible - bajo CPU)")
        
        print()
        print("Launcher iniciado exitosamente!")
        print("Presiona el sensor táctil medio por 3+ segundos para alternar modos:")
        print("   Servicios activos → Preparar para Choregraphe")
        print("   Choregraphe listo → Restaurar servicios")
        print()
        
        # Mensaje inicial de TTS indicando estado
        try:
            if launcher.services_running:
                launcher.tts.say("Sistema iniciado en modo control. Presiona mi cabeza tres segundos para cambiar a Choregraphe")
            else:
                launcher.tts.say("Sistema iniciado. Presiona mi cabeza tres segundos para activar modo control")
        except Exception as e:
            print("Aviso: No se pudo enviar mensaje inicial de TTS: " + str(e))
        
        # Ejecutar el launcher
        launcher.run()
        
    except KeyboardInterrupt:
        print("Interrupción de usuario detectada")
    except Exception as e:
        print("Error fatal en main: " + str(e))
        print("Verifica la conexión a NAOqi y los archivos de configuración")
    finally:
        if launcher:
            launcher.cleanup()

if __name__ == "__main__":
    main()
