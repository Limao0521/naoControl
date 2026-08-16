# -*- coding: utf-8 -*-
"""
Whisper STT Provider - Transcripción de voz usando OpenAI Whisper API
El audio se graba en el robot y se envía a la nube para transcripción.

NOTA: Requiere una API key de OpenAI o usar Groq (que también soporta Whisper gratis)
"""

import json
import urllib2
import ssl
import base64
import os


class WhisperSTTProvider(object):
    """Proveedor de Speech-to-Text usando Whisper API"""
    
    def __init__(self, api_key, provider='groq'):
        """
        Inicializar el proveedor de Whisper
        
        Args:
            api_key: API key (OpenAI o Groq)
            provider: 'openai' o 'groq' (groq es gratis y soporta Whisper)
        """
        self.api_key = api_key
        self.provider = provider
        
        # URLs de las APIs
        self.api_urls = {
            'openai': 'https://api.openai.com/v1/audio/transcriptions',
            'groq': 'https://api.groq.com/openai/v1/audio/transcriptions',
        }
        
        # Modelos disponibles
        self.models = {
            'openai': 'whisper-1',
            'groq': 'whisper-large-v3',  # Groq ofrece Whisper gratis!
        }
    
    @property
    def api_url(self):
        return self.api_urls.get(self.provider, self.api_urls['groq'])
    
    @property
    def model(self):
        return self.models.get(self.provider, self.models['groq'])
    
    def transcribe_file(self, audio_file_path, language='es'):
        """
        Transcribir un archivo de audio
        
        Args:
            audio_file_path: Ruta al archivo de audio (WAV, MP3, etc.)
            language: Código de idioma (es=español, en=inglés)
            
        Returns:
            Texto transcrito
        """
        if not os.path.exists(audio_file_path):
            raise Exception("Archivo de audio no encontrado: {}".format(audio_file_path))
        
        # Leer el archivo de audio
        with open(audio_file_path, 'rb') as f:
            audio_data = f.read()
        
        return self.transcribe_bytes(audio_data, language, audio_file_path)
    
    def transcribe_bytes(self, audio_bytes, language='es', filename='audio.wav'):
        """
        Transcribir bytes de audio
        
        Args:
            audio_bytes: Bytes del audio
            language: Código de idioma
            filename: Nombre del archivo para el Content-Type
            
        Returns:
            Texto transcrito
        """
        # Crear boundary para multipart (igual al test que funciona)
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        
        # Construir body IGUAL AL TEST QUE FUNCIONA
        body = []
        body.append('--{}'.format(boundary))
        body.append('Content-Disposition: form-data; name="model"')
        body.append('')
        body.append(self.model)
        body.append('--{}'.format(boundary))
        body.append('Content-Disposition: form-data; name="file"; filename="{}"'.format(filename))
        body.append('Content-Type: audio/wav')
        body.append('')
        
        # Crear string y convertir a bytes
        body_str = '\r\n'.join(body) + '\r\n'
        body_end = '\r\n--{}--\r\n'.format(boundary)
        
        # Concatenar igual que el test
        full_body = body_str.encode('utf-8') + audio_bytes + body_end.encode('utf-8')
        
        # Crear y enviar request
        request = urllib2.Request(self.api_url, data=full_body)
        request.add_header('Authorization', 'Bearer {}'.format(self.api_key))
        request.add_header('Content-Type', 'multipart/form-data; boundary={}'.format(boundary))
        request.add_header('User-Agent', 'Mozilla/5.0')
        
        try:
            response = urllib2.urlopen(request, timeout=30)
            response_data = json.loads(response.read().decode('utf-8'))
            return response_data.get('text', '')
        except urllib2.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception("HTTP Error {}: {}".format(e.code, error_body))
        except urllib2.URLError as e:
            raise Exception("URL Error: {}".format(e.reason))


class GoogleSpeechSTTProvider(object):
    """
    Proveedor de STT usando Google Cloud Speech-to-Text
    Alternativa gratuita con la API key de Gemini (misma cuenta de Google)
    """
    
    def __init__(self, api_key):
        """
        Inicializar el proveedor
        
        Args:
            api_key: API key de Google Cloud
        """
        self.api_key = api_key
        self.api_url = 'https://speech.googleapis.com/v1/speech:recognize?key={}'.format(api_key)
    
    def transcribe_bytes(self, audio_bytes, language='es-ES', sample_rate=16000):
        """
        Transcribir bytes de audio
        
        Args:
            audio_bytes: Bytes del audio (LINEAR16/WAV)
            language: Código de idioma (es-ES, en-US)
            sample_rate: Sample rate del audio
            
        Returns:
            Texto transcrito
        """
        # Codificar audio en base64
        audio_content = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Construir request
        request_body = {
            'config': {
                'encoding': 'LINEAR16',
                'sampleRateHertz': sample_rate,
                'languageCode': language,
                'enableAutomaticPunctuation': True,
            },
            'audio': {
                'content': audio_content
            }
        }
        
        body = json.dumps(request_body)
        headers = {'Content-Type': 'application/json'}
        
        request = urllib2.Request(self.api_url, data=body.encode('utf-8'), headers=headers)
        
        try:
            response = urllib2.urlopen(request, timeout=30)
            response_data = json.loads(response.read().decode('utf-8'))
            
            # Extraer texto
            results = response_data.get('results', [])
            if results:
                alternatives = results[0].get('alternatives', [])
                if alternatives:
                    return alternatives[0].get('transcript', '')
            return ''
            
        except urllib2.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception("HTTP Error {}: {}".format(e.code, error_body))
        except urllib2.URLError as e:
            raise Exception("URL Error: {}".format(e.reason))
