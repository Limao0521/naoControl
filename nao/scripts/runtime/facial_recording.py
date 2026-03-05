#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
facial_recording.py - Sistema de grabación de video con reconocimiento facial para NAO

Funcionalidad:
1. Al iniciar, el robot busca un rostro usando reconocimiento facial
2. Al detectar un rostro, el ojo izquierdo se pone en verde (confirmación)
3. Al presionar el bumper derecho, inicia la grabación (ojo derecho en verde)
4. Al presionar nuevamente el bumper derecho, detiene la grabación
5. Usa la misma calidad de video que video_stream.py

Uso:
    python facial_recording.py --nao_ip <IP_DEL_ROBOT>

Ejemplo:
    python facial_recording.py --nao_ip 192.168.1.100
"""

import argparse
import sys
import time
import os
from datetime import datetime
import numpy as np
import cv2
from naoqi import ALProxy

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("FACIAL_REC")
except ImportError:
    # Fallback si no está disponible
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [FACIAL_REC] {}".format(msg))
        def info(self, msg): print("INFO [FACIAL_REC] {}".format(msg))
        def warning(self, msg): print("WARNING [FACIAL_REC] {}".format(msg))
        def error(self, msg): print("ERROR [FACIAL_REC] {}".format(msg))
        def critical(self, msg): print("CRITICAL [FACIAL_REC] {}".format(msg))
    logger = FallbackLogger()


class FacialRecordingSystem:
    """Sistema de grabación de video con reconocimiento facial"""
    
    def __init__(self, nao_ip, nao_port=9559, fps=13, resolution=1, auto_record_enabled=False):
        """
        Inicializar el sistema
        
        Args:
            nao_ip: IP del robot NAO
            nao_port: Puerto NAOqi (default: 9559)
            fps: Frames por segundo (default: 30)
            resolution: Resolución de video (0=160x120, 1=320x240, 2=640x480, 3=1280x960)
            auto_record_enabled: Si False, no inicia/detiene grabación según detección de rostro
        """
        self.nao_ip = nao_ip
        self.nao_port = nao_port
        self.fps = fps
        self.resolution = resolution
        
        # Estado del sistema
        self.face_detected = False
        self.face_currently_visible = False  # Para tracking continuo del rostro
        self.is_recording = False
        self.video_writer = None
        self.recording_filename = None
        
        # Sistema de grabación automática por detección continua
        self.auto_record_enabled = auto_record_enabled  # Habilitar grabación automática (puede desactivarse)
        self.auto_record_threshold = 5.0  # Segundos de detección continua para iniciar grabación
        self.face_visible_start_time = None  # Tiempo cuando empezó a ver el rostro
        self.auto_record_triggered = False  # Si ya se activó la grabación automática
        
        # Sistema de parada automática por pérdida de rostro
        self.auto_stop_threshold = 5.0  # Segundos sin rostro para detener grabación
        self.face_lost_start_time = None  # Tiempo cuando se perdió el rostro durante grabación
        
        # Sistema de grabación múltiple (15 videos de 3 segundos)
        self.bumper_press_time = None  # Tiempo cuando se presionó el bumper
        self.multi_video_recording = False  # Si estamos en modo de grabación múltiple
        self.multi_video_mode_active = False  # Si se está esperando los 5 segundos o grabando
        self.videos_recorded = 0  # Contador de videos grabados (máximo 15)
        self.video_start_time = None  # Tiempo cuando empezó el video actual
        self.video_duration = 6.0  # Duración de cada video en segundos
        self.max_videos = 16  # Máximo número de videos a grabar
        self.wait_before_recording = 5.0  # Segundos a esperar antes de empezar a grabar
        
        # Configuración de cámara (igual que video_stream.py)
        self.colorspace = 13  # BGR - compatible con OpenCV
        self.client_name = "facial_recording_client"
        
        # Resoluciones disponibles
        self.resolution_map = {
            0: (160, 120),
            1: (320, 240),
            2: (640, 480),
            3: (1280, 960)
        }
        
        # Parámetros de compresión JPEG (igual que video_stream.py)
        self.jpeg_params = [
            int(cv2.IMWRITE_JPEG_QUALITY), 75,
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
            int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1
        ]
        
        # Inicializar proxies NAOqi
        logger.info("Conectando al robot NAO en {}:{}".format(nao_ip, nao_port))
        try:
            self.video_proxy = ALProxy('ALVideoDevice', nao_ip, nao_port)
            self.face_detection = ALProxy('ALFaceDetection', nao_ip, nao_port)
            self.leds = ALProxy('ALLeds', nao_ip, nao_port)
            self.memory = ALProxy('ALMemory', nao_ip, nao_port)
            self.tts = ALProxy('ALTextToSpeech', nao_ip, nao_port)
            self.motion = ALProxy('ALMotion', nao_ip, nao_port)
            
            # Proxy para postura del robot
            try:
                self.posture = ALProxy('ALRobotPosture', nao_ip, nao_port)
                logger.info("ALRobotPosture proxy inicializado")
            except Exception as e:
                logger.warning("ALRobotPosture no disponible: {}".format(e))
                self.posture = None
            
            # Proxy para Face Tracker (opcional - puede no estar disponible)
            try:
                self.face_tracker = ALProxy('ALFaceTracker', nao_ip, nao_port)
                self.use_face_tracker = True
                logger.info("ALFaceTracker proxy inicializado")
            except Exception as e:
                logger.warning("ALFaceTracker no disponible, usando seguimiento manual: {}".format(e))
                self.face_tracker = None
                self.use_face_tracker = False
            
            # Proxy para Autonomous Life (para apagarlo)
            try:
                self.autonomous_life = ALProxy('ALAutonomousLife', nao_ip, nao_port)
                logger.info("ALAutonomousLife proxy inicializado")
            except Exception as e:
                logger.warning("No se pudo conectar a ALAutonomousLife: {}".format(e))
                self.autonomous_life = None
            
            logger.info("Todos los proxies NAOqi inicializados correctamente")
        except Exception as e:
            logger.critical("Error inicializando proxies NAOqi: {}".format(e))
            raise
        
        # Suscribir a eventos del bumper
        self.setup_bumper_events()
        
        # Configurar directorio de grabaciones
        self.recordings_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../data/video_record'
        )
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)
            logger.info("Directorio de grabaciones creado: {}".format(self.recordings_dir))
    
    def setup_bumper_events(self):
        """Configurar eventos del bumper derecho"""
        logger.info("Configurando eventos del bumper derecho...")
        # El bumper derecho es "RightBumperPressed"
        self.bumper_event = "RightBumperPressed"
    
    def disable_autonomous_life(self):
        """Desactivar el sistema Autonomous Life del robot y ponerlo en Stand"""
        if self.autonomous_life is None:
            logger.warning("ALAutonomousLife no disponible")
        else:
            try:
                current_state = self.autonomous_life.getState()
                logger.info("Estado actual de Autonomous Life: {}".format(current_state))
                
                if current_state != "disabled":
                    logger.info("Desactivando Autonomous Life...")
                    self.autonomous_life.setState("disabled")
                    time.sleep(1)  # Esperar a que se desactive completamente
                    logger.info("Autonomous Life desactivado")
                else:
                    logger.info("Autonomous Life ya estaba desactivado")
                    
            except Exception as e:
                logger.error("Error desactivando Autonomous Life: {}".format(e))
        
        # Poner el robot en pose Stand con todo el cuerpo rígido
        try:
            logger.info("Poniendo robot en posición Stand...")
            
            # Activar stiffness en todo el cuerpo
            self.motion.setStiffnesses("Body", 1.0)
            logger.info("Stiffness activado en todo el cuerpo")
            
            # Despertar al robot
            self.motion.wakeUp()
            time.sleep(0.5)
            
            # Ir a postura Stand
            if self.posture:
                self.posture.goToPosture("Stand", 0.5)
                logger.info("Robot en posición Stand")
            else:
                logger.warning("No se pudo ir a postura Stand (ALRobotPosture no disponible)")
            
        except Exception as e:
            logger.error("Error poniendo robot en Stand: {}".format(e))
    
    def enable_head_tracking(self):
        """Habilitar el seguimiento de rostro solo con la cabeza"""
        try:
            # El cuerpo ya está rígido desde disable_autonomous_life
            # Solo configuramos el Face Tracker para usar solo la cabeza
            if self.use_face_tracker and self.face_tracker:
                self.face_tracker.setWholeBodyOn(False)
                logger.info("Face Tracker configurado para usar solo la cabeza")
            else:
                logger.info("Usando seguimiento manual de cabeza")
            
        except Exception as e:
            logger.error("Error configurando seguimiento de cabeza: {}".format(e))
    
    def start_face_tracking(self):
        """Iniciar el seguimiento de rostro con la cabeza"""
        if self.use_face_tracker and self.face_tracker:
            try:
                # Configurar tamaño del rostro a seguir (en metros, aprox 0.1-0.2m)
                self.face_tracker.setFaceWidth(0.15)
                
                # Iniciar tracking
                self.face_tracker.startTracker()
                logger.info("Seguimiento de rostro con ALFaceTracker iniciado")
                
            except Exception as e:
                logger.error("Error iniciando ALFaceTracker: {}".format(e))
                self.use_face_tracker = False
        else:
            logger.info("Usando seguimiento manual de rostro")
    
    def stop_face_tracking(self):
        """Detener el seguimiento de rostro"""
        if self.use_face_tracker and self.face_tracker:
            try:
                self.face_tracker.stopTracker()
                logger.info("Seguimiento de rostro detenido")
            except Exception as e:
                logger.error("Error deteniendo seguimiento de rostro: {}".format(e))
    
    def manual_face_tracking(self):
        """
        Seguimiento manual de rostro usando ALMotion
        Lee la posición del rostro de FaceDetected y mueve la cabeza
        """
        try:
            face_data = self.memory.getData("FaceDetected")
            
            if face_data and len(face_data) >= 2:
                face_info = face_data[1]
                if len(face_info) > 0:
                    # Obtener la primera cara detectada
                    # face_info[0] contiene [ShapeInfo, ExtraInfo]
                    # ShapeInfo = [alpha, beta, sizeX, sizeY]
                    # alpha = ángulo horizontal (yaw), beta = ángulo vertical (pitch)
                    shape_info = face_info[0][0]
                    alpha = shape_info[1]  # Yaw (horizontal)
                    beta = shape_info[2]   # Pitch (vertical)
                    
                    # Obtener posición actual de la cabeza
                    current_yaw = self.motion.getAngles("HeadYaw", True)[0]
                    current_pitch = self.motion.getAngles("HeadPitch", True)[0]
                    
                    # Calcular nuevos ángulos (el rostro está en alpha, beta relativos a la cámara)
                    # Ajustar suavemente hacia el rostro
                    gain = 0.3  # Ganancia del controlador (0-1)
                    new_yaw = current_yaw + alpha * gain
                    new_pitch = current_pitch + beta * gain
                    
                    # Limitar ángulos a los rangos permitidos del NAO
                    # HeadYaw: -2.0857 a 2.0857 rad (-119.5° a 119.5°)
                    # HeadPitch: -0.6720 a 0.5149 rad (-38.5° a 29.5°)
                    new_yaw = max(-2.0, min(2.0, new_yaw))
                    new_pitch = max(-0.67, min(0.51, new_pitch))
                    
                    # Mover la cabeza suavemente
                    self.motion.setAngles(
                        ["HeadYaw", "HeadPitch"],
                        [new_yaw, new_pitch],
                        0.2  # Velocidad (fracción de velocidad máxima)
                    )
                    
        except Exception as e:
            # No logueamos cada error para no saturar
            pass
        
    def set_eye_color(self, eye, color):
        """
        Cambiar color de un ojo
        
        Args:
            eye: 'left' o 'right'
            color: 'green', 'red', 'blue', 'off'
        """
        eye_group = "LeftFaceLeds" if eye == 'left' else "RightFaceLeds"
        
        colors = {
            'green': [0.0, 1.0, 0.0],  # RGB
            'red': [1.0, 0.0, 0.0],
            'blue': [0.0, 0.0, 1.0],
            'yellow': [1.0, 1.0, 0.0],  # Amarillo para indicar pérdida de rostro
            'cyan': [0.0, 1.0, 1.0],    # Cyan para indicar preparación de grabación automática
            'off': [0.0, 0.0, 0.0]
        }
        
        if color in colors:
            rgb = colors[color]
            try:
                self.leds.fadeRGB(eye_group, rgb[0], rgb[1], rgb[2], 0.3)
                logger.debug("Ojo {} cambiado a color {}".format(eye, color))
            except Exception as e:
                logger.error("Error cambiando color del ojo: {}".format(e))
    
    def update_face_status_leds(self, face_visible):
        """
        Actualizar LEDs según el estado del rostro detectado
        
        Ojo izquierdo:
        - Verde: rostro detectado y visible
        - Amarillo/parpadeo: rostro perdido temporalmente
        
        Ojo derecho:
        - Cyan: preparando grabación automática (rostro detectado, contando 5s)
        - Verde: grabando
        - Apagado: no grabando
        """
        if face_visible:
            if not self.face_currently_visible:
                # Rostro recuperado
                self.set_eye_color('left', 'green')
                logger.info("Rostro recuperado - ojo izquierdo verde")
                # Reiniciar contador de tiempo de rostro visible
                self.face_visible_start_time = time.time()
            self.face_currently_visible = True
        else:
            if self.face_currently_visible:
                # Rostro perdido
                self.set_eye_color('left', 'yellow')
                logger.warning("Rostro perdido - ojo izquierdo amarillo")
                # Resetear contador de tiempo
                self.face_visible_start_time = None
                # Si no estamos grabando, apagar el ojo derecho (cyan)
                if not self.is_recording:
                    self.set_eye_color('right', 'off')
            self.face_currently_visible = False
    
    def check_auto_record(self):
        """
        Verificar si se debe iniciar grabación automática
        Si el rostro ha sido visible por más de 5 segundos, inicia grabación
        
        Returns:
            True si se inició grabación automática, False si no
        """
        if not self.auto_record_enabled:
            return False
        
        if self.is_recording:
            return False
        
        if not self.face_currently_visible:
            self.auto_record_triggered = False
            return False
        
        if self.face_visible_start_time is None:
            self.face_visible_start_time = time.time()
            return False
        
        elapsed_time = time.time() - self.face_visible_start_time
        
        # Mostrar ojo derecho cyan mientras cuenta los 5 segundos
        if elapsed_time >= 1.0 and not self.auto_record_triggered:
            # Después de 1 segundo, encender cyan para indicar que está preparando
            if not self.is_recording:
                self.set_eye_color('right', 'cyan')
        
        # Si ha pasado el umbral y no se ha activado ya
        if elapsed_time >= self.auto_record_threshold and not self.auto_record_triggered:
            self.auto_record_triggered = True
            logger.info("Grabación automática activada - rostro visible por {:.1f}s".format(elapsed_time))
            
            # Confirmar por voz
            self.tts.say("Iniciando grabación automática")
            
            # Iniciar grabación
            self.start_recording()
            return True
        
        return False
    
    def check_auto_stop(self):
        """
        Verificar si se debe detener grabación automáticamente
        Si el rostro no ha sido visible por más de 5 segundos durante grabación, detiene
        
        Returns:
            True si se detuvo grabación automática, False si no
        """
        if not self.is_recording:
            self.face_lost_start_time = None
            return False
        
        if self.face_currently_visible:
            # Rostro visible, resetear contador de pérdida
            self.face_lost_start_time = None
            return False
        
        # Rostro no visible durante grabación
        if self.face_lost_start_time is None:
            self.face_lost_start_time = time.time()
            logger.info("Rostro perdido durante grabación - iniciando contador")
            return False
        
        elapsed_time = time.time() - self.face_lost_start_time
        
        # Si ha pasado el umbral, detener grabación
        if elapsed_time >= self.auto_stop_threshold:
            logger.info("Grabación detenida automáticamente - rostro perdido por {:.1f}s".format(elapsed_time))
            
            # Confirmar por voz
            self.tts.say("Deteniendo grabación por pérdida de rostro")
            
            # Detener grabación
            self.stop_recording()
            
            # Resetear estados
            self.face_lost_start_time = None
            self.auto_record_triggered = False
            self.face_visible_start_time = None
            
            return True
        
        return False
    
    def check_bumper_pressed(self):
        """Verificar si el bumper derecho fue presionado"""
        try:
            bumper_value = self.memory.getData(self.bumper_event)
            return bumper_value == 1.0
        except Exception as e:
            logger.error("Error leyendo estado del bumper: {}".format(e))
            return False
    
    def start_face_detection(self):
        """Iniciar detección de rostros"""
        logger.info("Iniciando sistema de detección de rostros...")
        try:
            # Configurar parámetros de detección
            self.face_detection.setTrackingEnabled(True)
            
            # Suscribir al módulo de detección
            period = 500  # ms
            self.face_detection.subscribe("FacialRecording", period, 0.0)
            logger.info("Detección de rostros activada (período: {}ms)".format(period))
            
        except Exception as e:
            logger.error("Error iniciando detección de rostros: {}".format(e))
            raise
    
    def stop_face_detection(self):
        """Detener detección de rostros"""
        try:
            self.face_detection.unsubscribe("FacialRecording")
            logger.info("Detección de rostros desactivada")
        except Exception as e:
            logger.error("Error deteniendo detección de rostros: {}".format(e))
    
    def check_face_detected(self):
        """Verificar si hay un rostro detectado"""
        try:
            face_data = self.memory.getData("FaceDetected")
            
            # Formato de FaceDetected: [TimeStamp, FaceInfo]
            # FaceInfo es una lista de rostros detectados
            if face_data and len(face_data) >= 2:
                face_info = face_data[1]
                if len(face_info) > 0:
                    return True
            return False
        except Exception as e:
            logger.error("Error verificando rostro detectado: {}".format(e))
            return False
    
    def wait_for_face(self):
        """Esperar hasta que se detecte un rostro"""
        logger.info("Buscando rostro...")
        self.tts.say("Buscando rostro")
        
        # Apagar ambos ojos mientras busca
        self.set_eye_color('left', 'off')
        self.set_eye_color('right', 'off')
        
        check_interval = 0.5  # segundos
        max_wait_time = 300  # 5 minutos máximo
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            if self.check_face_detected():
                logger.info("¡Rostro detectado!")
                self.face_detected = True
                self.face_currently_visible = True
                
                # Poner ojo izquierdo en verde
                self.set_eye_color('left', 'green')
                self.tts.say("Rostro detectado")
                
                return True
            
            time.sleep(check_interval)
            elapsed_time += check_interval
            
            # Mensaje cada 10 segundos
            if int(elapsed_time) % 10 == 0:
                logger.info("Buscando rostro... ({:.0f}s)".format(elapsed_time))
        
        logger.warning("Timeout esperando detección de rostro")
        self.tts.say("No se detectó ningún rostro")
        return False
    
    def start_recording(self):
        """Iniciar grabación de video"""
        if self.is_recording:
            logger.warning("Ya se está grabando")
            return
        
        # Crear nombre de archivo con timestamp (formato: dia_mes_año_hora_minuto_segundo)
        # Ejemplo: 05_03_2026_143012
        timestamp = datetime.now().strftime("%d_%m_%Y_%H%M%S")
        self.recording_filename = os.path.join(
            self.recordings_dir,
            "face_recording_{}.avi".format(timestamp)
        )
        
        # Obtener resolución
        width, height = self.resolution_map[self.resolution]
        
        # Configurar codec y crear VideoWriter
        # Usar XVID que es compatible y tiene buena calidad
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        
        try:
            self.video_writer = cv2.VideoWriter(
                self.recording_filename,
                fourcc,
                self.fps,
                (width, height)
            )
            
            if not self.video_writer.isOpened():
                raise Exception("No se pudo abrir el VideoWriter")
            
            self.is_recording = True
            
            # Poner ojo derecho en verde (confirmación visual)
            self.set_eye_color('right', 'green')
            
            logger.info("Grabación iniciada: {}".format(self.recording_filename))
            self.tts.say("Grabación iniciada")
            
        except Exception as e:
            logger.error("Error iniciando grabación: {}".format(e))
            self.tts.say("Error al iniciar grabación")
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
    
    def stop_recording(self):
        """Detener grabación de video"""
        if not self.is_recording:
            logger.warning("No hay grabación activa")
            return
        
        try:
            # Cerrar VideoWriter
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            
            self.is_recording = False
            
            # Apagar ojo derecho
            self.set_eye_color('right', 'off')
            
            logger.info("Grabación detenida: {}".format(self.recording_filename))
            self.tts.say("Grabación detenida")
            
            # Verificar que el archivo se creó correctamente
            if os.path.exists(self.recording_filename):
                file_size = os.path.getsize(self.recording_filename)
                logger.info("Archivo guardado: {} ({:.2f} MB)".format(
                    self.recording_filename,
                    file_size / (1024.0 * 1024.0)
                ))
            
        except Exception as e:
            logger.error("Error deteniendo grabación: {}".format(e))
    
    def start_multi_video_recording(self):
        """Iniciar el proceso de grabación múltiple (5 segundos de espera, luego 15 videos de 3 segundos)"""
        self.bumper_press_time = time.time()
        self.multi_video_mode_active = True
        self.videos_recorded = 0
        self.video_start_time = None
        self.multi_video_recording = False  # Aún no comenzó la grabación, primero espera 5 segundos
        
        logger.info("Modo multi-video activado - esperando 5 segundos antes de grabar...")
        self.tts.say("Grabación múltiple iniciada, esperando 5 segundos")
        
        # Indicar visualmente que está en modo de espera (ambos ojos diferentes)
        self.set_eye_color('left', 'cyan')
        self.set_eye_color('right', 'cyan')
    
    def check_multi_video_state(self):
        """
        Verificar y manejar el estado de grabación múltiple
        Returns True si el modo multi-video sigue activo, False si terminou
        """
        if not self.multi_video_mode_active:
            return False
        
        current_time = time.time()
        elapsed_since_press = current_time - self.bumper_press_time
        
        # Fase 1: Esperar 5 segundos antes de empezar a grabar
        if not self.multi_video_recording:
            if elapsed_since_press < self.wait_before_recording:
                # Aún en fase de espera
                remaining = self.wait_before_recording - elapsed_since_press
                if int(remaining) % 2 == 0:  # Parpadear cada segundo (alternando)
                    self.set_eye_color('left', 'cyan')
                    self.set_eye_color('right', 'cyan')
                else:
                    self.set_eye_color('left', 'off')
                    self.set_eye_color('right', 'off')
                
                # Contar los segundos en voz alta cada segundo
                if int(remaining) != int(self.wait_before_recording - max(1, elapsed_since_press - 1)):
                    if int(remaining) > 0:
                        self.tts.say(str(int(remaining)))
                
                return True
            else:
                # Ya pasaron 5 segundos, empezar grabación de videos
                self.multi_video_recording = True
                logger.info("Iniciando grabación de 15 videos de 3 segundos cada uno...")
                self.tts.say("Iniciando grabación de videos")
                self.start_recording()
                self.video_start_time = current_time
                self.videos_recorded = 1
                
                # Encender ojo derecho en verde
                self.set_eye_color('right', 'green')
                self.set_eye_color('left', 'green')
                
                return True
        
        # Fase 2: Grabar 15 videos de 3 segundos cada uno
        if self.video_start_time is None:
            self.video_start_time = current_time
        
        elapsed_current_video = current_time - self.video_start_time
        
        if elapsed_current_video >= self.video_duration:
            # Tiempo de cambiar a siguiente video
            self.stop_recording()
            
            if self.videos_recorded < self.max_videos:
                # Aún hay más videos por grabar
                self.videos_recorded += 1
                
                logger.info("Video {} completado, iniciando video {}...".format(
                    self.videos_recorded - 1,
                    self.videos_recorded
                ))
                self.tts.say("Video {} de {}".format(self.videos_recorded, self.max_videos))
                
                # Pequeña pausa entre videos
                time.sleep(0.5)
                
                # Iniciar nuevo video - ACTUALIZAR current_time después de la pausa
                current_time = time.time()
                self.start_recording()
                self.video_start_time = current_time
                
                if self.videos_recorded == self.max_videos:
                    # Este es el último video
                    logger.info("Iniciando video final ({}/{})...".format(
                        self.max_videos, self.max_videos))
                
                return True
            else:
                # Todos los videos se han grabado
                logger.info("Grabación múltiple completada - {} videos grabados".format(
                    self.max_videos))
                self.tts.say("Grabación completada, 15 videos grabados")
                
                self.multi_video_mode_active = False
                self.multi_video_recording = False
                
                # Apagar LEDs
                self.set_eye_color('left', 'green')
                self.set_eye_color('right', 'off')
                
                return False
        
        return True

    
    def subscribe_camera(self):
        """Suscribir a la cámara del robot"""
        try:
            self.camera_client = self.video_proxy.subscribeCamera(
                self.client_name,
                0,  # Cámara superior
                self.resolution,
                self.colorspace,
                self.fps
            )
            
            resolution_name = {0: "160x120", 1: "320x240", 2: "640x480", 3: "1280x960"}
            logger.info("Cámara suscrita - Resolución: {}, FPS: {}".format(
                resolution_name.get(self.resolution, "Unknown"),
                self.fps
            ))
            
        except Exception as e:
            logger.error("Error suscribiendo cámara: {}".format(e))
            raise
    
    def unsubscribe_camera(self):
        """Desuscribir de la cámara"""
        try:
            if hasattr(self, 'camera_client'):
                self.video_proxy.unsubscribe(self.camera_client)
                logger.info("Cámara desuscrita correctamente")
        except Exception as e:
            logger.error("Error desuscribiendo cámara: {}".format(e))
    
    def process_frame(self, image_data):
        """
        Procesar un frame de la cámara
        
        Args:
            image_data: Datos de imagen de ALVideoDevice
            
        Returns:
            numpy array con el frame BGR
        """
        width, height = image_data[0], image_data[1]
        arr = np.frombuffer(image_data[6], dtype=np.uint8)
        img = arr.reshape((height, width, 3))
        return img
    
    def run(self):
        """Ejecutar el sistema completo"""
        logger.info("=== SISTEMA DE GRABACIÓN CON RECONOCIMIENTO FACIAL ===")
        
        try:
            # 1. Desactivar Autonomous Life
            logger.info("Paso 1: Desactivando Autonomous Life...")
            self.disable_autonomous_life()
            
            # 2. Configurar cabeza para seguimiento
            logger.info("Paso 2: Configurando seguimiento de cabeza...")
            self.enable_head_tracking()
            
            # 3. Iniciar detección de rostros
            logger.info("Paso 3: Iniciando detección de rostros...")
            self.start_face_detection()
            
            # 4. Esperar a que se detecte un rostro
            if not self.wait_for_face():
                logger.error("No se pudo detectar un rostro. Saliendo...")
                return
            
            # 5. Iniciar seguimiento de rostro con la cabeza
            logger.info("Paso 4: Iniciando seguimiento de rostro con cabeza...")
            self.start_face_tracking()
            
            # 6. Suscribir a la cámara para grabación
            self.subscribe_camera()
            
            # 7. Loop principal de grabación
            logger.info("Sistema listo. Presiona el bumper derecho para grabar/detener.")
            logger.info("Grabación automática: rostro visible por 5 segundos.")
            logger.info("Presiona Ctrl+C para salir.")
            
            frame_count = 0
            last_bumper_state = False
            bumper_cooldown = 0
            
            while True:
                try:
                    # Obtener frame de la cámara
                    image_data = self.video_proxy.getImageRemote(self.camera_client)
                    
                    if image_data is None:
                        time.sleep(0.001)
                        continue
                    
                    # Procesar frame
                    frame = self.process_frame(image_data)
                    
                    # Verificar si el rostro sigue visible y actualizar LEDs
                    face_visible = self.check_face_detected()
                    self.update_face_status_leds(face_visible)
                    
                            # Verificar grabación automática (rostro visible por 5 segundos)
                    if self.auto_record_enabled:
                        self.check_auto_record()
                        # Verificar parada automática (rostro perdido por 5 segundos durante grabación)
                        if self.check_auto_stop():
                            frame_count = 0
                    
                    # Seguimiento manual de rostro si ALFaceTracker no está disponible
                    if not self.use_face_tracker:
                        self.manual_face_tracking()
                    
                    # Si está grabando, escribir frame al archivo
                    if self.is_recording and self.video_writer:
                        self.video_writer.write(frame)
                        frame_count += 1
                        
                        # Log cada 100 frames
                        if frame_count % 100 == 0:
                            logger.info("Frames grabados: {}".format(frame_count))
                    
                    # Verificar estado del bumper (con cooldown para evitar rebotes)
                    if bumper_cooldown > 0:
                        bumper_cooldown -= 1
                    else:
                        current_bumper_state = self.check_bumper_pressed()
                        
                        # Detectar flanco de subida (presión del botón)
                        if current_bumper_state and not last_bumper_state:
                            logger.info("Bumper derecho presionado")
                            
                            # Si no hay grabación en progreso, iniciar modo multi-video
                            if not self.multi_video_mode_active:
                                self.start_multi_video_recording()
                            else:
                                # Si estamos en modo multi-video, cancelar
                                logger.info("Cancelando grabación múltiple")
                                self.tts.say("Grabación múltiple cancelada")
                                
                                if self.is_recording:
                                    self.stop_recording()
                                
                                self.multi_video_mode_active = False
                                self.multi_video_recording = False
                                self.set_eye_color('left', 'green')
                                self.set_eye_color('right', 'off')
                            
                            # Cooldown de 500ms (15 frames)
                            bumper_cooldown = 15
                        
                        last_bumper_state = current_bumper_state
                    
                    # Manejar grabación múltiple si está activa
                    if self.multi_video_mode_active:
                        self.check_multi_video_state()

                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error("Error en loop principal: {}".format(e))
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("Interrupción de usuario detectada")
        
        finally:
            # Limpieza
            logger.info("Cerrando sistema...")
            
            if self.is_recording:
                self.stop_recording()
            
            self.unsubscribe_camera()
            self.stop_face_tracking()
            self.stop_face_detection()
            
            # Apagar LEDs
            self.set_eye_color('left', 'off')
            self.set_eye_color('right', 'off')
            
            # Relajar la cabeza
            try:
                self.motion.setStiffnesses("Head", 0.0)
                logger.info("Stiffness de cabeza relajado")
            except:
                pass
            
            logger.info("Sistema cerrado correctamente")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Sistema de grabación de video con reconocimiento facial para NAO'
    )
    parser.add_argument(
        '--nao_ip',
        required=True,
        help='IP del robot NAO'
    )
    parser.add_argument(
        '--nao_port',
        type=int,
        default=9559,
        help='Puerto NAOqi del robot (default: 9559)'
    )
    parser.add_argument(
        '--fps',
        type=int,
        default=13,
        help='Frames por segundo (default: 30)'
    )
    parser.add_argument(
        '--resolution',
        type=int,
        default=2,
        choices=[0, 1, 2, 3],
        help='Resolución: 0=160x120, 1=320x240, 2=640x480, 3=1280x960 (default: 2)'
    )
    parser.add_argument(
        '--enable-face-auto',
        action='store_true',
        help='Activa el inicio/detención de grabación automático basado en detección facial (desactivado por defecto)'
    )
    
    args = parser.parse_args()
    
    # Crear e iniciar el sistema
    try:
        system = FacialRecordingSystem(
            nao_ip=args.nao_ip,
            nao_port=args.nao_port,
            fps=args.fps,
            resolution=args.resolution,
            auto_record_enabled=args.enable_face_auto
        )
        system.run()
    except Exception as e:
        logger.critical("Error fatal: {}".format(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
