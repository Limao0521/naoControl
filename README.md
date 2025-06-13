
Pensado durante un par de segundos

# Control-NAO Remote Control Suite

> Tele-operación completa de NAO a través de navegador web y WebSocket
> Compatible con Python 2.7 + NAOqi 2.8

---

## 📖 Descripción

Control-NAO es un sistema de control remoto para robots NAO desde cualquier navegador (móvil o PC), sin dependencias adicionales más allá de Python 2.7 y NAOqi. Permite:

* **Tele-operar** la locomoción (caminata) con joystick virtual.
* **Mover** brazos (izquierdo/derecho) y cabeza con el mismo joystick.
* **Posturas** básicas: Stand / Sit.
* **Control de LEDs** por grupos (pecho, cara, ojos) y color vía selector.
* **Síntesis de voz** (“say”).
* **Watchdog** de parada de emergencia si no llegan comandos de walk.
* **Reconexión automática** WebSocket en caso de desconexión.

---

## 🚀 Características Principales

* **Interfaz web** responsive y ligera (HTML5 + CSS3 + JavaScript puro).
* **WebSocket server** en Python 2.7: despacha mensajes a NAOqi.
* **Joystick táctil** con cálculos en \[-1,1], corrección de orientación.
* **Control granular de LEDs**: seleccionar uno o varios grupos, ajustar color.
* **Voice** y **MJPEG camera feed** integrados (cámara sin servidor extra).
* **Logs detallados** en consola NAO y navegador.
* **Watchdog** que detiene la marcha automáticamente si no hay comandos de walk en 0.6 s.
* **AutonomousLife** desactivado, stiffness en Body al iniciar.

---

## 🏗️ Estructura del Proyecto

```
remote_control/
├─ index.html               # UI principal
├─ styles.css               # Estilos y layout responsive
├─ logic.js                 # Lógica de cliente (WebSocket, joystick, menús)
├─ SimpleWebSocketServer.py # Biblioteca WS pura Python
└─ control_server.py        # Servidor WS → NAOqi (Python 2.7)
```

---

## 🔧 Requisitos

* **Robot NAO** con NAOqi 2.8 instalado.
* **Python 2.7** en NAO (incluye `pip2`).
* Navegador moderno con soporte WebSocket (Chrome, Firefox, Edge, Safari).

---

## 📑 Uso

* **Modos de control**: elije “Caminata”, “Brazo Izq.”, “Brazo Der.” o “Cabeza”.
* **Joystick**: arrastra para generar vectores `vx`, `vy`; se ha corregido la orientación de ejes.
* **Stand / Sit**: botones para cambiar postura.
* **LEDs**: abre menú 💡, selecciona grupo, color y “Encender” / “Apagar”.
* **Voz**: abre menú 🎤, escribe texto y pulsa “Hablar”.
* **Cámara**: menú 📷 muestra stream MJPEG nativo (no requiere script extra).

> **Reconnect** automático si pierdes conexión WS: la UI reintenta en 3 s.

---

## 🛠️ Estructura y Puntos Clave de los Scripts

### control_server.py

* **Imports y configuración** de NAOqi (`ALMotion`, `ALLeds`, `ALTextToSpeech`, `ALAutonomousLife`).
* **Clase `RobotWS`** extiende `WebSocket`:

  * `handleMessage` parsea JSON y despacha a NAOqi.
* **Watchdog thread**: llama `motion.stopMove()` cada 0.6 s sin comandos `walk`.
* **Puerto WebSocket** con reintentos y `SO_REUSEADDR` para evitar “Address in use”.

### logic.js

* **Conexión WS** dinámica con reconexión en 3 s.
* **Joystick**: cálculo de radio, knob, normalización, corrección de ejes para que “adelante” sea arrastrar knob hacia arriba.
* **sendCmd()**: despacho de JSON con `{action, vx, vy, ...}` según modo.
* **Menús**: toggle de clases `.active`.
* **LEDs**: selector de grupo + color HEX → valores `[0–1]`.
* **Voz** y **Cámara MJPEG** integrados.

---

## 🔎 Solución de Problemas

* **“Address already in use”**: asegúrate de que no haya instancias previas; el script reintenta por ti.
* **WS desconectado constantemente**: verifica IP de NAO y habilita puertos en tu red.
* **Joystick girado**: corregido intercambiando `vx` y `vy` en `sendCmd()`.
* **getInfo / Stats**: deshabilitado temporalmente en UI. Puedes reactivar `handleWS` y mostrar `<div id="stats">…`.

---

## 1 · Arquitectura general

```
[ Navegador ]  index.html + styles.css + logic.js
        │  WebSocket ws://<NAO_IP>:6671
        ▼
[ control_server.py ]  WebSocket → ALMotion.moveToward
        │  (Python 2.7 + NAOqi 2.8, puerto 9559)
        ▼
[   NAO real   ]  motores y desplazamiento
```

### Flujo de datos

