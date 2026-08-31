# NAO Control Suite v2.0

> Sistema de tele-operación y control remoto para robots NAO
> Compatible con Python 2.7 + NAOqi 2.8

---

## 📖 Descripción

NAO Control Suite es un sistema completo de control remoto para robots NAO V6 desde cualquier navegador web (móvil o PC). El sistema incluye:

- **Tele-operación** de locomoción con joystick virtual
- **Control articular** de brazos y cabeza
- **Behaviors/Danzas**: kick, siu, saxophone, taichichua, gangnamstyle, elephant, disco, macarena
- **Control de LEDs** RGB por grupos
- **Síntesis de voz** (TTS)
- **Video streaming** en tiempo real
- **Sistema adaptativo** de marcha con Machine Learning (LightGBM)
- **Logging centralizado** vía WebSocket

---

## 🏗️ Estructura del Proyecto

```
naoControl/
├── README.md                     # Este archivo
├── requirements.txt              # Dependencias PC (desarrollo)
│
├── Frontend/
│   ├── ControllerWebServer/      # Build de producción (servir directamente)
│   └── NaoControlReact/          # Código fuente React
│
├── nao/                          # TODO LO QUE VA AL ROBOT
│   ├── README_NAO.md             # Instrucciones específicas NAO
│   ├── requirements-robot.txt   # Dependencias robot
│   │
│   ├── assets/
│   │   └── Behaivors/            # Behaviors Choregraphe (.pml)
│   │       ├── disco/
│   │       ├── Elephant/
│   │       ├── GangnamStyle/
│   │       ├── nao-kick/
│   │       ├── Saxophone/
│   │       ├── siu/
│   │       └── taichichua/
│   │
│   ├── data/
│   │   ├── analysis/             # Reportes de análisis de marcha
│   │   ├── records/              # Grabaciones de audio
│   │   └── walks/                # Datasets de caminata (.csv)
│   │
│   ├── deploy/                   # Scripts de despliegue automático
│   │   ├── deploy.py
│   │   ├── install.ps1
│   │   ├── install.sh
│   │   └── structure.json
│   │
│   ├── models/                   # Modelos ML para marcha adaptativa
│   │   ├── lightgbm_model_*.npz
│   │   ├── feature_scaler.npz
│   │   └── golden_parameters.csv
│   │
│   └── scripts/
│       ├── nao_config.py         # Configuración global
│       ├── nao_connection_test.py
│       │
│       ├── runtime/              # ⭐ SISTEMA PRINCIPAL
│       │   ├── launcher.py       # Punto de entrada (sensor táctil)
│       │   ├── logger.py         # Sistema de logging WebSocket/UDP
│       │   ├── video_stream.py   # Streaming MJPEG
│       │   ├── data_logger.py    # Logger de datos para ML
│       │   │
│       │   └── control_server/   # ⭐ BACKEND MODULAR
│       │       ├── server.py     # Servidor WebSocket principal
│       │       ├── command_factory.py
│       │       ├── base_command.py
│       │       │
│       │       ├── commands/     # Comandos (Command Pattern)
│       │       │   ├── movement_commands.py
│       │       │   ├── basic_commands.py
│       │       │   ├── led_commands.py
│       │       │   ├── system_commands.py
│       │       │   ├── behavior_commands.py
│       │       │   ├── gait_commands.py
│       │       │   ├── adaptive_commands.py
│       │       │   ├── logging_commands.py
│       │       │   ├── record_commands.py
│       │       │   └── safety_commands.py
│       │       │
│       │       ├── facades/      # Abstracciones NAOqi
│       │       │   └── nao_facade.py
│       │       │
│       │       └── strategies/   # Estrategias de movimiento
│       │           └── movement_strategies.py
│       │
│       ├── diagnostics/          # Herramientas de diagnóstico
│       └── ml/                   # Scripts ML para robot
│
├── models_automl/                # Resultados AutoML
└── tools/                        # Herramientas de desarrollo (PC)
```
---

## 🔧 Requisitos

## 🚀 Despliegue actual NAO + Nemotron

Desde PowerShell, en la raíz del repositorio, ejecutar:

```powershell
.\tools\deploy-nao.ps1 -NaoIp <IP_ACTUAL_DEL_NAO>
```

Añadir `-StartServices` si se desea iniciar los servicios inmediatamente tras
el despliegue. El script preserva el secreto del robot y no copia `.env` ni las
credenciales NVIDIA. La guía operativa actual está en `docs/nemotron/physical-test.md`.

