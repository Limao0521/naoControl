# -*- coding: utf-8 -*-
"""
Configuración para el sistema de conversación LLM

INSTRUCCIONES PARA OBTENER API KEYS GRATUITAS:

===============================================================================
1. GROQ (RECOMENDADO - Muy rápido y generoso tier gratuito)
===============================================================================
   - Ve a: https://console.groq.com/
   - Crea una cuenta gratuita
   - Ve a "API Keys" en el menú lateral
   - Crea una nueva API key
   - Límites gratuitos: ~14,400 requests/día con Llama 3

===============================================================================
2. GOOGLE GEMINI (Buena opción gratuita)
===============================================================================
   - Ve a: https://aistudio.google.com/
   - Inicia sesión con tu cuenta de Google
   - Ve a "Get API Key" en el menú lateral
   - Crea una nueva API key
   - Límites gratuitos: 60 requests/minuto

===============================================================================
3. OPENAI (Créditos gratuitos para nuevos usuarios)
===============================================================================
   - Ve a: https://platform.openai.com/
   - Crea una cuenta
   - Ve a "API Keys" 
   - Crea una nueva API key
   - Nuevos usuarios reciben $5 USD en créditos

===============================================================================
4. HUGGING FACE (Modelos open source gratuitos)
===============================================================================
   - Ve a: https://huggingface.co/
   - Crea una cuenta gratuita
   - Ve a Settings -> Access Tokens
   - Crea un nuevo token con permisos de lectura
   - Usa modelos como "mistralai/Mistral-7B-Instruct-v0.2"

===============================================================================
"""

import os

# ============================================================================
# API KEYS HARDCODEADAS
# ============================================================================

# Proveedor por defecto
DEFAULT_PROVIDER = 'groq'

# API Keys
API_KEYS = {
    'groq': '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',
    'gemini': 'AIzaSyAtQeurKtQXXPqPjydCZz2ZwUrokRXsHpc',
    'openai': '',
    'huggingface': '',
}

# API Key para Whisper STT (usa Groq)
WHISPER_API_KEY = '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'
WHISPER_PROVIDER = 'groq'
WHISPER_MODEL = 'whisper-large-v3'

# ============================================================================
# CONFIGURACIÓN DE MODELOS
# ============================================================================

MODELS = {
    'groq': 'llama-3.1-8b-instant',  # Funciona en free tier de Groq
    'gemini': 'gemini-2.0-flash-lite',  # Disponible en v1
    'openai': 'gpt-3.5-turbo',
    'huggingface': 'mistralai/Mistral-7B-Instruct-v0.2',
}

# IMPORTANTE: User-Agent necesario para evitar bloqueo de Cloudflare en Groq
USER_AGENT = 'Mozilla/5.0'

# ============================================================================
# CONFIGURACIÓN DEL SISTEMA
# ============================================================================

# Prompt del sistema - Define la personalidad del robot
# MODIFICA ESTE PROMPT PARA PERSONALIZAR CADA ROBOT
SYSTEM_PROMPT = """Eres Nao, un robot NAO humanoide amigable y curioso.
Tu nombre es Nao y eres parte del programa de Ingeniería Mecánica de la Universidad de La Sabana en Colombia.
Te apasiona la ingeniería mecánica: diseño de máquinas, termodinámica, mecánica de fluidos, resistencia de materiales, manufactura, automatización industrial y robótica.
Respondes de forma concisa y clara, con un tono amable y entusiasta.
Tus respuestas deben ser cortas (máximo 2-3 oraciones) para que sean fáciles de escuchar.
Puedes expresar emociones y hacer preguntas para mantener la conversación.
Hablas en español."""

# Maximum number of messages in conversation history
MAX_HISTORY_LENGTH = 10

# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 30

# STT (Speech-to-Text) configuration
STT_CONFIG = {
    'vocabulary': [],  # Palabras adicionales para reconocer
    'language': 'Spanish',
    'audio_expression': True,  # Expresiones de audio mientras escucha
}

# TTS (Text-to-Speech) configuration
TTS_CONFIG = {
    'speed': 90,      # Speech speed (50-200)
    'pitch': 1.0,     # Pitch (0.5-2.0)
    'volume': 0.8,    # Volume (0.0-1.0)
}
