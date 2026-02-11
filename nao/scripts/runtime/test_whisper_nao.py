#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_whisper_nao.py - Test de Whisper STT en el robot NAO (Python 2)
"""

import os
import sys
import json
import wave
import struct
import urllib2
import ssl

print("=" * 80)
print("TEST WHISPER STT EN NAO")
print("=" * 80)

# API Key directa
GROQ_API_KEY = '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'

print("[INFO] API Key: {}...".format(GROQ_API_KEY[:20]))
print("[INFO] Python version: {}".format(sys.version))
print()

# Crear archivo WAV de prueba (silencio de 1 segundo)
print("[PASO 1] Creando archivo WAV de prueba...")
filename = '/tmp/test_whisper.wav'
sample_rate = 16000
duration = 1

# Generar audio (silencio)
audio_data = [0] * (sample_rate * duration)

# Guardar como WAV (compatible con Python 2.7)
wav_file = wave.open(filename, 'w')
try:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    for sample in audio_data:
        wav_file.writeframes(struct.pack('<h', int(sample)))
finally:
    wav_file.close()

print("[OK] Archivo creado: {} ({} bytes)".format(filename, os.path.getsize(filename)))

# Leer archivo (compatible con Python 2.7)
f = open(filename, 'rb')
try:
    audio_bytes = f.read()
finally:
    f.close()

print("[OK] Archivo leído: {} bytes".format(len(audio_bytes)))
print()

# Crear request a Whisper
print("[PASO 2] Enviando request a Groq Whisper API...")
url = 'https://api.groq.com/openai/v1/audio/transcriptions'
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

# Construir multipart form-data
body = []
body.append('--{}'.format(boundary))
body.append('Content-Disposition: form-data; name="model"')
body.append('')
body.append('whisper-large-v3')
body.append('--{}'.format(boundary))
body.append('Content-Disposition: form-data; name="file"; filename="test_whisper.wav"')
body.append('Content-Type: audio/wav')
body.append('')

body_str = '\r\n'.join(body) + '\r\n'
body_end = '\r\n--{}--\r\n'.format(boundary)

full_body = body_str.encode('utf-8') + audio_bytes + body_end.encode('utf-8')

print("[INFO] URL: {}".format(url))
print("[INFO] Body size: {} bytes".format(len(full_body)))
print()

# Crear request
req = urllib2.Request(url, data=full_body)
req.add_header('Authorization', 'Bearer {}'.format(GROQ_API_KEY))
req.add_header('Content-Type', 'multipart/form-data; boundary={}'.format(boundary))
req.add_header('User-Agent', 'NAO-Whisper-Test/1.0')

# Contexto SSL
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print("[PASO 3] Esperando respuesta...")
try:
    print("[DEBUG] Abriendo conexión...")
    response = urllib2.urlopen(req, context=ctx, timeout=30)
    response_data = response.read()
    
    print("[OK] Status 200: Respuesta recibida")
    print("[INFO] Response: {}".format(response_data))
    
    result = json.loads(response_data)
    text = result.get('text', '')
    print()
    print("=" * 80)
    print("RESULTADO:")
    print("=" * 80)
    print("[TRANSCRIPCIÓN] {}".format(text))
    print("[STATUS] EXITOSO")
    print("=" * 80)
    sys.exit(0)
    
except urllib2.HTTPError as e:
    print("[ERROR] HTTP Error {}: {}".format(e.code, e.reason))
    error_body = e.read()
    print("[ERROR] Body: {}".format(error_body))
    
    print()
    print("=" * 80)
    print("RECOMENDACIONES:")
    print("=" * 80)
    if e.code == 403:
        print("- Error 403: API key revocada o IP bloqueado")
        print("- Genera nueva key en: https://console.groq.com/")
    elif e.code == 404:
        print("- Error 404: Modelo no encontrado")
        print("- Usa: whisper-large-v3 o whisper-large-v3-turbo")
    elif e.code == 400:
        print("- Error 400: Request inválido")
        print("- Verifica que el multipart form-data sea correcto")
    
    sys.exit(1)
    
except urllib2.URLError as e:
    print("[ERROR] Connection Error: {}".format(e.reason))
    print()
    print("POSIBLES PROBLEMAS:")
    print("1. No hay conexión a internet")
    print("2. El robot está en una red restringida")
    print("3. Hay un firewall bloqueando requests a api.groq.com")
    print("4. El certificado SSL no es válido")
    sys.exit(1)
    
except Exception as e:
    print("[ERROR] Unexpected error: {}".format(e))
    print("[ERROR] Type: {}".format(type(e).__name__))
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
finally:
    # Limpiar
    if os.path.exists(filename):
        os.remove(filename)
        print("[INFO] Archivo de prueba eliminado")
