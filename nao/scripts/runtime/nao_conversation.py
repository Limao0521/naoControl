#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
nao_conversation_whisper.py - Conversación con LLM usando Whisper para STT

Este script usa:
- Whisper API (Groq o OpenAI) para reconocimiento de voz
- Gemini/GPT/etc para generar respuestas
- TTS del robot NAO para hablar

Ventajas sobre el ASR nativo de NAO:
- Reconoce cualquier frase (no solo vocabulario predefinido)
- Soporta español y otros idiomas
- Mayor precisión

Uso:
    python nao_conversation_whisper.py --nao_ip 127.0.0.1 --provider gemini

    # Con API key de Groq para Whisper (recomendado, es gratis):
    python nao_conversation_whisper.py --nao_ip 127.0.0.1 --provider gemini --whisper_key TU_GROQ_KEY
"""

import argparse
import sys
import time
import os
import wave
import struct

# Agregar paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm_conversation', 'providers'))

from naoqi import ALProxy

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("WHISPER_CONV")
except ImportError:
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [WHISPER_CONV] {}".format(msg))
        def info(self, msg): print("INFO [WHISPER_CONV] {}".format(msg))
        def warning(self, msg): print("WARNING [WHISPER_CONV] {}".format(msg))
        def error(self, msg): print("ERROR [WHISPER_CONV] {}".format(msg))
        def critical(self, msg): print("CRITICAL [WHISPER_CONV] {}".format(msg))
    logger = FallbackLogger()


class NaoConversationWhisper:
    """Sistema de conversación usando Whisper para STT"""
    
    def __init__(self, nao_ip, nao_port=9559, provider='groq', api_key=None, 
                 whisper_key=None, whisper_provider='groq'):
        """
        Inicializar el sistema
        
        Args:
            nao_ip: IP del robot NAO
            nao_port: Puerto NAOqi
            provider: Proveedor de LLM ('gemini', 'groq', 'openai')
            api_key: API key del LLM
            whisper_key: API key para Whisper (Groq o OpenAI)
            whisper_provider: 'groq' (gratis) o 'openai'
        """
        self.nao_ip = nao_ip
        self.nao_port = nao_port
        self.provider_name = provider
        self.whisper_provider = whisper_provider
        
        # Cargar configuración
        try:
            from llm_conversation import config
            self.config = config
        except ImportError:
            logger.warning("No se pudo cargar config.py")
            self.config = None
        
        # API keys
        if api_key:
            self.api_key = api_key
        elif self.config and provider in self.config.API_KEYS:
            self.api_key = self.config.API_KEYS[provider]
        else:
            # Fallback: API keys hardcodeadas
            _fallback_keys = {
                'gemini': 'AIzaSyAtQeurKtQXXPqPjydCZz2ZwUrokRXsHpc',
                'groq': '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',
            }
            self.api_key = _fallback_keys.get(provider, '')
        
        # Verificar que la API key es válida
        if not self.api_key or 'TU_' in self.api_key:
            raise ValueError("Debes proporcionar una API key válida para {}".format(provider))
        
        # Whisper API key - usar config dedicada si existe
        if whisper_key:
            self.whisper_key = whisper_key
        elif self.config and hasattr(self.config, 'WHISPER_API_KEY'):
            self.whisper_key = self.config.WHISPER_API_KEY
        elif self.config and 'groq' in self.config.API_KEYS:
            self.whisper_key = self.config.API_KEYS.get('groq')
        else:
            self.whisper_key = None
        
        # Whisper provider
        if self.config and hasattr(self.config, 'WHISPER_PROVIDER'):
            self.whisper_provider = self.config.WHISPER_PROVIDER
        
        # Inicializar proveedores
        self._init_llm_provider()
        self._init_whisper_provider()
        
        # Inicializar proxies NAOqi
        logger.info("Conectando al robot NAO en {}:{}".format(nao_ip, nao_port))
        self._init_nao_proxies()
        
        # Directorio temporal para audio
        self.temp_dir = '/tmp/nao_whisper'
        try:
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
        except:
            self.temp_dir = '/tmp'
        
        # Estado
        self.conversation_active = True
        self.exit_keywords = ['adios', 'adiós', 'hasta luego', 'chao', 'terminar', 'salir', 'bye', 'exit']
        self.reset_keywords = ['reiniciar', 'nueva conversacion', 'nueva conversación', 'reset']
    
    def _init_nao_proxies(self):
        """Inicializar proxies de NAOqi"""
        try:
            self.tts = ALProxy('ALTextToSpeech', self.nao_ip, self.nao_port)
            self.leds = ALProxy('ALLeds', self.nao_ip, self.nao_port)
            self.audio_recorder = ALProxy('ALAudioRecorder', self.nao_ip, self.nao_port)
            self.audio_device = ALProxy('ALAudioDevice', self.nao_ip, self.nao_port)
            self.memory = ALProxy('ALMemory', self.nao_ip, self.nao_port)
            
            # Opcionales
            try:
                self.motion = ALProxy('ALMotion', self.nao_ip, self.nao_port)
                self.posture = ALProxy('ALRobotPosture', self.nao_ip, self.nao_port)
            except:
                self.motion = None
                self.posture = None
            
            try:
                self.autonomous_life = ALProxy('ALAutonomousLife', self.nao_ip, self.nao_port)
            except:
                self.autonomous_life = None
            
            logger.info("Proxies NAOqi inicializados correctamente")
            
        except Exception as e:
            logger.critical("Error inicializando proxies: {}".format(e))
            raise
    
    def _init_llm_provider(self):
        """Inicializar proveedor LLM"""
        try:
            if self.provider_name == 'groq':
                from groq_provider import GroqProvider
                self.llm = GroqProvider(self.api_key)
            elif self.provider_name == 'gemini':
                from gemini_provider import GeminiProvider
                self.llm = GeminiProvider(self.api_key)
            elif self.provider_name == 'openai':
                from openai_provider import OpenAIProvider
                self.llm = OpenAIProvider(self.api_key)
            else:
                raise ValueError("Proveedor no soportado: {}".format(self.provider_name))
            
            # System prompt
            system_prompt = "Eres Nao, un robot NAO amigable experto en ingeniería mecánica. Responde de forma concisa en español."
            if self.config and hasattr(self.config, 'SYSTEM_PROMPT'):
                system_prompt = self.config.SYSTEM_PROMPT
            
            self.llm.set_system_prompt(system_prompt)
            logger.info("LLM inicializado: {} ({})".format(self.provider_name, self.llm.model))
            
        except Exception as e:
            logger.critical("Error inicializando LLM: {}".format(e))
            raise
    
    def _init_whisper_provider(self):
        """Inicializar proveedor Whisper para STT"""
        # Usar API key hardcodeada como fallback si no se cargó desde config
        if not self.whisper_key or 'TU_' in self.whisper_key:
            # Fallback: API key hardcodeada
            self.whisper_key = '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'
        
        if not self.whisper_key or 'TU_' in self.whisper_key:
            logger.warning("Sin API key de Whisper - STT no disponible")
            logger.warning("Obtén una API key gratuita de Groq: https://console.groq.com")
            self.whisper = None
            return
        
        try:
            from whisper_stt import WhisperSTTProvider
            logger.debug("Inicializando Whisper con key: {}...".format(self.whisper_key[:20]))
            self.whisper = WhisperSTTProvider(self.whisper_key, self.whisper_provider)
            logger.info("Whisper STT inicializado ({})".format(self.whisper_provider))
        except Exception as e:
            logger.error("Error inicializando Whisper: {}".format(e))
            self.whisper = None
    
    def set_eye_color(self, color):
        """Cambiar color de ojos"""
        colors = {
            'green': 0x0000FF00,
            'blue': 0x000000FF,
            'red': 0x00FF0000,
            'yellow': 0x00FFFF00,
            'cyan': 0x0000FFFF,
            'white': 0x00FFFFFF,
            'off': 0x00000000
        }
        
        if color in colors:
            try:
                self.leds.fadeRGB("FaceLeds", colors[color], 0.3)
            except Exception as e:
                logger.error("Error cambiando LEDs: {}".format(e))
    
    def record_audio(self, duration=5, sample_rate=16000):
        """
        Grabar audio del micrófono del robot
        
        Args:
            duration: Duración en segundos
            sample_rate: Sample rate (16000 recomendado para Whisper)
            
        Returns:
            Ruta al archivo WAV grabado
        """
        audio_file = os.path.join(self.temp_dir, 'recording_{}.wav'.format(int(time.time())))
        
        try:
            # Configurar grabación
            # Canales: [front, rear, left, right] - usar todos (1,1,1,1)
            channels = (1, 0, 0, 0)  # Solo micrófono frontal para mejor calidad
            
            logger.info("Grabando audio ({} segundos)...".format(duration))
            
            # Iniciar grabación
            self.audio_recorder.startMicrophonesRecording(
                audio_file,
                'wav',
                sample_rate,
                channels
            )
            
            # Esperar duración
            time.sleep(duration)
            
            # Detener grabación
            self.audio_recorder.stopMicrophonesRecording()
            
            logger.info("Audio grabado: {}".format(audio_file))
            return audio_file
            
        except Exception as e:
            logger.error("Error grabando audio: {}".format(e))
            try:
                self.audio_recorder.stopMicrophonesRecording()
            except:
                pass
            return None
    
    def transcribe_audio(self, audio_file):
        """
        Transcribir audio usando Whisper
        
        Args:
            audio_file: Ruta al archivo de audio
            
        Returns:
            Texto transcrito
        """
        if not self.whisper:
            logger.error("Whisper no está configurado")
            return None
        
        try:
            logger.info("Transcribiendo con Whisper...")
            text = self.whisper.transcribe_file(audio_file, language='es')
            logger.info("Transcripción: {}".format(text))
            return text.strip() if text else None
            
        except Exception as e:
            logger.error("Error transcribiendo: {}".format(e))
            return None
        finally:
            # Limpiar archivo temporal
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
    
    def listen_and_transcribe(self, duration=5):
        """
        Escuchar y transcribir usando Whisper
        
        Args:
            duration: Duración de la grabación
            
        Returns:
            Texto transcrito o None
        """
        # Indicar que está escuchando
        self.set_eye_color('cyan')
        
        # Grabar audio
        audio_file = self.record_audio(duration)
        if not audio_file:
            return None
        
        # Indicar que está procesando
        self.set_eye_color('yellow')
        
        # Transcribir
        return self.transcribe_audio(audio_file)
    
    def speak(self, text):
        """Hacer que el robot hable"""
        try:
            self.set_eye_color('green')
            logger.info("Hablando: {}".format(text[:60] + "..." if len(text) > 60 else text))
            # Asegurar que el texto es str (bytes) para NAOqi en Python 2
            if isinstance(text, unicode):
                text = text.encode('utf-8')
            elif not isinstance(text, str):
                text = str(text)
            self.tts.say(text)
        except Exception as e:
            logger.error("Error al hablar: {}".format(e))
    
    def get_llm_response(self, user_message):
        """Obtener respuesta del LLM"""
        try:
            self.set_eye_color('yellow')
            logger.info("Consultando LLM...")
            
            response = self.llm.chat(user_message, timeout=30)
            
            # Recortar historial
            max_history = 10
            if self.config and hasattr(self.config, 'MAX_HISTORY_LENGTH'):
                max_history = self.config.MAX_HISTORY_LENGTH
            self.llm.trim_history(max_history)
            
            return response
            
        except Exception as e:
            logger.error("Error con LLM: {}".format(e))
            return "Lo siento, tuve un problema. ¿Puedes repetir?"
    
    def check_commands(self, text):
        """Verificar comandos especiales"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        for keyword in self.exit_keywords:
            if keyword in text_lower:
                return 'exit'
        
        for keyword in self.reset_keywords:
            if keyword in text_lower:
                return 'reset'
        
        return None
    
    def run(self):
        """Ejecutar conversación"""
        logger.info("=== CONVERSACIÓN CON WHISPER STT ===")
        logger.info("Proveedor: {} | Whisper: {}".format(self.provider_name, self.whisper_provider))
        
        # Verificar Whisper
        if not self.whisper:
            logger.critical("Whisper no configurado. Necesitas una API key de Groq (gratis)")
            logger.info("1. Ve a https://console.groq.com/")
            logger.info("2. Crea una cuenta gratuita")
            logger.info("3. Copia tu API key")
            logger.info("4. Ejecuta: python nao_conversation_whisper.py --whisper_key TU_KEY")
            return
        
        try:
            # Ensure robot is standing (do NOT disable autonomous life, it causes sitting)
            if self.posture and self.motion:
                try:
                    self.motion.wakeUp()
                    self.posture.goToPosture("Stand", 0.5)
                except:
                    pass
            
            # Saludo
            self.speak("Hola, soy Nao. Estoy listo para conversar sobre ingeniería mecánica. Habla cuando mis ojos estén azules.")
            
            # Loop de conversación
            while self.conversation_active:
                try:
                    # Escuchar
                    self.speak("Te escucho")
                    user_input = self.listen_and_transcribe(duration=5)
                    
                    if not user_input:
                        self.set_eye_color('red')
                        self.speak("No te escuché bien. Intenta de nuevo.")
                        continue
                    
                    # Mostrar lo que escuchó
                    logger.info("Usuario dijo: {}".format(user_input))
                    
                    # Verificar comandos
                    command = self.check_commands(user_input)
                    
                    if command == 'exit':
                        self.speak("¡Fue un placer hablar contigo! Hasta pronto.")
                        break
                    
                    if command == 'reset':
                        self.llm.clear_history()
                        self.speak("Conversación reiniciada. ¿De qué quieres hablar?")
                        continue
                    
                    # Obtener respuesta del LLM
                    response = self.get_llm_response(user_input)
                    
                    # Responder
                    self.speak(response)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error("Error en loop: {}".format(e))
                    self.speak("Tuve un problema. Intentemos de nuevo.")
                    time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("Interrupción de usuario")
            self.speak("¡Hasta luego!")
        
        finally:
            self.set_eye_color('off')
            logger.info("Conversación finalizada")


