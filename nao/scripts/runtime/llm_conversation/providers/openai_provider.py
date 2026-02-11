# -*- coding: utf-8 -*-
"""
OpenAI Provider - Proveedor de LLM usando OpenAI API
"""

from base_provider import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Proveedor de LLM usando OpenAI API"""
    
    @property
    def default_model(self):
        return 'gpt-3.5-turbo'
    
    @property
    def api_url(self):
        return 'https://api.openai.com/v1/chat/completions'
    
    def _build_messages(self):
        """Construir mensajes en formato OpenAI"""
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
        """Construir cuerpo de la petición para OpenAI"""
        return {
            'model': self.model,
            'messages': self._build_messages(),
            'temperature': 0.7,
            'max_tokens': 256,
            'top_p': 1,
            'frequency_penalty': 0,
            'presence_penalty': 0
        }
    
    def _parse_response(self, response_data):
        """Parsear respuesta de OpenAI"""
        return response_data['choices'][0]['message']['content']
