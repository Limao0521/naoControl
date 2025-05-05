# Control‑NAO — Documentación definitiva (mayo 2025)

## Changelog de mejoras

* **V1**: Prototipo inicial con puente UDP (`ws2udp.py`) y servidor UDP (`walk_server.py`).
* **V2**: Eliminación de puente. Introducción de servidor WebSocket directo en Python 2.7 (`walk_ws_server.py`).
* **V3**: Añadidos *prints* para trazabilidad: conexiones, peticiones, normalizaciones y watchdog.
* **V4**: Correcciones de compatibilidad Py2.7: eliminación de f‑strings, uso de `.format()`, hilos demonio con `setDaemon()`.

---

## 1 · Arquitectura general

```
[ Navegador ]  index.html + styles.css + logic.js
        │  WebSocket ws://<NAO_IP>:6671
        ▼
[ walk_ws_server.py ]  WebSocket → ALMotion.moveToward
        │  (Python 2.7 + NAOqi 2.8, puerto 9559)
        ▼
[   NAO real   ]  motores y desplazamiento
```

### Flujo de datos

| Nº | Emisor (WS)            | Receptor            | Formato         | Descripción                               |
| -- | ---------------------- | ------------------- | --------------- | ----------------------------------------- |
| ①  | `logic.js` (browser)   | `walk_ws_server.py` | WebSocket texto | “walk vx vy wz” \~15 Hz                   |
| ②  | `walk_ws_server.py`    | `ALMotion`          | API NAOqi       | `moveToward(vx, vy, wz)`                  |
| ③  | `watchdog_loop` (hilo) | `ALMotion`          | API NAOqi       | `stopMove()` tras WATCHDOG s sin comandos |

---

## 2 · Archivos y responsabilidades

| Archivo                      | Lenguaje   | Rol                                                         |
| ---------------------------- | ---------- | ----------------------------------------------------------- |
| **index.html**               | HTML       | Estructura del mando (cruceta NES + joystick táctil)        |
| **styles.css**               | CSS        | Responsividad y animaciones de botones/joystick             |
| **logic.js**                 | JavaScript | Captura toques/teclas, normaliza e invoca WS dinámico       |
| **SimpleWebSocketServer.py** | Python 2   | Implementación pura Python del protocolo WebSocket          |
| **walk\_ws\_server.py**      | Python 2.7 | Servidor WS + watchdog → `ALMotion.moveToward`/`stopMove()` |

*Coloca `SimpleWebSocketServer.py` y `walk_ws_server.py` en la misma carpeta `/home/nao/remote_control`.*

---

## 3 · Instalación en NAO real (manteniendo Python 2.7)

1. **Copiar ficheros**

   ```bash
   # en tu PC:
   scp -r remote_control/ nao@<IP_NAO>:/home/nao/remote_control
   ```
2. **Instalar dependencias Py2** (si no están presentes)

   ```bash
   ssh nao@<IP_NAO>
   pip2 install argparse websocket-client --user
   ```
3. **Servir la web**

   ```bash
   cd ~/remote_control
   python2 -m SimpleHTTPServer 8000 &   # HTTP en 8000
   ```
4. **Lanzar servidor WebSocket**

   ```bash
   cd ~/remote_control
   python2 walk_ws_server.py &
   ```
5. **Conectar y probar**

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

© 2025 Control‑NAO Project — Universidad de La Sabana
