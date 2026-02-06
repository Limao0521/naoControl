#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_callback_working.py - Test para verificar que el callback funciona
"""

from __future__ import print_function
import time
from naoqi import ALProxy

# Variables globales
memory = None
leds = None

# CALLBACK GLOBAL - debe estar en nivel del módulo
def onRightBumperPressed(key, value, message):
    """Callback que SÍ va a funcionar"""
    print("🟢 *** BUMPER DERECHO DETECTADO ***")
    print("Key: {}".format(key))
    print("Value: {}".format(value))
    print("Message: {}".format(message))
    
    # Cambiar LEDs según el estado
    if value == 1.0:
        print("🔴 BUMPER PRESIONADO - LEDs ROJOS")
        leds.fadeRGB("FaceLeds", 0xFF0000, 0.2)  # Rojo
    else:
        print("🟠 BUMPER LIBERADO - LEDs NARANJAS") 
        leds.fadeRGB("FaceLeds", 0xFFA500, 0.2)  # Naranja

def test_simple():
    global memory, leds
    
    print("Iniciando test simple de callback...")
    
    try:
        # Inicializar proxies
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)
        leds = ALProxy("ALLeds", "127.0.0.1", 9559)
        
        print("Proxies inicializados")
        
        # Suscribirse usando el nombre exacto del módulo actual
        print("Suscribiendo a RightBumperPressed...")
        memory.subscribeToEvent("RightBumperPressed", "TestSimple", "onRightBumperPressed")
        print("✓ Suscrito exitosamente")
        
        # LEDs azules para indicar que está activo
        leds.fadeRGB("FaceLeds", 0x0000FF, 0.3)  # Azul
        
        print("\n" + "="*50)
        print("🔵 TEST ACTIVO - LEDs AZULES")
        print("Presiona el BUMPER DERECHO del pie")
        print("Deberías ver:")
        print("  🔴 LEDs ROJOS al presionar")  
        print("  🟠 LEDs NARANJAS al soltar")
        print("Presiona Ctrl+C para terminar")
        print("="*50)
        
        # Mantener activo
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nTest interrumpido")
        
        # Limpiar
        print("Limpiando...")
        memory.unsubscribeToEvent("RightBumperPressed", "TestSimple")
        leds.fadeRGB("FaceLeds", 0x000000, 0.3)  # Apagar
        print("Test completado")
        
    except Exception as e:
        print("Error: {}".format(e))

if __name__ == "__main__":
    test_simple()