# Control Server v2.0 - Arquitectura Modular

## Descripción

El Control Server v2.0 es una refactorización completa del servidor WebSocket monolítico original, implementando una arquitectura modular basada en patrones de diseño probados para mejorar la mantenibilidad, extensibilidad y testabilidad del código.

## Arquitectura

### Patrones de Diseño Implementados

1. **Command Pattern** - Cada acción WebSocket es encapsulada como un comando independiente
2. **Strategy Pattern** - Diferentes estrategias de movimiento (manual, adaptativo, cauteloso)
3. **Factory Pattern** - Centraliza la creación de comandos basados en el action recibido
4. **Facade Pattern** - Simplifica la interfaz con NAOqi y manejo de errores
5. **Observer Pattern** - Para eventos y sistema de logging (futuro)

### Estructura del Proyecto

```
control_server/
├── __init__.py                 # Información del paquete
├── base_command.py             # Interfaz base para comandos (Command Pattern)
├── command_factory.py          # Factory para crear comandos
├── server.py                   # Servidor principal refactorizado
├── facades/
│   └── nao_facade.py          # Facade para NAOqi (simplifica acceso)
├── strategies/
│   └── movement_strategies.py  # Strategy Pattern para movimiento
└── commands/
    ├── movement_commands.py    # Comandos de movimiento
    ├── basic_commands.py       # Comandos básicos (TTS, articulaciones)
    ├── led_commands.py         # Comandos de LEDs
    ├── system_commands.py      # Comandos de sistema
    ├── behavior_commands.py    # Comandos de behaviors
    ├── gait_commands.py        # Comandos de configuración de marcha
    ├── adaptive_commands.py    # Comandos adaptativos LightGBM
    ├── logging_commands.py     # Comandos de data logging
    ├── record_commands.py      # Comandos de grabación
    └── safety_commands.py      # Comandos de seguridad
```

## Ventajas de la Nueva Arquitectura

### 1. **Mantenibilidad**
- Separación clara de responsabilidades
- Código modular y fácil de entender
- Cada comando es independiente

### 2. **Extensibilidad**
- Fácil agregar nuevos comandos creando nueva clase
- Nuevas estrategias de movimiento sin afectar código existente
- Registro dinámico de comandos

### 3. **Testabilidad**
- Cada comando se puede testear de forma aislada
- Mocking facilitado por la inyección de dependencias
- Facade permite tests sin NAOqi real

### 4. **Reutilización**
- Componentes reutilizables entre diferentes comandos
- Facade centraliza operaciones comunes de NAOqi
- Estrategias intercambiables

## Migración desde v1.0

### Cambios Principales

1. **Estructura de Archivos**:
   ```bash
   # Antes (monolítico)
   control_server.py (1100+ líneas)
   
   # Después (modular)
   control_server/
   ├── server.py (200 líneas)
   ├── facades/nao_facade.py
   ├── commands/*.py
   └── strategies/*.py
   ```

2. **Punto de Entrada**:
   ```bash
   # Antes
   python2 control_server.py
   
   # Después  
   python2 control_server/server.py
   ```

3. **Adición de Comandos**:
   ```python
   # Antes: Editar elif gigante en control_server.py
   elif action == "newAction":
       # 50+ líneas de código inline
   
   # Después: Crear nueva clase
   class NewActionCommand(BaseCommand):
       def execute(self, message, websocket):
           # Lógica encapsulada
   ```

### Retrocompatibilidad

- **API WebSocket**: 100% compatible con clientes existentes
- **Mensajes JSON**: Mismo formato de entrada y salida
- **Funcionalidad**: Todas las características preserved

## Uso

### Iniciar Servidor
```bash
cd /data/home/nao/scripts/runtime
python2 control_server/server.py
```

### Crear Nuevo Comando

1. **Crear clase de comando**:
```python
# En commands/my_commands.py
class MyNewCommand(BaseCommand):
    def execute(self, message, websocket):
        # Tu lógica aquí
        param = self.get_param_safe(message, "param", default_value)
        success = self.nao.some_operation(param)
        
        if success:
            self.send_success_response(websocket, "myAction", {"result": param})
        else:
            self.send_error_response(websocket, "myAction", "Error message")
        
        return success
    
    def get_action_name(self):
        return "myAction"
```

2. **Registrar en Factory**:
```python
# En command_factory.py
self.command_classes['myAction'] = MyNewCommand
```

### Cambiar Estrategia de Movimiento

```python
# El MovementContext permite cambiar estrategias dinámicamente
movement_context.set_strategy('adaptive')  # Usar LightGBM
movement_context.set_strategy('manual')    # Movimiento manual
movement_context.set_strategy('cautious')  # Límites restrictivos
```

## API de Comandos

### Comandos de Movimiento
- `walk` - Movimiento reactivo con estrategias
- `walkTo` - Movimiento a posición específica
- `turnLeft`/`turnRight` - Giros con duración o continuos
- `posture` - Cambio de postura

### Comandos Básicos
- `move` - Movimiento directo de articulaciones
- `say` - Text-to-Speech
- `language` - Cambio de idioma TTS
- `volume` - Control de volumen

### Comandos del Sistema
- `getBattery` - Nivel de batería
- `autonomous` - Control Autonomous Life
- `getConfig` - Configuración actual

### Comandos Avanzados
- `adaptiveLightGBM` - Control de movimiento adaptativo
- `recordMode` - Sistema de grabación de voz
- `startLogging` - Data logging para ML

## Configuración

### Parámetros Principales
```python
# En server.py
IP_NAO = "127.0.0.1"      # IP del robot
PORT_NAO = 9559           # Puerto NAOqi
WS_PORT = 6671            # Puerto WebSocket
WATCHDOG = 0.6            # Timeout en segundos
```

### Health Check
El servidor incluye verificación de salud de conexiones NAOqi:
```json
{
  "health_score": 100.0,
  "available_proxies": ["motion", "posture", "leds", ...],
  "is_healthy": true
}
```

## Desarrollo y Testing

### Estructura para Tests
```
tests/
├── test_commands/
├── test_strategies/
├── test_facades/
└── mocks/
```

### Logging
El sistema usa logging centralizado con niveles:
```python
logger.debug("Información de debugging")
logger.info("Información general")
logger.warning("Advertencias") 
logger.error("Errores recuperables")
logger.critical("Errores fatales")
```

## Futuras Mejoras

1. **Observer Pattern** completo para eventos
2. **Decorator Pattern** para validation y caching
3. **State Pattern** para estados del robot
4. **Plugin System** para comandos dinámicos
5. **Configuration Management** externalizado
6. **Metrics y Monitoring** integrados
7. **Security Layer** para autenticación

## Contribución

Para añadir nuevas funcionalidades:

1. Crear comando en `commands/` extendiendo `BaseCommand`
2. Registrar en `CommandFactory` 
3. Añadir tests correspondientes
4. Actualizar documentación
5. Mantener compatibilidad de API

---

**Control Server v2.0** - Arquitectura modular para control robótico NAO