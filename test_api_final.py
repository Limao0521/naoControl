#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test DEFINITIVO de APIs - Prueba Groq y Gemini con Python 3
Ejecutar desde tu PC: python test_api_final.py
"""

import urllib.request
import urllib.error
import json
import ssl
import sys

# ============================================================================
# API KEYS HARDCODEADAS
# ============================================================================
GROQ_KEY = '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'
GEMINI_KEY = 'AIzaSyAtQeurKtQXXPqPjydCZz2ZwUrokRXsHpc'

# SSL context sin verificación
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def test_groq_chat(model='llama-3.1-8b-instant'):
    """Probar Groq Chat API"""
    print("\n[GROQ CHAT] Probando modelo: {}".format(model))
    
    url = 'https://api.groq.com/openai/v1/chat/completions'
    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'Eres un asistente. Responde en español.'},
            {'role': 'user', 'content': 'Hola, di algo corto.'}
        ],
        'max_tokens': 50,
        'temperature': 0.7
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(GROQ_KEY)
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        data = json.loads(resp.read().decode('utf-8'))
        text = data['choices'][0]['message']['content']
        print("    ✅ FUNCIONA - Respuesta: {}".format(text[:80]))
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print("    ❌ HTTP {}: {}".format(e.code, body[:120]))
        return False
    except Exception as e:
        print("    ❌ Error: {}".format(str(e)[:100]))
        return False


def test_gemini_chat(model='gemini-2.0-flash-lite'):
    """Probar Gemini Chat API"""
    print("\n[GEMINI CHAT] Probando modelo: {}".format(model))
    
    url = 'https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}'.format(model, GEMINI_KEY)
    payload = json.dumps({
        'contents': [
            {
                'role': 'user',
                'parts': [{'text': 'Hola, di algo corto en español.'}]
            }
        ],
        'generationConfig': {
            'temperature': 0.7,
            'maxOutputTokens': 50
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json'
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        data = json.loads(resp.read().decode('utf-8'))
        text = data['candidates'][0]['content']['parts'][0]['text']
        print("    ✅ FUNCIONA - Respuesta: {}".format(text[:80]))
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print("    ❌ HTTP {}: {}".format(e.code, body[:120]))
        return False
    except Exception as e:
        print("    ❌ Error: {}".format(str(e)[:100]))
        return False


def test_groq_whisper():
    """Probar Groq Whisper (solo verificar que la API responde)"""
    print("\n[GROQ WHISPER] Verificando acceso a Whisper API...")
    
    # Crear un WAV vacío mínimo para probar la conexión
    import struct
    sample_rate = 16000
    duration = 0.1
    num_samples = int(sample_rate * duration)
    
    # WAV header + silent audio
    import io
    buf = io.BytesIO()
    # Write WAV manually
    num_channels = 1
    sample_width = 2
    data_size = num_samples * num_channels * sample_width
    
    # RIFF header
    buf.write(b'RIFF')
    buf.write(struct.pack('<I', 36 + data_size))
    buf.write(b'WAVE')
    # fmt chunk
    buf.write(b'fmt ')
    buf.write(struct.pack('<I', 16))
    buf.write(struct.pack('<HHIIHH', 1, num_channels, sample_rate, 
                          sample_rate * num_channels * sample_width,
                          num_channels * sample_width, sample_width * 8))
    # data chunk
    buf.write(b'data')
    buf.write(struct.pack('<I', data_size))
    buf.write(b'\x00' * data_size)
    
    audio_bytes = buf.getvalue()
    
    # Multipart upload
    boundary = '----TestBoundary123'
    body_parts = []
    body_parts.append('--{}'.format(boundary).encode())
    body_parts.append(b'Content-Disposition: form-data; name="model"')
    body_parts.append(b'')
    body_parts.append(b'whisper-large-v3')
    body_parts.append('--{}'.format(boundary).encode())
    body_parts.append(b'Content-Disposition: form-data; name="file"; filename="test.wav"')
    body_parts.append(b'Content-Type: audio/wav')
    body_parts.append(b'')
    
    body_header = b'\r\n'.join(body_parts) + b'\r\n'
    body_footer = '\r\n--{}--\r\n'.format(boundary).encode()
    full_body = body_header + audio_bytes + body_footer
    
    url = 'https://api.groq.com/openai/v1/audio/transcriptions'
    req = urllib.request.Request(url, data=full_body, headers={
        'Authorization': 'Bearer {}'.format(GROQ_KEY),
        'Content-Type': 'multipart/form-data; boundary={}'.format(boundary)
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        data = json.loads(resp.read().decode('utf-8'))
        print("    ✅ FUNCIONA - Whisper respondió correctamente")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print("    ❌ HTTP {}: {}".format(e.code, body[:120]))
        return False
    except Exception as e:
        print("    ❌ Error: {}".format(str(e)[:100]))
        return False


def main():
    print("=" * 70)
    print("TEST DEFINITIVO DE APIs")
    print("=" * 70)
    print("Groq Key: {}...".format(GROQ_KEY[:20]))
    print("Gemini Key: {}...".format(GEMINI_KEY[:20]))
    
    results = {}
    
    # Test Groq modelos
    groq_models = ['llama-3.1-8b-instant', 'llama-3.3-70b-versatile']
    for m in groq_models:
        results['groq_' + m] = test_groq_chat(m)
    
    # Test Gemini modelos
    gemini_models = ['gemini-2.0-flash-lite', 'gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-2.5-flash-preview-04-17']
    for m in gemini_models:
        results['gemini_' + m] = test_gemini_chat(m)
    
    # Test Whisper
    results['whisper'] = test_groq_whisper()
    
    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    
    working_llm = None
    working_whisper = False
    
    for name, ok in results.items():
        status = "✅" if ok else "❌"
        print("  {} {}".format(status, name))
        if ok and 'whisper' not in name and not working_llm:
            working_llm = name
        if ok and 'whisper' in name:
            working_whisper = True
    
    print("\n" + "-" * 70)
    if working_llm:
        print("RECOMENDACIÓN LLM: Usar '{}'".format(working_llm))
    else:
        print("⚠️  NINGÚN LLM FUNCIONA - Revisa tus API keys")
    
    if working_whisper:
        print("WHISPER: ✅ Funciona")
    else:
        print("WHISPER: ❌ No funciona")
    
    print("=" * 70)
    
    return 0 if working_llm else 1


if __name__ == '__main__':
    sys.exit(main())
