#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_bumper_simple.py - Test simple para diagnosticar el problema del bumper
"""

from __future__ import print_function
import time
from naoqi import ALProxy

# Callback global para NAOqi - DEBE estar en el nivel del módulo
def onBumperEvent(key, value, message):
    print("*** CALLBACK ACTIVADO ***")
    print("Key: {}".format(key))
    print("Value: {}".format(value)) 
    print("Message: {}".format(message))
    print("Timestamp: {}".format(time.time()))
    print("=" * 50)

def test_all_bumper_events():
    print("Iniciando test de eventos de bumper...")
    
    try:
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)
        leds = ALProxy("ALLeds", "127.0.0.1", 9559)
        
        # Obtener lista de todos los eventos disponibles
        events = memory.getEventList()
        bumper_events = [e for e in events if any(word in e.lower() for word in ['bump', 'tactil', 'touch', 'foot'])]
        
        print("Eventos relacionados con sensores tactiles encontrados:")
        for event in sorted(bumper_events):
            print("  - {}".format(event))
        
        # Suscribirse a múltiples eventos para encontrar el correcto
        events_to_test = [
            "RightBumperPressed",
            "LeftBumperPressed",
            "FrontTactilTouched", 
            "MiddleTactilTouched",
            "RearTactilTouched",
            "rightBumperPressed",  # Alternativa con minúscula
            "leftBumperPressed"
        ]
        
        successfully_subscribed = []
        
        # Intentar suscribirse a cada evento
        for event in events_to_test:
            try:
                memory.subscribeToEvent(event, "TestBumper", "onBumperEvent")
                successfully_subscribed.append(event)
                print("✓ Suscrito exitosamente a: {}".format(event))
            except Exception as e:
                print("✗ Error suscribiendo a {}: {}".format(event, e))
        
        if not successfully_subscribed:
            print("⚠ ERROR: No se pudo suscribir a ningún evento")
            return
        
        # Cambiar LEDs a azul para indicar que el test está activo
        leds.fadeRGB("FaceLeds", 0x0000FF, 0.3)  # Azul
        
        print("\n" + "="*60)
        print("TEST ACTIVO - Presiona TODOS los sensores táctiles del NAO")
        print("Especialmente los bumpers de los pies")
        print("Presiona Ctrl+C para terminar")
        print("="*60)
        
        # Mantener el test activo
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nTest interrumpido por usuario")
        
        # Limpiar suscripciones
        print("Limpiando suscripciones...")
        for event in successfully_subscribed:
            try:
                memory.unsubscribeToEvent(event, "TestBumper")
                print("Desuscrito de: {}".format(event))
            except Exception as e:
                print("Error desuscribiendo {}: {}".format(event, e))
        
        # Apagar LEDs
        leds.fadeRGB("FaceLeds", 0x000000, 0.3)
        print("Test completado")
        
    except Exception as e:
        print("Error en test: {}".format(e))

if __name__ == "__main__":
    test_all_bumper_events()