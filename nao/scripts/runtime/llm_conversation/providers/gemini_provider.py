# -*- coding: utf-8 -*-
"""
Gemini Provider - Proveedor de LLM usando Google Gemini API
"""

from base_provider import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Proveedor de LLM usando Google Gemini API"""
    
    @property
    def default_model(self):
        return 'gemini-2.0-flash-lite'  # Ligero, rápido y eficiente para el robot NAO
    
    @property
    def api_url(self):
        return 'https://generativelanguage.googleapis.com/v1/models/{}:generateContent?key={}'.format(
            self.model, self.api_key
        )
    
    def _get_headers(self):
        """Gemini usa la API key en la URL, no en headers"""
        return {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
    
    def _build_messages(self):
        """Construir mensajes en formato Gemini"""
        contents = []
        
        # Gemini maneja el system prompt diferente
        # Se incluye como primer mensaje de usuario
        if self.system_prompt and len(self.conversation_history) == 1:
            # Solo en el primer mensaje, incluir system prompt
            first_user_msg = self.conversation_history[0]
            if first_user_msg['role'] == 'user':
                contents.append({
                    'role': 'user',
                    'parts': [{'text': self.system_prompt + '\n\nUsuario: ' + first_user_msg['content']}]
                })
                # Agregar resto del historial
                for msg in self.conversation_history[1:]:
                    role = 'user' if msg['role'] == 'user' else 'model'
                    contents.append({
                        'role': role,
                        'parts': [{'text': msg['content']}]
                    })
                return contents
        
        # Convertir historial al formato de Gemini
        for msg in self.conversation_history:
            role = 'user' if msg['role'] == 'user' else 'model'
            contents.append({
                'role': role,
                'parts': [{'text': msg['content']}]
            })
        
        return contents
    
    def _build_request_body(self):
        """Construir cuerpo de la petición para Gemini"""
        body = {
            'contents': self._build_messages(),
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': 256,
                'topP': 1,
                'topK': 40
            }
        }
        
        # Agregar system instruction si existe (Gemini 1.5+)
        if self.system_prompt:
            body['systemInstruction'] = {
                'parts': [{'text': self.system_prompt}]
            }
        
        return body
    
    def _parse_response(self, response_data):
        """Parsear respuesta de Gemini"""
        candidates = response_data.get('candidates', [])
        if candidates:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts:
                return parts[0].get('text', '')
        return ''
