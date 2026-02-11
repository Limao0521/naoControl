#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test final - Simula exactamente lo que hará el robot con las keys y User-Agent fix
"""

import urllib.request
import urllib.error
import json
import ssl
import struct
import io

# Las mismas keys que están hardcodeadas en config.py
GROQ_KEY = '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'
GEMINI_KEY = 'AIzaSyAtQeurKtQXXPqPjydCZz2ZwUrokRXsHpc'
USER_AGENT = 'Mozilla/5.0'  # Fix para Cloudflare

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print("=" * 70)
print("VERIFICACION FINAL - Simulando llamadas del robot")
print("=" * 70)

# ---- TEST 1: Groq LLM Chat ----
print("\n[1/3] GROQ LLM (llama-3.1-8b-instant)...")
url = 'https://api.groq.com/openai/v1/chat/completions'
payload = json.dumps({
    'model': 'llama-3.1-8b-instant',
    'messages': [
        {'role': 'system', 'content': 'Eres Heron, un robot NAO amigable. Responde en español.'},
        {'role': 'user', 'content': 'Hola, ¿cómo te llamas?'}
    ],
    'max_tokens': 100,
    'temperature': 0.7
}).encode('utf-8')

req = urllib.request.Request(url, data=payload, headers={
    'Content-Type': 'application/json',
    'Authorization': 'Bearer {}'.format(GROQ_KEY),
    'User-Agent': USER_AGENT
})

try:
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    data = json.loads(resp.read().decode('utf-8'))
    text = data['choices'][0]['message']['content']
    print("   ✅ GROQ LLM FUNCIONA!")
    print("   Respuesta: {}".format(text[:100]))
    groq_ok = True
except Exception as e:
    print("   ❌ FALLO: {}".format(str(e)[:100]))
    groq_ok = False

# ---- TEST 2: Groq Whisper STT ----
print("\n[2/3] GROQ WHISPER (whisper-large-v3)...")

# Crear WAV de prueba
sample_rate = 16000
num_samples = int(sample_rate * 0.5)
buf = io.BytesIO()
data_size = num_samples * 2
buf.write(b'RIFF')
buf.write(struct.pack('<I', 36 + data_size))
buf.write(b'WAVE')
buf.write(b'fmt ')
buf.write(struct.pack('<I', 16))
buf.write(struct.pack('<HHIIHH', 1, 1, sample_rate, sample_rate * 2, 2, 16))
buf.write(b'data')
buf.write(struct.pack('<I', data_size))
buf.write(b'\x00' * data_size)
audio_bytes = buf.getvalue()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body_parts = []
body_parts.append('--{}'.format(boundary))
body_parts.append('Content-Disposition: form-data; name="model"')
body_parts.append('')
body_parts.append('whisper-large-v3')
body_parts.append('--{}'.format(boundary))
body_parts.append('Content-Disposition: form-data; name="file"; filename="test.wav"')
body_parts.append('Content-Type: audio/wav')
body_parts.append('')

body_header = '\r\n'.join(body_parts) + '\r\n'
body_footer = '\r\n--{}--\r\n'.format(boundary)
full_body = body_header.encode('utf-8') + audio_bytes + body_footer.encode('utf-8')

req = urllib.request.Request(
    'https://api.groq.com/openai/v1/audio/transcriptions',
    data=full_body,
    headers={
        'Authorization': 'Bearer {}'.format(GROQ_KEY),
        'Content-Type': 'multipart/form-data; boundary={}'.format(boundary),
        'User-Agent': USER_AGENT
    }
)

try:
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    data = json.loads(resp.read().decode('utf-8'))
    print("   ✅ WHISPER FUNCIONA!")
    print("   Respuesta: {}".format(data))
    whisper_ok = True
except Exception as e:
    print("   ❌ FALLO: {}".format(str(e)[:100]))
    whisper_ok = False

# ---- TEST 3: Gemini LLM Chat ----
print("\n[3/3] GEMINI LLM (gemini-2.0-flash-lite via v1)...")
url = 'https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent?key={}'.format(GEMINI_KEY)
payload = json.dumps({
    'contents': [{'role': 'user', 'parts': [{'text': 'Hola, ¿cómo estás?'}]}],
    'systemInstruction': {'parts': [{'text': 'Eres Heron, un robot NAO amigable.'}]},
    'generationConfig': {'maxOutputTokens': 100, 'temperature': 0.7}
}).encode('utf-8')

req = urllib.request.Request(url, data=payload, headers={
    'Content-Type': 'application/json',
    'User-Agent': USER_AGENT
})

try:
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    data = json.loads(resp.read().decode('utf-8'))
    text = data['candidates'][0]['content']['parts'][0]['text']
    print("   ✅ GEMINI FUNCIONA!")
    print("   Respuesta: {}".format(text[:100]))
    gemini_ok = True
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    try:
        msg = json.loads(body)['error']['message'][:80]
    except:
        msg = body[:80]
    print("   ❌ HTTP {}: {}".format(e.code, msg))
    gemini_ok = False
except Exception as e:
    print("   ❌ FALLO: {}".format(str(e)[:100]))
    gemini_ok = False

# ---- RESUMEN ----
print("\n" + "=" * 70)
print("RESUMEN FINAL")
print("=" * 70)
print("  Groq LLM:    {} {}".format("✅" if groq_ok else "❌", "LISTO" if groq_ok else "FALLO"))
print("  Whisper STT:  {} {}".format("✅" if whisper_ok else "❌", "LISTO" if whisper_ok else "FALLO"))
print("  Gemini LLM:   {} {}".format("✅" if gemini_ok else "❌", "LISTO (backup)" if gemini_ok else "Cuota agotada (esperar reset)"))

if groq_ok and whisper_ok:
    print("\n🎉 TODO LISTO para usar en el robot NAO!")
    print("   Comando: python2 nao_conversation.py")
elif groq_ok:
    print("\n⚠️  LLM funciona pero Whisper falló")
elif gemini_ok:
    print("\n⚠️  Usar Gemini como fallback: python2 nao_conversation.py --provider gemini")
else:
    print("\n❌ Nada funciona aún")

print("=" * 70)