La documentación vigente del sistema se concentra en:

- [Arquitectura y catálogo de responsabilidades](docs/architecture.md)
- [Operación, despliegue y diagnóstico](docs/operations.md)
- [Cambio de proveedor Nemotron/Gemma](docs/nemotron/provider-switching.md)

### Gestión de red desde la web

El gestor de red forma parte del control WebSocket del NAO y queda disponible
automáticamente al iniciar los servicios. No necesita un broker en el PC,
claves SSH adicionales, Nemotron ni credenciales NVIDIA. El menú **Red** usa
el mismo puerto `6671` para consultar, escanear, conectar, desconectar y
eliminar perfiles.

Cada cambio requiere mantener el sensor táctil trasero durante tres segundos.
Consulta `docs/network-management.md` para el flujo completo, los límites de
seguridad y la recuperación tras un cambio de IP.

### Inicio automático de Nemotron en el PC

El gateway pesado se distribuye dentro del paquete del NAO, pero se ejecuta en
el PC. En cada PC nuevo se prepara una sola vez un lanzador ligero y autenticado
desde PowerShell con permisos de administrador:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\setup-nemotron-pc-host.ps1" -NaoIp <NAO_IP>
```

Luego, ese PC abre el control web y guarda el proveedor; el NAO infiere su IP
automáticamente como destino del gateway. Al mantener el bumper izquierdo
durante 1.5 segundos, el NAO
envía una solicitud HMAC al puerto `6676`; el PC descarga del NAO el bundle
verificado por el puerto `6677` y arranca el gateway. Ya no es necesario lanzar
`nao_gateway.main` manualmente. Consulta `docs/nemotron/automatic-pc-start.md`.

### En el Robot NAO
- **NAO V6** con NAOqi 2.8
- **Python 2.7** (preinstalado)
- **SimpleWebSocketServer** (se instala manualmente)

### En el PC de Desarrollo
- **Node.js 18+** (para el frontend React)
- **Python 3.8+** (para herramientas de desarrollo)

---

## 📦 Setup Manual en el Robot NAO

### Paso 1: Conectar al Robot

```bash
ssh nao@<NAO_IP>
# Password por defecto: nao
```

### Paso 2: Crear Estructura de Directorios

```bash
mkdir -p /home/nao/scripts/runtime/control_server/commands
mkdir -p /home/nao/scripts/runtime/control_server/facades
mkdir -p /home/nao/scripts/runtime/control_server/strategies
mkdir -p /home/nao/models
mkdir -p /home/nao/datasets/records
mkdir -p /home/nao/datasets/walks
```

### Paso 3: Instalar SimpleWebSocketServer

```bash
cd /home/nao
wget https://github.com/dpallot/simple-websocket-server/archive/refs/heads/master.zip
unzip master.zip
mv simple-websocket-server-master SimpleWebSocketServer-0.1.2
rm master.zip
```

### Paso 4: Copiar Archivos desde PC

Desde tu PC (en la raíz del proyecto):

```bash
# Copiar todo el runtime
scp -r nao/scripts/runtime/* nao@<NAO_IP>:/home/nao/scripts/runtime/

# Copiar modelos ML
scp -r nao/models/* nao@<NAO_IP>:/home/nao/models/

# Copiar configuración
scp nao/scripts/nao_config.py nao@<NAO_IP>:/home/nao/scripts/
```

### Paso 5: Instalar Behaviors desde Choregraphe

⚠️ **IMPORTANTE**: Los behaviors **NO funcionan** simplemente copiando archivos al robot. **DEBEN** ser instalados a través de Choregraphe para que se registren en el PackageManager del robot.

#### Behaviors Incluidos

La carpeta `nao/assets/Behaivors/` contiene proyectos de Choregraphe con las siguientes animaciones:

| Carpeta | Acción WebSocket | Descripción |
|---------|------------------|-------------|
| `disco/` | `{"action": "disco"}` | Baile disco |
| `Elephant/` | `{"action": "elephant"}` | Movimiento de elefante |
| `GangnamStyle/` | `{"action": "gangnamstyle"}` | Baile Gangnam Style |
| `macarena-original/` | `{"action": "macarena"}` | Baile Macarena |
| `nao-kick/` | `{"action": "kick"}` | Patada de fútbol |
| `Saxophone/` | `{"action": "saxophone"}` | Tocar saxofón |
| `siu/` | `{"action": "siu"}` | Celebración Cristiano Ronaldo |
| `taichichua/` | `{"action": "taichichua"}` | Movimientos de Tai Chi |

#### Proceso de Instalación

1. **Abrir Choregraphe** y conectar al robot (Connection → Connect to...)

2. **Para cada behavior**:
   - File → **Open Project** → Seleccionar la carpeta del behavior (ej: `nao/assets/Behaivors/disco/`)
   - Robot → **Upload to robot and Install current project**
   - Esperar a que aparezca "Installation successful"

3. **Verificar instalación**:
   ```bash
   ssh nao@<NAO_IP>
   python2 -c "from naoqi import ALProxy; b=ALProxy('ALBehaviorManager','127.0.0.1',9559); print(b.getInstalledBehaviors())"
   ```

#### Nomenclatura de Behaviors

Cuando Choregraphe instala un behavior, le asigna un nombre con un **hash único**. Por ejemplo:
- `disco-8c59b8/behavior_1`
- `kicknao-f6eb94/behavior_1`
- `siu-17777b/behavior_1`

El archivo `behavior_commands.py` del control server debe tener los nombres **exactos** que muestra `getInstalledBehaviors()`. Si instalas los behaviors en otro robot, los hashes serán diferentes y deberás actualizar los nombres en el código.

#### Cómo Actualizar Nombres de Behaviors

1. Listar behaviors instalados en el robot:
   ```bash
   ls /home/nao/.local/share/PackageManager/apps/
   ```

2. Editar `nao/scripts/runtime/control_server/commands/behavior_commands.py`

3. Actualizar el `behavior_name` de cada comando con el nombre correcto:
   ```python
   class DiscoCommand(BehaviorCommand):
       def __init__(self):
           self.behavior_name = "disco-XXXXXX/behavior_1"  # Reemplazar XXXXXX con tu hash
   ```

4. Re-copiar el archivo al robot:
   ```bash
   scp nao/scripts/runtime/control_server/commands/behavior_commands.py nao@<NAO_IP>:/home/nao/scripts/runtime/control_server/commands/
   ```

### Paso 6: Verificar Estructura Final en Robot

```bash
ssh nao@<NAO_IP>
find /home/nao/scripts/runtime -type f -name "*.py" | head -20
```

---

## 🚀 Ejecución

### Iniciar Sistema Completo (Recomendado)

```bash
ssh nao@<NAO_IP>
cd /home/nao/scripts/runtime
python2 launcher.py
```

El launcher:
1. Inicia el **Logger** (WebSocket puerto 6672, UDP puerto 6673)
2. Inicia el **Control Server** (WebSocket puerto 6671)
3. Inicia el **Video Stream** (HTTP puerto 8080)
4. Escucha **sensor táctil** de la cabeza para alternar modos

**Control por sensor táctil:**
- **Presión larga (3+ segundos)** en sensor medio: Alterna entre modo Control y modo Choregraphe
- El modo Choregraphe desactiva los servicios para permitir uso de Choregraphe

### Iniciar Componentes Individuales

```bash
# Solo Control Server
cd /home/nao/scripts/runtime/control_server
python2 server.py

# Solo Logger
cd /home/nao/scripts/runtime
python2 logger.py

# Solo Video
cd /home/nao/scripts/runtime
python2 video_stream.py
```

### Ejecución en Background

```bash
nohup python2 /home/nao/scripts/runtime/launcher.py > /tmp/nao_launcher.log 2>&1 &
```

### Auto-inicio al Encender

Añadir a `/home/nao/naoqi/preferences/autoload.ini`:
```ini
[user]
/home/nao/scripts/runtime/launcher.py
```

O crear un cron job:
```bash
crontab -e
# Añadir:
@reboot sleep 30 && python2 /home/nao/scripts/runtime/launcher.py > /tmp/nao_launcher.log 2>&1
```

---

## 🎮 Comandos WebSocket Disponibles

Conectar a `ws://<NAO_IP>:6671`

### Movimiento
| Acción | Ejemplo JSON |
|--------|--------------|
| Caminar | `{"action": "walk", "vx": 0.5, "vy": 0, "wz": 0}` |
| Caminar a punto | `{"action": "walkTo", "x": 1.0, "y": 0, "theta": 0}` |
| Girar izquierda | `{"action": "turnLeft"}` |
| Girar derecha | `{"action": "turnRight"}` |
| Postura | `{"action": "posture", "value": "Stand"}` |

### Articulaciones
```json
{"action": "move", "joint": "HeadYaw", "value": 0.5, "speed": 0.1}
```

Articulaciones disponibles: `HeadYaw`, `HeadPitch`, `LShoulderPitch`, `LShoulderRoll`, `LElbowYaw`, `LElbowRoll`, `LWristYaw`, `RShoulderPitch`, `RShoulderRoll`, `RElbowYaw`, `RElbowRoll`, `RWristYaw`, `LHipYawPitch`, `LHipRoll`, `LHipPitch`, `LKneePitch`, `LAnklePitch`, `LAnkleRoll`, `RHipRoll`, `RHipPitch`, `RKneePitch`, `RAnklePitch`, `RAnkleRoll`

### Behaviors (Danzas)
| Acción | Descripción |
|--------|-------------|
| `{"action": "kick"}` | Patada de fútbol |
| `{"action": "siu"}` | Celebración Cristiano Ronaldo |
| `{"action": "saxophone"}` | Tocar saxofón |
| `{"action": "taichichua"}` | Tai Chi |
| `{"action": "gangnamstyle"}` | Baile Gangnam Style |
| `{"action": "elephant"}` | Elefante |
| `{"action": "disco"}` | Baile disco |
| `{"action": "macarena"}` | Macarena |
| `{"action": "listBehaviors"}` | Listar behaviors instalados |
| `{"action": "stopBehavior"}` | Detener behavior actual |

### LEDs
```json
{"action": "led", "group": "FaceLeds", "r": 1.0, "g": 0, "b": 0, "duration": 0.5}
```

Grupos de LEDs: `ChestLeds`, `FaceLeds`, `LeftEarLeds`, `RightEarLeds`, `LeftFootLeds`, `RightFootLeds`, `BrainLeds`

### Voz
| Acción | Ejemplo |
|--------|---------|
| Hablar | `{"action": "say", "text": "Hola mundo"}` |
| Idioma | `{"action": "language", "value": "Spanish"}` |
| Volumen | `{"action": "volume", "value": 80}` |

### Sistema
| Acción | Descripción |
|--------|-------------|
| `{"action": "getBattery"}` | Nivel de batería |
| `{"action": "getAutonomousLife"}` | Estado de vida autónoma |
| `{"action": "autonomous", "value": false}` | Activar/desactivar vida autónoma |
| `{"action": "getConfig"}` | Configuración actual |

### Marcha Adaptativa (ML)
| Acción | Descripción |
|--------|-------------|
| `{"action": "gait", "MaxStepX": 0.04, ...}` | Configurar parámetros de marcha |
| `{"action": "getGait"}` | Obtener parámetros actuales |
| `{"action": "resetGait"}` | Restaurar parámetros por defecto |
| `{"action": "gaitPreset", "preset": "fast"}` | Aplicar preset (fast/slow/stable) |
| `{"action": "adaptiveLightGBM", "enable": true}` | Activar modo adaptativo ML |
| `{"action": "setAdaptiveMode", "mode": "manual"}` | Cambiar modo (manual/adaptive/cautious) |

### Seguridad
| Acción | Descripción |
|--------|-------------|
| `{"action": "footProtection", "enable": true}` | Protección de contacto de pie |
| `{"action": "fallManager", "enable": false}` | Gestión de caídas |
| `{"action": "forceDisableFallManager"}` | Forzar desactivación de fall manager |

---

## 🌐 Frontend Web

### Desarrollo
```bash
cd Frontend/NaoControlReact
npm install
npm start
```

### Producción
Servir la carpeta `Frontend/ControllerWebServer/` con cualquier servidor HTTP:
```bash
# Con Python
cd Frontend/ControllerWebServer
python3 -m http.server 3000

# Con Node
npx serve -s . -l 3000
```

Acceder a `http://localhost:3000` y configurar la IP del robot.

---

## 🔌 Puertos Utilizados

| Puerto | Protocolo | Servicio | Descripción |
|--------|-----------|----------|-------------|
| 6671   | WebSocket | Control Server | Comandos de control |
| 6672   | WebSocket | Logger | Logs en tiempo real |
| 6673   | UDP       | Logger | Logs UDP |
| 8080   | HTTP      | Video Stream | MJPEG streaming |
| 9559   | NAOqi     | NAOqi Framework | API interna |

---

## 🐛 Solución de Problemas

### "Address already in use"
```bash
# Matar procesos existentes
pkill -f "python2.*server.py"
pkill -f "python2.*launcher.py"
pkill -f "python2.*logger.py"
```

### Robot no se mueve con walk
1. Verificar que el robot está en postura correcta:
   ```json
   {"action": "posture", "value": "StandInit"}
   ```
2. Verificar que Autonomous Life está desactivado:
   ```json
   {"action": "autonomous", "value": false}
   ```

### Behaviors no funcionan

**Error: "Behavior is not installed"**

1. Verificar que el behavior está instalado (NO basta con copiar archivos):
   ```bash
   ssh nao@<NAO_IP>
   python2 -c "from naoqi import ALProxy; b=ALProxy('ALBehaviorManager','127.0.0.1',9559); print(b.getInstalledBehaviors())"
   ```

2. Si no aparece, debes **instalarlo desde Choregraphe** (ver Paso 5)

3. Si aparece pero con diferente nombre/hash, actualiza `behavior_commands.py`:
   ```bash
   # Ver nombres exactos instalados
   ls /home/nao/.local/share/PackageManager/apps/
   ```

4. Listar behaviors desde WebSocket para debug:
   ```json
   {"action": "listBehaviors"}
   ```

### Ver logs del sistema
```bash
# Log principal
tail -f /tmp/nao_system.log

# Log específico del launcher
tail -f /tmp/nao_launcher.log
```

### WebSocket no conecta
1. Verificar que el servicio está corriendo:
   ```bash
   ps aux | grep python2
   ```
2. Verificar firewall y red
3. Probar conexión:
   ```bash
   # Desde PC
   curl -v telnet://<NAO_IP>:6671
   ```

---

## 🔒 Seguridad y Buenas Prácticas

- **Zona despejada** (≥1.5 × 1.5 m) sin obstáculos
- **Superficie antideslizante** (no usar en superficies pulidas)
- **Batería** ≥30% para evitar fallos de tensión
- **Watchdog interno**: detiene marcha automáticamente si no hay comandos en 0.6s
- **Fall Manager**: activar para protección ante caídas (a menos que interfiera con behaviors)
- **No ejecutar** simultáneamente otros clientes que usen ALMotion

---

## 📊 Arquitectura del Sistema

```
┌─────────────────────┐     WebSocket      ┌───────────────────────────────┐
│   Frontend React    │◄──────────────────►│     Control Server v2.0       │
│  (Navegador/Móvil)  │     :6671          │                               │
└─────────────────────┘                    │  ┌─────────────────────────┐  │
                                           │  │    Command Factory      │  │
┌─────────────────────┐     WebSocket      │  │  (Patrón Command)       │  │
│   Logger Client     │◄──────────────────►│  └───────────┬─────────────┘  │
│   (Postman/etc)     │     :6672          │              │                │
└─────────────────────┘                    │  ┌───────────▼─────────────┐  │
                                           │  │      NAO Facade         │  │
┌─────────────────────┐     HTTP/MJPEG     │  │  (Abstracción NAOqi)    │  │
│   Video Viewer      │◄──────────────────►│  └───────────┬─────────────┘  │
│                     │     :8080          │              │                │
└─────────────────────┘                    │  ┌───────────▼─────────────┐  │
                                           │  │   Movement Strategies   │  │
                                           │  │ (Manual/Adaptive/etc)   │  │
                                           │  └───────────┬─────────────┘  │
                                           └──────────────┼────────────────┘
                                                          │
                                                          ▼ NAOqi API :9559
                                           ┌──────────────────────────────┐
                                           │         NAO Robot            │
                                           │   ALMotion, ALPosture, etc   │
                                           └──────────────────────────────┘
```

---

## 📜 Changelog

### v2.0 (2025)
- ✅ Arquitectura modular con Command Pattern
- ✅ Facade para abstracción de NAOqi
- ✅ Strategies para modos de movimiento
- ✅ Soporte completo de behaviors
- ✅ Sistema de logging centralizado
- ✅ Launcher con control por sensor táctil

### v1.x (2024)
- Sistema monolítico inicial
- Control básico de movimiento
- Prototipo de interfaz web

---

## ⚖️ Licencia

MIT License - Universidad de La Sabana

---

## 👥 Créditos

- **Semillero de Robótica Aplicada** - Universidad de La Sabana
- **Desarrollador principal**: Luis Mario Ramírez Muñoz

---

¡Disfruta controlando a NAO! 🤖🚀
