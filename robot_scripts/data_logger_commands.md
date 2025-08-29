# Comandos WebSocket para Data Logger

El control server ahora incluye acciones para controlar el data logger remotamente vía WebSocket.

## Configuración WebSocket

- **URL**: `ws://localhost:6671` (o la IP del NAO)
- **Protocolo**: WebSocket
- **Formato**: JSON

## Comandos disponibles

### 1. Iniciar logging

```json
{
  "action": "startLogging",
  "duration": 300,
  "frequency": 10,
  "output": "/home/nao/logs/test_session.csv"
}
```

Parámetros:
- `duration`: Duración en segundos (opcional, default: 300)
- `frequency`: Frecuencia de muestreo en Hz (opcional, default: 10)
- `output`: Archivo de salida (opcional, se genera automáticamente si no se especifica)

Respuesta exitosa:
```json
{
  "startLogging": {
    "success": true,
    "output": "/home/nao/logs/test_session.csv",
    "duration": 300,
    "frequency": 10
  }
}
```

### 2. Detener logging

```json
{
  "action": "stopLogging"
}
```

Respuesta exitosa:
```json
{
  "stopLogging": {
    "success": true,
    "samples": 1234
  }
}
```

### 3. Obtener estado del logging

```json
{
  "action": "getLoggingStatus"
}
```

Respuesta:
```json
{
  "loggingStatus": {
    "active": true,
    "available": true,
    "samples": 567,
    "output": "/home/nao/logs/test_session.csv"
  }
}
```

### 4. Registrar una muestra manual

```json
{
  "action": "logSample"
}
```

Respuesta:
```json
{
  "logSample": {
    "success": true,
    "samples": 568
  }
}
```

## Flujo de trabajo típico

1. **Verificar estado**: Usar `getLoggingStatus` para ver si está disponible
2. **Iniciar logging**: Usar `startLogging` con parámetros deseados
3. **Ejecutar movimientos**: Usar comandos como `walk`, `walkTo`, `turnLeft`, etc.
4. **Monitorear progreso**: Usar `getLoggingStatus` periódicamente
5. **Detener logging**: Usar `stopLogging` cuando termine la sesión

## Ejemplo de secuencia completa

```json
// 1. Verificar estado
{"action": "getLoggingStatus"}

// 2. Iniciar logging de 5 minutos a 10Hz
{
  "action": "startLogging",
  "duration": 300,
  "frequency": 10
}

// 3. Realizar movimientos (ejemplos)
{"action": "walk", "vx": 0.3, "vy": 0, "wz": 0}
{"action": "turnLeft", "speed": 0.5, "duration": 2}
{"action": "walkTo", "x": 1.0, "y": 0, "theta": 0}

// 4. Detener logging
{"action": "stopLogging"}
```

## Comandos para Postman

Si usas Postman para WebSocket:

1. **Nueva conexión WebSocket**: `ws://localhost:6671`
2. **Enviar mensajes JSON** como los ejemplos de arriba
3. **Observar respuestas** en tiempo real

## Comandos curl para testing HTTP → WebSocket

Si prefieres curl, puedes usar websocat o herramientas similares:

```bash
# Instalar websocat
cargo install websocat

# Conectar y enviar comando
echo '{"action":"getLoggingStatus"}' | websocat ws://localhost:6671
```

## Archivos CSV generados

Los archivos CSV tendrán estas columnas:
- Features de sensores: `accel_x`, `accel_y`, `accel_z`, `gyro_x`, `gyro_y`, `gyro_z`, `angle_x`, `angle_y`
- Presión de pies: `lfoot_fl`, `lfoot_fr`, `lfoot_rl`, `lfoot_rr`, `rfoot_fl`, `rfoot_fr`, `rfoot_rl`, `rfoot_rr`
- Velocidades: `vx`, `vy`, `wz`, `vtotal`
- Parámetros de marcha: `StepHeight`, `MaxStepX`, `MaxStepY`, `MaxStepTheta`, `Frequency`
- Timestamp: `timestamp`

Estos CSV son compatibles con `retrain_from_logs.py` para reentrenar el modelo RandomForest.
