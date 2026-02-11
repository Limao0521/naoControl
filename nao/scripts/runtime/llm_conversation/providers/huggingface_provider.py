# -*- coding: utf-8 -*-
"""
HuggingFace Provider - Proveedor de LLM usando HuggingFace Inference API
Permite usar modelos open source como Mistral, Llama, etc.
"""

from base_provider import BaseLLMProvider


class HuggingFaceProvider(BaseLLMProvider):
    """Proveedor de LLM usando HuggingFace Inference API"""
    
    @property
    def default_model(self):
        return 'mistralai/Mistral-7B-Instruct-v0.2'
    
    @property
    def api_url(self):
        return 'https://api-inference.huggingface.co/models/{}'.format(self.model)
    
    def _build_messages(self):
        """Construir prompt en formato de texto para HuggingFace"""
        prompt_parts = []
        
        # Agregar system prompt
        if self.system_prompt:
            prompt_parts.append("<s>[INST] {} [/INST]</s>".format(self.system_prompt))
        
        # Construir conversación en formato Mistral/Llama
        for i, msg in enumerate(self.conversation_history):
            if msg['role'] == 'user':
                prompt_parts.append("<s>[INST] {} [/INST]".format(msg['content']))
            else:
                prompt_parts.append("{}</s>".format(msg['content']))
        
        return '\n'.join(prompt_parts)
    
    def _build_request_body(self):
        """Construir cuerpo de la petición para HuggingFace"""
        return {
            'inputs': self._build_messages(),
            'parameters': {
                'max_new_tokens': 256,
                'temperature': 0.7,
                'top_p': 0.95,
                'do_sample': True,
                'return_full_text': False
            }
        }
    
    def _parse_response(self, response_data):
        """Parsear respuesta de HuggingFace"""
        if isinstance(response_data, list) and len(response_data) > 0:
            generated_text = response_data[0].get('generated_text', '')
            # Limpiar el texto de tokens especiales
            generated_text = generated_text.replace('</s>', '').strip()
            return generated_text
        return ''
