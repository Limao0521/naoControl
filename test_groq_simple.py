#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test simple de Groq - Python es más confiable que curl
"""

import urllib.request
import urllib.error
import json

api_key = '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'

# Modelos para probar (en orden de probabilidad de funcionar)
models = [
    'llama-3.1-8b-instant',
    'mixtral-8x7b-32768',
    'llama-3.3-70b-versatile',
    'qwen/qwen3-32b',
    'meta-llama/llama-4-maverick-17b-128e-instruct',
]

print("=" * 70)
print("TEST SIMPLE DE GROQ")
print("=" * 70)

for model in models:
    print(f"\n[PROBANDO] {model}...", end=" ")
    
    try:
        url = 'https://api.groq.com/openai/v1/chat/completions'
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': 'Hola'}
            ],
            'max_tokens': 50,
        }
        
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            message = result['choices'][0]['message']['content']
            print(f"✅ FUNCIONA")
            print(f"   Respuesta: {message[:60]}")
            
    except urllib.error.HTTPError as e:
        error_data = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_data)
            error_msg = error_json.get('error', {}).get('message', str(e))
        except:
            error_msg = error_data[:100]
        print(f"❌ Error HTTP {e.code}: {error_msg[:60]}")
        
    except urllib.error.URLError as e:
        print(f"❌ Error de red: {str(e)[:60]}")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error JSON: {str(e)[:60]}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:60]}")

print("\n" + "=" * 70)
