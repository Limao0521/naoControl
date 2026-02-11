#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test exhaustivo Gemini - probar todos los endpoints y modelos
"""

import urllib.request
import urllib.error
import json
import ssl

GEMINI_KEY = 'AIzaSyAtQeurKtQXXPqPjydCZz2ZwUrokRXsHpc'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print("=" * 70)
print("TEST EXHAUSTIVO GEMINI")
print("=" * 70)

# 1. Listar modelos disponibles (no consume cuota de generación)
print("\n[1] Listando modelos disponibles...")
for api_version in ['v1beta', 'v1']:
    print(f"  Endpoint: {api_version}")
    url = f'https://generativelanguage.googleapis.com/{api_version}/models?key={GEMINI_KEY}'
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read().decode('utf-8'))
        models = data.get('models', [])
        print(f"    ✅ {len(models)} modelos disponibles:")
        for m in models:
            name = m.get('name', '').replace('models/', '')
            methods = m.get('supportedGenerationMethods', [])
            if 'generateContent' in methods:
                print(f"      - {name}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')[:120]
        print(f"    ❌ HTTP {e.code}: {body}")
    except Exception as e:
        print(f"    ❌ {str(e)[:80]}")

# 2. Probar generación con diferentes modelos y endpoints
print("\n[2] Probando generación de contenido...")

test_configs = [
    ('v1beta', 'gemini-2.0-flash-lite'),
    ('v1beta', 'gemini-2.0-flash'),
    ('v1', 'gemini-2.0-flash-lite'),
    ('v1', 'gemini-2.0-flash'),
    ('v1beta', 'gemini-pro'),
    ('v1', 'gemini-pro'),
]

for api_ver, model in test_configs:
    print(f"\n  [{api_ver}] {model}...", end=" ")
    
    url = f'https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={GEMINI_KEY}'
    payload = json.dumps({
        'contents': [{'role': 'user', 'parts': [{'text': 'Hola'}]}],
        'generationConfig': {'maxOutputTokens': 30}
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        data = json.loads(resp.read().decode('utf-8'))
        text = data['candidates'][0]['content']['parts'][0]['text']
        print(f"✅ FUNCIONA! -> {text[:50]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            err = json.loads(body)
            msg = err['error']['message'][:60]
        except:
            msg = body[:60]
        print(f"❌ {e.code}: {msg}")
    except Exception as e:
        print(f"❌ {str(e)[:60]}")

# 3. Probar Groq via proxy/alternativo
print("\n\n[3] Probando acceso alternativo a Groq...")
GROQ_KEY = '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'

# Intentar con User-Agent diferente
for ua in ['Mozilla/5.0', 'NAO-Robot/1.0', 'Python/3.13']:
    print(f"  User-Agent: {ua}...", end=" ")
    
    url = 'https://api.groq.com/openai/v1/chat/completions'
    payload = json.dumps({
        'model': 'llama-3.1-8b-instant',
        'messages': [{'role': 'user', 'content': 'Hi'}],
        'max_tokens': 10
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_KEY}',
        'User-Agent': ua
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read().decode('utf-8'))
        print(f"✅ FUNCIONA!")
        break
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}")
    except Exception as e:
        print(f"❌ {str(e)[:40]}")

print("\n" + "=" * 70)
