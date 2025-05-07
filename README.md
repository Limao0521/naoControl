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
└─ walk_ws_server.py        # Servidor WS → NAOqi (Python 2.7)
```

---

## 🔧 Requisitos

* **Robot NAO** con NAOqi 2.8 instalado.
* **Python 2.7** en NAO (incluye `pip2`).
* Navegador moderno con soporte WebSocket (Chrome, Firefox, Edge, Safari).

---

## 📥 Instalación

1. **Clona o descarga** este repositorio en tu máquina local.
2. **Copia** la carpeta al NAO:

   ```bash
   scp -r remote_control/ nao@<IP_NAO>:/home/nao/remote_control
   ```
3. **Dependencias Python** (en NAO):

   ```bash
   ssh nao@<IP_NAO>
   pip2 install websocket-server --user
   ```

   > *Nota: `SimpleWebSocketServer.py` ya está incluido, esta línea es opcional si prefieres instalar otra implementación WS.*

---

## ⚙️ Despliegue

1. **Servir la interfaz web** desde NAO:

   ```bash
   cd ~/remote_control
   python2 -m SimpleHTTPServer 8000 &
   ```
2. **Iniciar servidor WebSocket**:

   ```bash
   cd ~/remote_control
   python2 walk_ws_server.py &
   ```
3. **Abrir navegador** y visitar:

   ```
   http://<IP_NAO>:8000/
   ```

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

### walk\_ws\_server.py

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

## ⚖️ Licencia & Créditos

* **Proyecto Open Source** para investigación y educación.
* Inspirado en control remoto de NAO de Universidad de La Sabana.

---

¡Disfruta pilotar a tu NAO! 🤖🚀
