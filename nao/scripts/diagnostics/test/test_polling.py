#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_polling.py - Test de polling del bumper
"""

from __future__ import print_function
import time
from naoqi import ALProxy

def test_polling():
    print("Test de polling del bumper...")
    
    try:
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)
        leds = ALProxy("ALLeds", "127.0.0.1", 9559)
        
        # LEDs azules para indicar test activo
        leds.fadeRGB("FaceLeds", 0x0000FF, 0.3)
        
        print("🔵 TEST POLLING ACTIVO")
        print("Presiona el bumper derecho para ver cambios")
        print("Presiona Ctrl+C para terminar")
        
        last_state = memory.getData("RightBumperPressed")
        print("Estado inicial del bumper: {}".format(last_state))
        
        while True:
            current_state = memory.getData("RightBumperPressed")
            
            if current_state != last_state:
                if current_state == 1.0:
                    print("🔴 BUMPER PRESIONADO")
                    leds.fadeRGB("FaceLeds", 0xFF0000, 0.1)  # Rojo
                else:
                    print("🟠 BUMPER LIBERADO")
                    leds.fadeRGB("FaceLeds", 0xFFA500, 0.1)  # Naranja
                
                last_state = current_state
            
            time.sleep(0.05)  # 20Hz
            
    except KeyboardInterrupt:
        print("\nTest interrumpido")
        leds.fadeRGB("FaceLeds", 0x000000, 0.3)  # Apagar
    except Exception as e:
        print("Error: {}".format(e))

if __name__ == "__main__":
    test_polling()