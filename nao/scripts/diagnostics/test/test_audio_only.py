#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_audio_only.py - Test solo de grabación de audio
"""

from __future__ import print_function
import time, os
from datetime import datetime
from naoqi import ALProxy

def test_audio_recording():
    print("Test de grabación de audio...")
    
    try:
        audio_recorder = ALProxy("ALAudioRecorder", "127.0.0.1", 9559)
        leds = ALProxy("ALLeds", "127.0.0.1", 9559)
        
        # Configuración
        recordings_dir = "/data/home/nao/datasets/records"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "{}/test_recording_{}.wav".format(recordings_dir, timestamp)
        
        print("Archivo de prueba: {}".format(filename))
        
        # Verificar directorio
        if not os.path.exists(recordings_dir):
            os.makedirs(recordings_dir)
            print("Directorio creado: {}".format(recordings_dir))
        
        # Test de escritura
        test_file = "{}/test_write.tmp".format(recordings_dir)
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print("✓ Directorio es escribible")
        except Exception as e:
            print("✗ Error de escritura: {}".format(e))
            return
        
        # LEDs rojos para indicar grabación
        leds.fadeRGB("FaceLeds", 0xFF0000, 0.3)
        
        print("Iniciando grabación de 5 segundos...")
        
        # Parar cualquier grabación previa
        try:
            audio_recorder.stopMicrophonesRecording()
            time.sleep(0.2)
        except Exception as e:
            print("stopMicrophonesRecording: {} (esperado)".format(e))
        
        # Iniciar grabación
        audio_recorder.startMicrophonesRecording(
            filename,
            "wav",
            16000,
            [0, 0, 1, 0]  # Solo micrófono frontal
        )
        print("✓ Grabación iniciada")
        
        # Grabar por 5 segundos
        time.sleep(5)
        
        # Parar grabación
        print("Parando grabación...")
        audio_recorder.stopMicrophonesRecording()
        
        # LEDs verdes para indicar procesamiento
        leds.fadeRGB("FaceLeds", 0x00FF00, 0.3)
        
        # Verificar archivo
        print("Verificando archivo...")
        for attempt in range(10):
            time.sleep(0.5)
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print("✓ Archivo creado: {} ({} bytes)".format(filename, file_size))
                
                # Listar archivos en directorio
                files = os.listdir(recordings_dir)
                print("Archivos en directorio: {}".format(files))
                break
            else:
                print("Intento {}/10 - Archivo no existe aún".format(attempt + 1))
        else:
            print("✗ Archivo NO fue creado")
            
            # Debug del directorio
            try:
                files = os.listdir(recordings_dir)
                print("Archivos en directorio: {}".format(files))
                
                import stat
                dir_stat = os.stat(recordings_dir)
                print("Permisos directorio: {}".format(oct(dir_stat.st_mode)))
            except Exception as e:
                print("Error verificando directorio: {}".format(e))
        
        # Apagar LEDs
        leds.fadeRGB("FaceLeds", 0x000000, 0.3)
        print("Test completado")
        
    except Exception as e:
        print("Error: {}".format(e))

if __name__ == "__main__":
    test_audio_recording()