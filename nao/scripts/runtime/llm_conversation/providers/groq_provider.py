# -*- coding: utf-8 -*-
"""
Groq Provider - Proveedor de LLM usando Groq API
Groq ofrece inferencia muy rápida con modelos como Llama 3
"""

from base_provider import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    """Proveedor de LLM usando Groq API"""
    
    @property
    def default_model(self):
        return 'llama-3.1-8b-instant'  # Modelo comprobado en free tier
    
    @property
    def api_url(self):
        return 'https://api.groq.com/openai/v1/chat/completions'
    
    def _build_messages(self):
        """Construir mensajes en formato OpenAI (compatible con Groq)"""
        messages = []
        
        # Agregar system prompt si existe
        if self.system_prompt:
            messages.append({
                'role': 'system',
                'content': self.system_prompt
            })
        
        # Agregar historial de conversación
        messages.extend(self.conversation_history)
        
        return messages
    
    def _build_request_body(self):
        """Construir cuerpo de la petición para Groq"""
        return {
            'model': self.model,
            'messages': self._build_messages(),
            'temperature': 0.7,
            'max_tokens': 256,
            'top_p': 1,
            'stream': False
        }
    
    def _parse_response(self, response_data):
        """Parsear respuesta de Groq"""
        return response_data['choices'][0]['message']['content']
