#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de Gemini - Fallback cuando Groq falla
"""

import urllib.request
import urllib.error
import json

API_KEY = 'AIzaSyDxwyh4QFPIxnlL_5OxSlgjpPNTTjH_kho'

models = [
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
]

print("=" * 70)
print("TEST GEMINI (FALLBACK)")
print("=" * 70)

for model in models:
    print(f"\n[PROBANDO] {model}...", end=" ")
    
    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}'
        
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': 'Hola'}
                    ]
                }
            ]
        }
        
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            try:
                message = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ FUNCIONA")
                print(f"   Respuesta: {message[:60]}")
            except:
                print(f"✅ Response recibida pero sin contenido")
                print(f"   {str(result)[:60]}")
            
    except urllib.error.HTTPError as e:
        error_data = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_data)
            error_msg = error_json.get('error', {}).get('message', str(e))
        except:
            error_msg = error_data[:100]
        print(f"❌ Error HTTP {e.code}")
        print(f"   {error_msg[:70]}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:70]}")

print("\n" + "=" * 70)
print("CONCLUSIÓN: Si Gemini funciona, úsalo como fallback")
print("=" * 70)
