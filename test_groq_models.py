#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para encontrar el mejor modelo de Groq disponible en tu account
Prueba modelos potentes en orden de preferencia
"""

import urllib.request
import urllib.error
import json
import sys

def test_groq_model(api_key, model):
    """Probar si un modelo específico funciona"""
    
    try:
        url = 'https://api.groq.com/openai/v1/chat/completions'
        
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'Eres un asistente útil.'},
                {'role': 'user', 'content': 'Hola, ¿cómo estás?'}
            ],
            'temperature': 0.7,
            'max_tokens': 50,
        }
        
        json_data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(api_key)
            }
        )
        
        response = urllib.request.urlopen(req, timeout=10)
        response_data = json.loads(response.read().decode('utf-8'))
        
        # Si llegó aquí, funciona
        return True, response_data['choices'][0]['message']['content']
        
    except urllib.error.HTTPError as e:
        try:
            error_body = json.loads(e.read().decode('utf-8'))
            error_msg = error_body.get('error', {}).get('message', str(e))
        except:
            error_msg = str(e)
        return False, "HTTP {}: {}".format(e.code, error_msg)
        
    except Exception as e:
        return False, str(e)


def main():
    """Encontrar el mejor modelo disponible"""
    
    # Tu API key - REEMPLAZA CON TU KEY COMPLETA
    api_key = input("Ingresa tu API key de Groq completa: ").strip()
    
    if not api_key or api_key.startswith('gsk_') == False:
        print("[ERROR] API key inválida")
        sys.exit(1)
    
    # Modelos ordenados por potencia (mejores primero)
    models = [
        ('llama-3.3-70b-versatile', 'Llama 3.3 70B - Más potente (RECOMENDADO)'),
        ('meta-llama/llama-4-maverick-17b-128e-instruct', 'Llama 4 Maverick 17B - Muy potente'),
        ('qwen/qwen3-32b', 'Qwen3 32B - Alternativa potente'),
        ('meta-llama/llama-4-scout-17b-16e-instruct', 'Llama 4 Scout 17B - Versión ligera del 4'),
        ('moonshotai/kimi-k2-instruct', 'Kimi K2 - Alternativa Asia'),
        ('llama-3.1-8b-instant', 'Llama 3.1 8B - Fallback (funciona seguro)'),
    ]
    
    print("\n" + "=" * 80)
    print("BUSCANDO EL MEJOR MODELO DE GROQ DISPONIBLE")
    print("=" * 80)
    
    working_models = []
    
    for model_id, description in models:
        print("\n[TEST] {}".format(description))
        print("       Probando: {}".format(model_id))
        
        success, result = test_groq_model(api_key, model_id)
        
        if success:
            print("       ✅ FUNCIONA")
            print("       Response: {}...".format(result[:60]))
            working_models.append((model_id, description))
        else:
            print("       ❌ No disponible")
            print("       Error: {}".format(result[:80]))
    
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    
    if working_models:
        print("\n✅ MODELOS QUE FUNCIONAN:")
        for i, (model_id, description) in enumerate(working_models, 1):
            marker = "🥇 RECOMENDADO" if i == 1 else ""
            print("  {}. {} {}".format(i, model_id, marker))
        
        best_model = working_models[0][0]
        print("\n" + "=" * 80)
        print("RECOMENDACIÓN: Usar '{}' para nao_conversation.py".format(best_model))
        print("=" * 80)
        
        return best_model
    else:
        print("\n❌ ERROR: Ningún modelo funciona con tu API key")
        print("Verifica que tu key sea válida en https://console.groq.com/")
        sys.exit(1)


if __name__ == '__main__':
    best = main()
