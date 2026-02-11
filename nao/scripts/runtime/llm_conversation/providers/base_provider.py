# -*- coding: utf-8 -*-
"""
Base Provider - Clase base para todos los proveedores de LLM
"""

import json
import urllib2
import ssl


class BaseLLMProvider(object):
    """Clase base abstracta para proveedores de LLM"""
    
    def __init__(self, api_key, model=None):
        """
        Inicializar el proveedor
        
        Args:
            api_key: API key para autenticación
            model: Modelo a usar (opcional)
        """
        self.api_key = api_key
        self.model = model or self.default_model
        self.conversation_history = []
        self.system_prompt = None
        
    @property
    def default_model(self):
        """Modelo por defecto del proveedor"""
        raise NotImplementedError("Subclase debe implementar default_model")
    
    @property
    def api_url(self):
        """URL de la API del proveedor"""
        raise NotImplementedError("Subclase debe implementar api_url")
    
    def set_system_prompt(self, prompt):
        """
        Establecer el prompt del sistema
        
        Args:
            prompt: Texto del prompt del sistema
        """
        self.system_prompt = prompt
    
    def add_message(self, role, content):
        """
        Agregar mensaje al historial de conversación
        
        Args:
            role: 'user' o 'assistant'
            content: Contenido del mensaje
        """
        self.conversation_history.append({
            'role': role,
            'content': content
        })
    
    def clear_history(self):
        """Limpiar el historial de conversación"""
        self.conversation_history = []
    
    def trim_history(self, max_length):
        """
        Recortar historial para mantener máximo N mensajes
        
        Args:
            max_length: Número máximo de mensajes a mantener
        """
        if len(self.conversation_history) > max_length:
            self.conversation_history = self.conversation_history[-max_length:]
    
    def _build_messages(self):
        """
        Construir la lista de mensajes para enviar a la API
        
        Returns:
            Lista de mensajes con formato del proveedor
        """
        raise NotImplementedError("Subclase debe implementar _build_messages")
    
    def _build_request_body(self):
        """
        Construir el cuerpo de la petición
        
        Returns:
            Dict con el cuerpo de la petición
        """
        raise NotImplementedError("Subclase debe implementar _build_request_body")
    
    def _parse_response(self, response_data):
        """
        Parsear la respuesta de la API
        
        Args:
            response_data: Dict con la respuesta de la API
            
        Returns:
            Texto de la respuesta
        """
        raise NotImplementedError("Subclase debe implementar _parse_response")
    
    def _make_request(self, timeout=30):
        """
        Realizar petición HTTP a la API
        
        Args:
            timeout: Timeout en segundos
            
        Returns:
            Dict con la respuesta parseada
        """
        # Crear contexto SSL que ignore verificación (para compatibilidad)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Construir request
        body = json.dumps(self._build_request_body())
        headers = self._get_headers()
        
        request = urllib2.Request(
            self.api_url,
            data=body.encode('utf-8'),
            headers=headers
        )
        
        try:
            response = urllib2.urlopen(request, timeout=timeout, context=context)
            response_data = json.loads(response.read().decode('utf-8'))
            return response_data
        except urllib2.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception("HTTP Error {}: {}".format(e.code, error_body))
        except urllib2.URLError as e:
            raise Exception("URL Error: {}".format(e.reason))
    
    def _get_headers(self):
        """
        Obtener headers para la petición
        
        Returns:
            Dict con los headers
        """
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.api_key),
            'User-Agent': 'Mozilla/5.0'
        }
    
    def chat(self, user_message, timeout=30):
        """
        Enviar mensaje y obtener respuesta del LLM
        
        Args:
            user_message: Mensaje del usuario
            timeout: Timeout en segundos
            
        Returns:
            Respuesta del LLM
        """
        # Agregar mensaje del usuario al historial
        self.add_message('user', user_message)
        
        try:
            # Hacer petición
            response_data = self._make_request(timeout)
            
            # Parsear respuesta
            assistant_message = self._parse_response(response_data)
            
            # Agregar respuesta al historial
            self.add_message('assistant', assistant_message)
            
            return assistant_message
            
        except Exception as e:
            # Remover el último mensaje si falló
            if self.conversation_history and self.conversation_history[-1]['role'] == 'user':
                self.conversation_history.pop()
            raise
