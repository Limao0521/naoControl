# Sistema NAO Modular v2.0

## Descripción general

Sistema de control para robot NAO refactorizado con arquitectura modular. Proporciona control del robot incluyendo:

- Caminata adaptiva mediante modelos ML
- API WebSocket para control remoto
- Activación por sensores táctiles
- Streaming de video
- Logging centralizado
- Configuración centralizada

## Arquitectura modular

### Principios de diseño

1. Separación de responsabilidades: cada módulo tiene una responsabilidad única.
2. Interfaces y contratos explícitos entre componentes.
3. Dependencia invertida: los módulos consumen abstracciones en lugar de implementaciones concretas.
4. Configuración centralizada en un único archivo de parámetros.
5. Logging estructurado y streaming de eventos.
6. Manejo explícito de errores y modos de simulación.

### Estructura del sistema

```
nao_system/
├── core/
│   ├── config.py
│   └── system_manager.py
├── interfaces/
│   └── base_interfaces.py
├── services/
│   ├── logging_service.py
│   ├── adaptive_walk_service.py
│   ├── websocket_service.py
│   ├── launcher_service.py
│   └── video_service.py
├── adapters/
│   └── nao_adapter.py
├── utils/
│   └── math_utils.py
└── models/
    └── __init__.py

nao_main.py
test_system.py
migrate_to_modular.py
```

## Migración desde el sistema legacy

### Comparación funcional

| Funcionalidad | Sistema legacy | Sistema modular v2.0 | Mejoras |
|---------------|----------------|----------------------|---------|
| Caminata adaptiva | `adaptive_walk_lightgbm_nao.py` | `services/adaptive_walk_service.py` | Modular, testeable, con límites de seguridad |
| Servidor WebSocket | `control_server.py` | `services/websocket_service.py` | Separación de responsabilidades, API clara |
| Control táctil | `launcher.py` | `services/launcher_service.py` | Servicio independiente, más robusto |
| Logging | `logger.py` | `services/logging_service.py` | Centralizado y con streaming opcional |
| Video streaming | `video_stream.py` | `services/video_service.py` | Configurable, encapsulado |
| Comunicación NAO | Código disperso | `adapters/nao_adapter.py` | Encapsulado y con modo simulación |
| Configuración | Hardcode | `core/config.py` | Centralizado |
| Coordinación | Manual | `core/system_manager.py` | Orquestación centralizada |

## Funcionalidades principales

### Caminata adaptiva

- Modelos LightGBM para predicción de parámetros de marcha.
- Modos: `production` (parámetros optimizados) y `training` (ajuste con ML).
- Adaptación según tipo de movimiento: avance, retroceso, lateral, giro.
- Límites de seguridad aplicados antes de ejecutar cualquier comando.
- Parámetros por tipo de superficie configurables.

Uso básico:

```python
adaptive_walk = system.get_service('adaptive_walk')
adaptive_walk.set_mode('production')
adaptive_walk.start_adaptive_walk(x=0.02, y=0.0, theta=0.0)
```

### API WebSocket

- Puerto por defecto: configurado en `core/config.py` (por ejemplo 6671).
- Comandos JSON soportados: `walk`, `stop`, `posture`, `say`, `adaptiveWalk`, `getSensorData`, `getStatus`.

Ejemplo de cliente JavaScript (esquemático):

```javascript
const ws = new WebSocket('ws://nao_ip:6671');
ws.send(JSON.stringify({ action: 'walk', x: 0.1, y: 0.0, theta: 0.0 }));
```

### Control por sensores táctiles

- Detección de presión prolongada (configurable, por defecto 3 segundos) en el sensor medio de la cabeza.
- Alternancia entre modo de control remoto y modo Choregraphe: el servicio pausará o reanudará los servicios necesarios.
- Retroalimentación mediante síntesis de voz (TTS) cuando esté disponible.

### Streaming de video

- Integración con `ALVideoDevice` cuando NAOqi está disponible.
- Soporta streaming MJPEG para navegadores y envío por UDP para consumidores remotos.
- Configuración de resolución y FPS en `core/config.py`.