| Nº | Emisor (WS)            | Receptor            | Formato         | Descripción                               |
| -- | ---------------------- | ------------------- | --------------- | ----------------------------------------- |
| ①  | `logic.js` (browser)   | `control_server.py` | WebSocket texto | “walk vx vy wz” \~15 Hz                   |
| ②  | `control_server.py`    | `ALMotion`          | API NAOqi       | `moveToward(vx, vy, wz)`                  |
| ③  | `watchdog_loop` (hilo) | `ALMotion`          | API NAOqi       | `stopMove()` tras WATCHDOG s sin comandos |

---

## 2 · Archivos y responsabilidades

| Archivo                      | Lenguaje   | Rol                                                         |
| ---------------------------- | ---------- | ----------------------------------------------------------- |
| **index.html**               | HTML       | Estructura del mando (cruceta NES + joystick táctil)        |
| **styles.css**               | CSS        | Responsividad y animaciones de botones/joystick             |
| **logic.js**                 | JavaScript | Captura toques/teclas, normaliza e invoca WS dinámico       |
| **SimpleWebSocketServer.py** | Python 2   | Implementación pura Python del protocolo WebSocket          |
| **control_server.py**        | Python 2.7 | Servidor WS + watchdog → `ALMotion.moveToward`/`stopMove()` |

*Coloca `SimpleWebSocketServer.py` y `walk_ws_server.py` en la misma carpeta `/home/nao/remote_control`.*

---

## 3 · Instalación en NAO real (manteniendo Python 2.7)

1. **Copiar ficheros**

   ```bash
   # en tu PC:
   scp -r remote_control/ nao@<IP_NAO>:/home/nao/remote_control
   ```
2. **Crear carpeta de dependencias** (si no están presentes)

   ```bash
   ssh nao@<IP_NAO>
   mkdir /home/nao/libs/SimpleWebSocketServer-0.1.2
   ```
3. **Instalar dependencias Py2** (si no están presentes)

   ```bash
   ssh nao@<IP_NAO>
   pip2 install --user /home/nao/libs/SimpleWebSocketServer-0.1.2
   ```
4. **Servir la web**

   ```bash
   cd ~/remote_control
   python2 -m SimpleHTTPServer 8000 &   # HTTP en 8000
   ```
5. **Lanzar servidor WebSocket**

   ```bash
   cd ~/remote_control
   python2 walk_ws_server.py &
   ```
6. **Conectar y probar**

   * Desde el móvil/PC: `http://<IP_NAO>:8000`.
   * Abrir consola SSH en el NAO para ver logs de conexiones, peticiones y watchdog.

---

## 4 · Seguridad y buenas prácticas

* **Zona despejada** (≥1 × 1 m) sin obstáculos.
* **Superficie antideslizante**.
* **Batería** ≥30 % para evitar fallos de tensión.
* **Watchdog interno**: frena en 0.6 s sin datos.
* **Stiffness** ON solo al tele-operar; OFF para manipular a mano.
* **AutonomousLife** desactivado por `walk_ws_server.py`.
* **No ejecutar** simultáneamente otros clientes que usen ALMotion.

---

## 5 · Explicación detallada de `walk_ws_server.py`

1. **Imports y path**: añade la carpeta local para importar `SimpleWebSocketServer.py`.
2. **Configurables**: IP, puertos y WATCHDOG al inicio.
3. **Inicialización NAOqi**:

   * `ALMotion`, `ALAutonomousLife`, `ALRobotPosture`.
   * Apaga gestos automáticos y fija postura de pie.
4. **Clase WalkWS**:

   * `handleConnected`/`handleClose`: logs de conexión.
   * `handleMessage`: parseo de “walk vx vy wz”, validación, normalización, llamada a `moveToward`, log de envío.
5. **Watchdog**:

   * Hilo demonio via `threading.Thread` + `setDaemon(True)`.
   * Cada 50 ms comprueba si `time()-last_cmd > WATCHDOG` → `stopMove()`.
6. **Arranque de servidor**:

   * `SimpleWebSocketServer("", WS_PORT, WalkWS).serveforever()`.
   * `KeyboardInterrupt` → frena motores y sale.

---
## ⚖️ Licencia & Créditos

* **Proyecto Open Source** para investigación y educación.
* Desarrollado por Semillero de Robotica Aplicada de Universidad de La Sabana.
* Desarrollador principal: Luis Mario Ramirez Muñoz, estudiante de Ingenieria Informatica.
---

¡Disfruta pilotar a tu NAO! 🤖🚀
=======
# Control‑NAO — Documentación definitiva (junio 2025)

## Changelog de mejoras

* **V1**: Prototipo inicial con puente UDP (`ws2udp.py`) y servidor UDP (`walk_server.py`).
* **V2**: Eliminación de puente. Introducción de servidor WebSocket directo en Python 2.7 (`walk_ws_server.py`).
* **V3**: Añadidos *prints* para trazabilidad: conexiones, peticiones, normalizaciones y watchdog.
* **V4**: Correcciones de compatibilidad Py2.7: eliminación de f‑strings, uso de `.format()`, hilos demonio con `setDaemon()`.
* **V5**: Mejoras de interfaz y manejo del robot.
---
© 2025 Control‑NAO Project — Universidad de La Sabana
