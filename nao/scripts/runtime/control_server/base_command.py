#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
base_command.py - Command Pattern Base Interface

Define la interfaz base para todos los comandos del control server.
Cada acción WebSocket se implementa como un comando independiente.
"""

from __future__ import print_function
import json
from abc import ABCMeta, abstractmethod

class BaseCommand(object):
    """
    Interfaz base para todos los comandos WebSocket.
    Implementa el Command Pattern para encapsular acciones.
    """
    __metaclass__ = ABCMeta
    
    def __init__(self, nao_facade, logger):
        """
        Inicializar comando con dependencias necesarias.
        
        Args:
            nao_facade: Facade para acceso a NAOqi
            logger: Logger para registro de eventos
        """
        self.nao = nao_facade
        self.logger = logger
    
    @abstractmethod
    def execute(self, message, websocket):
        """
        Ejecutar el comando con el mensaje recibido.
        
        Args:
            message (dict): Mensaje JSON parseado del WebSocket
            websocket: Instancia del WebSocket para enviar respuesta
            
        Returns:
            bool: True si la ejecución fue exitosa, False en caso contrario
        """
        pass
    
    @abstractmethod
    def get_action_name(self):
        """
        Obtener el nombre de la acción que maneja este comando.
        
        Returns:
            str: Nombre de la acción (ej: "walk", "posture", etc.)
        """
        pass
    
    def send_success_response(self, websocket, action, data=None):
        """
        Enviar respuesta de éxito al WebSocket.
        
        Args:
            websocket: Instancia del WebSocket
            action (str): Nombre de la acción
            data (dict): Datos adicionales de respuesta
        """
        response = {action: {"success": True}}
        if data:
            response[action].update(data)
        
        websocket.sendMessage(json.dumps(response))
        self.logger.info("{}: Comando ejecutado exitosamente".format(action))
    
    def send_error_response(self, websocket, action, error_msg, additional_data=None):
        """
        Enviar respuesta de error al WebSocket.
        
        Args:
            websocket: Instancia del WebSocket
            action (str): Nombre de la acción
            error_msg (str): Mensaje de error
            additional_data (dict): Datos adicionales de error
        """
        response = {action: {"success": False, "error": error_msg}}
        if additional_data:
            response[action].update(additional_data)
        
        websocket.sendMessage(json.dumps(response))
        self.logger.error("{}: Error - {}".format(action, error_msg))
    
    def validate_required_params(self, message, required_params):
        """
        Validar que el mensaje contenga los parámetros requeridos.
        
        Args:
            message (dict): Mensaje a validar
            required_params (list): Lista de parámetros requeridos
            
        Returns:
            tuple: (is_valid: bool, missing_params: list)
        """
        missing = [param for param in required_params if param not in message]
        return len(missing) == 0, missing
    
    def get_param_safe(self, message, param_name, default_value=None, param_type=None):
        """
        Obtener parámetro del mensaje de forma segura con conversión de tipo.
        
        Args:
            message (dict): Mensaje del WebSocket
            param_name (str): Nombre del parámetro
            default_value: Valor por defecto si no existe
            param_type: Tipo al cual convertir (int, float, str, bool)
            
        Returns:
            Valor del parámetro convertido o valor por defecto
        """
        value = message.get(param_name, default_value)
        
        if param_type and value is not None:
            try:
                if param_type == bool:
                    return bool(value)
                elif param_type == int:
                    return int(value)
                elif param_type == float:
                    return float(value)
                elif param_type == str:
                    return str(value)
            except (ValueError, TypeError) as e:
                self.logger.warning("Error convirtiendo parámetro {}: {} - usando default: {}".format(
                    param_name, e, default_value))
                return default_value
        
        return value