def main():
    parser = argparse.ArgumentParser(
        description='Conversación NAO con Whisper STT'
    )
    parser.add_argument('--nao_ip', default='127.0.0.1', help='IP del robot')
    parser.add_argument('--nao_port', type=int, default=9559, help='Puerto NAOqi')
    parser.add_argument('--provider', choices=['groq', 'gemini', 'openai'], 
                       default='groq', help='Proveedor LLM')
    parser.add_argument('--api_key', help='API key del LLM')
    parser.add_argument('--whisper_key', help='API key de Groq para Whisper (gratis)')
    parser.add_argument('--whisper_provider', choices=['groq', 'openai'],
                       default='groq', help='Proveedor de Whisper')
    
    args = parser.parse_args()
    
    try:
        conversation = NaoConversationWhisper(
            nao_ip=args.nao_ip,
            nao_port=args.nao_port,
            provider=args.provider,
            api_key=args.api_key,
            whisper_key=args.whisper_key,
            whisper_provider=args.whisper_provider
        )
        conversation.run()
        
    except Exception as e:
        logger.critical("Error: {}".format(e))
        print("\nError: {}".format(e))
        print("\nPara usar Whisper (STT en español), necesitas:")
        print("1. API key de Groq (gratis): https://console.groq.com/")
        print("2. Ejecutar: python nao_conversation_whisper.py --whisper_key TU_GROQ_KEY")
        sys.exit(1)


if __name__ == '__main__':
    main()
