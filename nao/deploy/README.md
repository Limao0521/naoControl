# NAO Control - Deploy Scripts

## Descripción

Este directorio contiene scripts para automatizar el despliegue del sistema de control en el robot NAO.

## Estructura del Robot

```
/home/nao/
├── scripts/
│   └── runtime/
│       ├── control_server.py          # Servidor monolítico (legacy)
│       ├── launcher.py                 # Launcher con touch de cabeza
│       ├── logger.py                   # Sistema de logging
│       ├── data_logger.py              # Data logger CSV
│       ├── record_system.py            # Sistema de grabación
│       ├── video_stream.py             # Streaming de video
│       ├── adaptive_walk_lightgbm_nao.py  # IA adaptativa
│       │
│       └── control_server/             # NUEVO: Arquitectura modular
│           ├── __init__.py
│           ├── base_command.py         # Command Pattern
│           ├── command_factory.py      # Factory Pattern
│           ├── server.py               # Servidor modular
│           │
│           ├── facades/
│           │   └── nao_facade.py       # Facade NAOqi
│           │
│           ├── strategies/
│           │   └── movement_strategies.py  # Strategy Pattern
│           │
│           ├── commands/               # Comandos individuales
│           │   ├── movement_commands.py
│           │   ├── basic_commands.py
│           │   ├── led_commands.py
│           │   ├── system_commands.py
│           │   ├── behavior_commands.py
│           │   ├── gait_commands.py
│           │   ├── adaptive_commands.py
│           │   ├── logging_commands.py
│           │   ├── record_commands.py
│           │   └── safety_commands.py
│           │
│           └── libs/                   # Utilidades
│               ├── sensor_reader.py
│               ├── gait_utils.py
│               └── motion_helpers.py
│
├── models/
│   └── models_npz_automl/              # Modelos LightGBM
│       ├── gait_model_production.npz
│       └── metadata.json
│
├── logs/                               # Logs CSV generados
│
├── Webs/
│   └── ControllerWebServer/            # Frontend web
│
└── SimpleWebSocketServer-0.1.2/        # Librería WebSocket
```

## Uso

### Deploy Automático

```bash
# Instalar en robot
python deploy.py 192.168.1.100

# Limpiar e instalar
python deploy.py 192.168.1.100 --clean

# Con credenciales personalizadas
python deploy.py 192.168.1.100 --user nao --password mypassword
```

### Deploy Manual

1. **Conectar por SSH:**
   ```bash
   ssh nao@<NAO_IP>
   # Password: nao
   ```

2. **Crear estructura:**
   ```bash
   mkdir -p /home/nao/scripts/runtime/control_server/{commands,facades,strategies,libs}
   mkdir -p /home/nao/models/models_npz_automl
   mkdir -p /home/nao/logs
   ```

3. **Copiar archivos:**
   ```bash
   # Desde tu PC
   scp -r nao/scripts/runtime/* nao@<NAO_IP>:/home/nao/scripts/runtime/
   scp -r nao/models/* nao@<NAO_IP>:/home/nao/models/
   ```

4. **Verificar:**
   ```bash
   ssh nao@<NAO_IP> 'ls -la /home/nao/scripts/runtime/control_server/'
   ```

## Iniciar el Sistema

### Opción 1: Servidor directo
```bash
ssh nao@<NAO_IP> 'python /home/nao/scripts/runtime/control_server.py'
```

### Opción 2: Servidor modular (recomendado)
```bash
ssh nao@<NAO_IP> 'python /home/nao/scripts/runtime/control_server/server.py'
```

### Opción 3: Launcher con touch de cabeza
```bash
ssh nao@<NAO_IP> 'python /home/nao/scripts/runtime/launcher.py &'
# Luego presiona el sensor táctil medio de la cabeza por 3+ segundos
```

## Verificar Funcionamiento

1. **Conectar WebSocket:**
   ```
   ws://<NAO_IP>:6671
   ```

2. **Enviar comando de prueba:**
   ```json
   {"action": "getBattery"}
   ```

3. **Respuesta esperada:**
   ```json
   {"battery": 85, "low": false, "full": false}
   ```

## Dependencias en el Robot

- Python 2.7 (incluido en NAOqi)
- SimpleWebSocketServer (copiar a /home/nao/)
- NAOqi SDK (incluido en el robot)

## Troubleshooting

### Error: "Puerto ocupado"
```bash
# Matar procesos anteriores
ssh nao@<NAO_IP> 'pkill -f control_server'
```

### Error: "Import NAOqi"
Verificar que estés usando Python 2.7 del sistema NAO.

### Error: "SimpleWebSocketServer not found"
```bash
# Copiar librería
scp -r SimpleWebSocketServer-0.1.2 nao@<NAO_IP>:/home/nao/
```