### Sistema de logging

- Streaming de logs opcional vía WebSocket (puerto configurable).
- Persistencia local en archivo de logs.
- Buffer circular en memoria para las entradas recientes.
- Clasificación por módulo y niveles estándar (DEBUG/INFO/WARNING/ERROR/CRITICAL).

### Configuración

Configuración centralizada en `core/config.py`. Ejemplo de parámetros relevantes:

```python
NAO_IP = '127.0.0.1'
WEBSOCKET_PORT = 6671
LOG_WEBSOCKET_PORT = 6672
SAFETY_LIMITS = {
    'max_velocity': { 'vx': 0.3, 'vy': 0.3, 'wz': 1.0 }
}
OPTIMAL_GRASS_PARAMS = { 'StepHeight': 0.025, 'MaxStepX': 0.045 }
```

## Componentes principales

### SystemManager (`core/system_manager.py`)

Responsabilidad: orquestar el ciclo de vida de los servicios y proveer una API unificada para operaciones comunes.

Características principales:
- Inicio/parada coordinada de servicios.
- API de alto nivel: `walk`, `stop_walk`, `set_posture`, `say`, `get_system_status`.
- Modo simulación cuando NAOqi no está disponible.

### Interfaces (`interfaces/base_interfaces.py`)

Definición de contratos para `ILogger`, `IMotionService`, `IAdaptiveWalk`, `ISensorReader`, `IWebSocketServer` y `ISystemManager`.

### Servicios destacados

- `AdaptiveWalkService`: encapsula la lógica de predicción y aplicación de parámetros de marcha.
- `WebSocketService`: expone la API JSON para control remoto y consulta de estado.
- `LoggingService`: gestor de logs, persistencia y streaming.
- `LauncherService`: monitor de sensores táctiles para alternancia de modos.
- `VideoService`: captura y distribución de video desde NAO.

### Adaptadores

- `NAOAdapter`: gestión segura de proxies NAOqi, reconexión y modo simulación.

### Utilidades

- `math_utils.py` proporciona funciones de uso común como `clamp`, `lerp` y validadores de velocidad.

## Uso

### Inicio rápido en desarrollo

```
cd scripts
python nao_main.py       # Ejecuta el sistema principal en modo desarrollo
python test_system.py    # Ejecuta la suite de pruebas integrada
python migrate_to_modular.py  # Script de migración y verificación
```

### Uso programático

```python
from nao_system.core.system_manager import get_system_manager
system = get_system_manager()
system.walk(0.1, 0.0, 0.0)
system.stop_walk()
system.set_posture('Stand')
system.say('Hola mundo')
```

### Ejecución en robot real

1. Ajustar `NAO_IP` en `core/config.py`.
2. Verificar que NAOqi esté disponible en el entorno Python.
3. Ejecutar `python nao_main.py` en la máquina que controle el robot.

## Migración y compatibilidad

- Los archivos originales fueron respaldados en `backup_YYYYMMDD_HHMMSS/` antes de eliminar el código legacy.
- La API WebSocket mantiene compatibilidad con clientes existentes mediante los mismos comandos JSON principales.
- La carpeta `nao_system/models/` se utiliza para modelos LightGBM; si no hay modelos presentes, el servicio de caminata adaptiva funciona con parámetros por defecto.

## Diagnóstico y debugging

Pasos recomendados:

1. Ejecutar `python test_system.py`.
2. Consultar `get_system_status()` para estado de servicios.
3. Revisar logs en consola o el archivo local configurado.
4. Verificar `core/config.py` para parámetros de red y límites de seguridad.

## Recomendaciones y próximos pasos

- Probar en robot real con NAOqi para validar captura de video y control físico.
- Copiar modelos LightGBM a `nao_system/models/` si están disponibles.
- Sustituir los stubs de WebSocket por una implementación de servidor en producción si se requiere mayor rendimiento o características.
- Añadir tests unitarios adicionales y una integración continua para validación automática.

## Créditos y cierre

Sistema desarrollado y migrado para proporcionar una base modular, testable y mantenible para control de robots NAO.

Hecho con amor por andres azcona
