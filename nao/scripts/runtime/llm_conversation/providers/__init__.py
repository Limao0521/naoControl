# -*- coding: utf-8 -*-
"""
LLM Providers Module
Proveedores de LLM soportados: Groq, Gemini, OpenAI, HuggingFace
"""

from base_provider import BaseLLMProvider
from groq_provider import GroqProvider
from gemini_provider import GeminiProvider
from openai_provider import OpenAIProvider
from huggingface_provider import HuggingFaceProvider

def get_provider(provider_name, api_key, model=None):
    """
    Factory function para obtener el proveedor de LLM apropiado
    
    Args:
        provider_name: Nombre del proveedor ('groq', 'gemini', 'openai', 'huggingface')
        api_key: API key del proveedor
        model: Modelo a usar (opcional, usa default si no se especifica)
        
    Returns:
        Instancia del proveedor LLM
    """
    providers = {
        'groq': GroqProvider,
        'gemini': GeminiProvider,
        'openai': OpenAIProvider,
        'huggingface': HuggingFaceProvider,
    }
    
    if provider_name not in providers:
        raise ValueError("Proveedor no soportado: {}. Opciones: {}".format(
            provider_name, list(providers.keys())
        ))
    
    return providers[provider_name](api_key, model)
