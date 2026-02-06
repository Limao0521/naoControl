# NAO Robot - Guía de Despliegue

Esta carpeta contiene todo lo necesario para ejecutar el sistema de control en el robot NAO.

---

## 📁 Contenido de esta Carpeta

```
nao/
├── assets/Behaivors/      # Behaviors para instalar en Choregraphe
├── data/                  # Datos (análisis, grabaciones, walks)
├── deploy/                # Scripts de despliegue automático
├── models/                # Modelos ML (LightGBM)
└── scripts/               # Código Python para el robot
    ├── runtime/           # Sistema principal
    │   ├── launcher.py    # Punto de entrada
    │   ├── logger.py      # Logging WebSocket/UDP
    │   ├── video_stream.py# Streaming MJPEG
    │   └── control_server/# Backend modular
    ├── diagnostics/       # Herramientas de diagnóstico
    └── ml/                # Scripts ML
```

---

## 🚀 Instalación Rápida (Manual)

### 1. Conectar al Robot
```bash
ssh nao@<NAO_IP>
# Password: nao
```

### 2. Crear Directorios
```bash
mkdir -p /home/nao/scripts/runtime/control_server/commands
mkdir -p /home/nao/scripts/runtime/control_server/facades
mkdir -p /home/nao/scripts/runtime/control_server/strategies
mkdir -p /home/nao/models
```

### 3. Instalar SimpleWebSocketServer
```bash
cd /home/nao
wget https://github.com/dpallot/simple-websocket-server/archive/refs/heads/master.zip
unzip master.zip
mv simple-websocket-server-master SimpleWebSocketServer-0.1.2
rm master.zip
```

### 4. Copiar Archivos (desde PC)
```bash
scp -r nao/scripts/runtime/* nao@<NAO_IP>:/home/nao/scripts/runtime/
scp -r nao/models/* nao@<NAO_IP>:/home/nao/models/
scp nao/scripts/nao_config.py nao@<NAO_IP>:/home/nao/scripts/
```

### 5. Instalar Behaviors
Usar Choregraphe para instalar cada behavior de `assets/Behaivors/`

### 6. Ejecutar
```bash
cd /home/nao/scripts/runtime
python2 launcher.py
```

---

## 📋 Archivos del Runtime

| Archivo | Descripción |
|---------|-------------|
| `launcher.py` | Punto de entrada principal. Gestiona servicios y sensor táctil |
| `logger.py` | Servidor de logging (WS:6672, UDP:6673) |
| `video_stream.py` | Streaming de cámara (HTTP:8080) |
| `data_logger.py` | Logger de datos para entrenamiento ML |
| `control_server/server.py` | Servidor WebSocket de control (WS:6671) |
| `control_server/command_factory.py` | Factory de comandos |
| `control_server/base_command.py` | Clase base para comandos |
| `control_server/commands/*.py` | Implementaciones de comandos |
| `control_server/facades/nao_facade.py` | Abstracción de NAOqi |
| `control_server/strategies/movement_strategies.py` | Estrategias de movimiento |

---

## 🎮 Uso del Launcher

El launcher (`launcher.py`) es el punto de entrada recomendado:

1. **Inicia automáticamente** todos los servicios (logger, control, video)
2. **Escucha sensor táctil** de la cabeza para alternar modos:
   - **Presión larga (3+ seg)** en sensor medio → Alterna modo
   - **Modo Control**: Servicios activos, listo para WebSocket
   - **Modo Choregraphe**: Servicios detenidos, listo para Choregraphe

### Ejecución Normal
```bash
python2 /home/nao/scripts/runtime/launcher.py
```

### Ejecución en Background
```bash
nohup python2 /home/nao/scripts/runtime/launcher.py > /tmp/nao.log 2>&1 &
```

### Auto-inicio
```bash
# Añadir a crontab
crontab -e
@reboot sleep 30 && python2 /home/nao/scripts/runtime/launcher.py > /tmp/nao.log 2>&1
```

---

## 🔌 Puertos

| Puerto | Servicio |
|--------|----------|
| 6671 | Control Server (WebSocket) |
| 6672 | Logger (WebSocket) |
| 6673 | Logger (UDP) |
| 8080 | Video Stream (HTTP MJPEG) |

---

## 🛠️ Solución de Problemas

### Procesos duplicados
```bash
pkill -f "python2.*launcher.py"
pkill -f "python2.*server.py"
pkill -f "python2.*logger.py"
```

### Ver logs
```bash
tail -f /tmp/nao_system.log
```

### Verificar procesos
```bash
ps aux | grep python2
```

---

## 📄 Requisitos del Robot

- NAO V6 con NAOqi 2.8
- Python 2.7 (preinstalado)
- SimpleWebSocketServer (ver instalación arriba)

---

© 2025 Universidad de La Sabana - Semillero de Robótica
