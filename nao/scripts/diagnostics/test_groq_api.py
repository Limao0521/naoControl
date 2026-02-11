#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_groq_api.py - Verificar que la API de Groq funciona correctamente (Python 3)

Prueba:
1. Conexión a Groq LLM
2. Conexión a Whisper STT
3. Genera un archivo de audio de prueba
4. Intenta transcribir
"""

import os
import sys
import json
import wave
import struct
import urllib.request
import urllib.error
import ssl
import io

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except ImportError:
    print("[WARNING] python-dotenv no instalado, intentando leer .env manualmente...")

# API Key
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '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')

print("=" * 80)
print("TEST DE API GROQ")
print("=" * 80)
print("[INFO] API Key: {}...".format(GROQ_API_KEY[:20]))
print()

# TEST 1: Whisper STT
print("[TEST 1] Probando Whisper STT...")
print("-" * 80)

def test_whisper():
    """Probar Whisper API de Groq"""
    try:
        # Crear archivo WAV de prueba (silencio de 1 segundo)
        filename = 'test_audio.wav'
        sample_rate = 16000
        duration = 1  # segundos
        
        # Generar audio (silencio)
        audio_data = [0] * (sample_rate * duration)
        
        # Guardar como WAV
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for sample in audio_data:
                wav_file.writeframes(struct.pack('<h', int(sample)))
        
        print("[OK] Archivo de audio de prueba creado: {}".format(filename))
        
        # Leer archivo
        with open(filename, 'rb') as f:
            audio_bytes = f.read()
        
        print("[OK] Archivo leído: {} bytes".format(len(audio_bytes)))
        
        # Crear request a Whisper
        url = 'https://api.groq.com/openai/v1/audio/transcriptions'
        
        # Crear multipart form data
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        
        body = []
        body.append('--{}'.format(boundary))
        body.append('Content-Disposition: form-data; name="model"')
        body.append('')
        body.append('whisper-large-v3')
        body.append('--{}'.format(boundary))
        body.append('Content-Disposition: form-data; name="file"; filename="test_audio.wav"')
        body.append('Content-Type: audio/wav')
        body.append('')
        
        body_str = '\r\n'.join(body) + '\r\n'
        
        # Agregar el archivo
        body_end = '\r\n--{}--\r\n'.format(boundary)
        
        # Construir request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        full_body = body_str.encode() + audio_bytes + body_end.encode()
        
        req = urllib.request.Request(url, data=full_body)
        req.add_header('Authorization', 'Bearer {}'.format(GROQ_API_KEY))
        req.add_header('Content-Type', 'multipart/form-data; boundary={}'.format(boundary))
        req.add_header('User-Agent', 'NAO-Test/1.0')
        
        print("[INFO] Enviando request a: {}".format(url))
        print("[INFO] Headers:")
        for header, value in req.headers.items():
            if 'Authorization' in header:
                print("  {}: Bearer {}...".format(header, GROQ_API_KEY[:20]))
            else:
                print("  {}: {}".format(header, value))
        
        # Enviar request
        try:
            response = urllib.request.urlopen(req, context=ctx)
            response_data = response.read()
            print("[OK] Response 200: Transcripción exitosa")
            print("[INFO] Response: {}".format(response_data[:200]))
            return True
            
        except urllib.error.HTTPError as e:
            print("[ERROR] HTTP Error {}: {}".format(e.code, e.reason))
            error_body = e.read()
            print("[ERROR] Body: {}".format(error_body))
            
            if e.code == 403:
                print("\n[ANÁLISIS] Error 403 (Forbidden):")
                print("  - La API key puede estar revocada o expirada")
                print("  - El IP podría estar bloqueado por Cloudflare")
                print("  - Verifica que la API key sea correcta")
            
            return False
            
        except Exception as e:
            print("[ERROR] Connection error: {}".format(e))
            return False
    
    finally:
        # Limpiar archivo de prueba
        if os.path.exists('test_audio.wav'):
            os.remove('test_audio.wav')
            print("[INFO] Archivo de prueba eliminado")

success_whisper = test_whisper()

print()
print("-" * 80)

# TEST 2: LLM Chat
print("[TEST 2] Probando Groq LLM Chat...")
print("-" * 80)

def test_llm():
    """Probar Groq LLM API"""
    try:
        url = 'https://api.groq.com/openai/v1/chat/completions'
        
        headers = {
            'Authorization': 'Bearer {}'.format(GROQ_API_KEY),
            'Content-Type': 'application/json',
            'User-Agent': 'NAO-Test/1.0'
        }
        
        payload = {
            'model': 'llama-3.1-8b-instant',  # Modelo más pequeño y disponible en free tier
            'messages': [
                {
                    'role': 'system',
                    'content': 'Eres un asistente amigable. Responde de forma muy breve (máximo 10 palabras).'
                },
                {
                    'role': 'user',
                    'content': 'Hola, ¿cómo estás?'
                }
            ],
            'temperature': 0.7,
            'max_tokens': 100
        }
        
        print("[INFO] Enviando request a: {}".format(url))
        print("[INFO] Payload: {}".format(json.dumps(payload, indent=2)[:200]))
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode())
        for header, value in headers.items():
            if 'Authorization' in header:
                req.add_header(header, value)
            else:
                req.add_header(header, value)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            response = urllib.request.urlopen(req, context=ctx)
            response_data = response.read()
            result = json.loads(response_data)
            print("[OK] Response 200: LLM respondió")
            if 'choices' in result:
                message = result['choices'][0]['message']['content']
                print("[INFO] Respuesta: {}".format(message))
            return True
            
        except urllib.error.HTTPError as e:
            print("[ERROR] HTTP Error {}: {}".format(e.code, e.reason))
            error_body = e.read()
            print("[ERROR] Body: {}".format(error_body[:500]))
            
            if e.code == 403:
                print("\n[ANÁLISIS] Error 403 (Forbidden):")
                print("  - La API key puede estar revocada o expirada")
                print("  - El IP podría estar bloqueado por Cloudflare")
                print("  - Intenta generar una nueva API key en https://console.groq.com/")
            
            return False
            
        except Exception as e:
            print("[ERROR] Connection error: {}".format(e))
            return False
    
    except Exception as e:
        print("[ERROR] Setup error: {}".format(e))
        return False

success_llm = test_llm()

print()
print("=" * 80)
print("RESUMEN DE PRUEBAS")
print("=" * 80)
print("[Whisper STT] {}".format("EXITOSO" if success_whisper else "FALLIDO"))
print("[LLM Chat]    {}".format("EXITOSO" if success_llm else "FALLIDO"))
print()

if not (success_whisper and success_llm):
    print("[RECOMENDACIONES]")
    print("1. Verifica tu API key en: https://console.groq.com/keys")
    print("2. Genera una nueva API key si la actual está expirada")
    print("3. Comprueba que tu IP no esté bloqueado por Cloudflare")
    print("4. Intenta acceder a https://api.groq.com/ desde tu navegador")
    sys.exit(1)
else:
    print("[OK] La API de Groq funciona correctamente!")
    sys.exit(0)
