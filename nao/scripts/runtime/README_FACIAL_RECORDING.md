# Sistema de Grabación con Reconocimiento Facial

Sistema automatizado de grabación de video para el robot NAO que utiliza reconocimiento facial para iniciar el proceso y control físico mediante bumper para grabar.

## Características

- ✅ **Reconocimiento facial automático**: El robot busca y detecta rostros
- ✅ **Confirmación visual con LEDs**: 
  - Ojo izquierdo verde = rostro detectado
  - Ojo derecho verde = grabación activa
- ✅ **Control físico simple**: Bumper derecho para iniciar/detener grabación
- ✅ **Misma calidad que video_stream**: Resolución y FPS configurables
- ✅ **Grabación en formato AVI**: Compatible con reproductores estándar

## Funcionamiento

1. **Inicio del sistema**: El robot comienza buscando rostros
2. **Detección**: Al encontrar un rostro, el ojo izquierdo se pone verde
3. **Iniciar grabación**: Presiona el bumper derecho → ojo derecho verde
4. **Detener grabación**: Presiona nuevamente el bumper derecho
5. **Archivos guardados**: En `nao/data/records/` con timestamp

## Uso

### Conexión SSH al robot

```bash
ssh nao@<IP_DEL_ROBOT>
# Contraseña por defecto: nao
```

### Navegación al directorio

```bash
cd /home/nao/naoControl/scripts/runtime
```

### Ejecución básica

```bash
python facial_recording.py --nao_ip 127.0.0.1
```

### Ejecución con opciones personalizadas

```bash
# Resolución 640x480 a 25 FPS
python facial_recording.py --nao_ip 127.0.0.1 --resolution 2 --fps 25

# Resolución HD 1280x960 a 15 FPS (para mejor calidad)
python facial_recording.py --nao_ip 127.0.0.1 --resolution 3 --fps 15
```

## Parámetros

| Parámetro | Descripción | Valores | Default |
|-----------|-------------|---------|---------|
| `--nao_ip` | IP del robot NAO | IP address | **Requerido** |
| `--nao_port` | Puerto NAOqi | Número | 9559 |
| `--fps` | Frames por segundo | 1-30 | 30 |
| `--resolution` | Resolución de video | 0-3 | 1 (320x240) |

### Opciones de resolución:

- `0` = 160x120 (muy baja)
- `1` = 320x240 (recomendada para pruebas)
- `2` = 640x480 (buena calidad)
- `3` = 1280x960 (alta calidad, requiere FPS más bajo)

## Indicadores Visuales

| LED | Color | Significado |
|-----|-------|-------------|
| Ojo izquierdo | 🟢 Verde | Rostro detectado y sistema listo |
| Ojo derecho | 🟢 Verde | Grabación en curso |
| Ambos ojos | ⚫ Apagados | Buscando rostro |

## Controles

- **Bumper derecho**: Alternar grabación (iniciar/detener)
- **Ctrl+C**: Salir del programa (detiene grabación automáticamente)

## Archivos de Salida

Los videos se guardan en: `nao/data/records/`

Formato de nombre: `face_recording_YYYYMMDD_HHMMSS.avi`

Ejemplo: `face_recording_20260206_143052.avi`

## Flujo de Trabajo Típico

```
1. Ejecutar script
   ↓
2. Robot dice "Buscando rostro"
   ↓
3. Posicionarse frente al robot
   ↓
4. Robot dice "Rostro detectado" + ojo izquierdo verde
   ↓
5. Presionar bumper derecho
   ↓
6. Robot dice "Grabación iniciada" + ojo derecho verde
   ↓
7. Realizar actividad a grabar
   ↓
8. Presionar bumper derecho nuevamente
   ↓
9. Robot dice "Grabación detenida"
   ↓
10. Video guardado en data/records/
```

## Solución de Problemas

### El robot no detecta rostros

- Asegúrate de estar a 1-3 metros del robot
- Verifica que haya buena iluminación
- El rostro debe estar de frente a la cámara
- Espera hasta 5 minutos (timeout máximo)

### No se inicia la grabación

- Verifica que el ojo izquierdo esté verde (rostro detectado)
- Asegúrate de presionar el bumper derecho (no el izquierdo)
- Revisa los logs para errores

### La grabación no tiene video

- Verifica que el directorio `data/records/` exista
- Comprueba permisos de escritura
- Revisa el espacio en disco del robot

### Calidad de video baja

- Aumenta la resolución: `--resolution 2` o `--resolution 3`
- Reduce FPS si la resolución es alta: `--fps 15`
- Balance recomendado: resolución 2, fps 25

## Ejemplo de Sesión Completa

```bash
# 1. Conectar por SSH
ssh nao@192.168.1.100

# 2. Navegar al directorio
cd /home/nao/naoControl/scripts/runtime

# 3. Ejecutar sistema
python facial_recording.py --nao_ip 127.0.0.1 --resolution 2 --fps 25

# Salida esperada:
# INFO [FACIAL_REC] === SISTEMA DE GRABACIÓN CON RECONOCIMIENTO FACIAL ===
# INFO [FACIAL_REC] Buscando rostro...
# INFO [FACIAL_REC] ¡Rostro detectado!
# INFO [FACIAL_REC] Sistema listo. Presiona el bumper derecho para grabar/detener.
# 
# [Presionar bumper derecho]
# INFO [FACIAL_REC] Grabación iniciada: /home/nao/naoControl/data/records/face_recording_20260206_143052.avi
# INFO [FACIAL_REC] Frames grabados: 100
# INFO [FACIAL_REC] Frames grabados: 200
# 
# [Presionar bumper derecho nuevamente]
# INFO [FACIAL_REC] Grabación detenida: /home/nao/naoControl/data/records/face_recording_20260206_143052.avi
# INFO [FACIAL_REC] Archivo guardado: ... (5.23 MB)

# 4. Salir con Ctrl+C

# 5. Transferir video a PC (desde tu PC, no desde el robot)
scp nao@192.168.1.100:/home/nao/naoControl/data/records/face_recording_*.avi ./
```

## Notas Técnicas

- **Codec**: XVID (compatible con la mayoría de reproductores)
- **Calidad JPEG**: 75% (balance entre calidad y tamaño)
- **Colorspace**: BGR (compatible con OpenCV)
- **Cooldown del bumper**: 500ms para evitar rebotes
- **Timeout detección facial**: 5 minutos

## Dependencias

- Python 2.7 (NAOqi)
- OpenCV (cv2)
- NAOqi SDK
- numpy

## Ver También

- [video_stream.py](video_stream.py) - Sistema de streaming de video
- [logger.py](logger.py) - Sistema de logging
