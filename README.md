Documentación actualizada
1 · Arquitectura general
less
Copiar
Editar
[ Navegador ]   index.html + styles.css + logic.js
      │   WebSocket ws://<IP_NAO>:6671
      ▼
[ control_server.py ]  NAOqi dispatcher (Python 2.7)
      │   JSON actions: walk/move/led/say/posture/getInfo
      ▼
[    NAO real   ]  ALMotion, ALLeds, ALTextToSpeech, ALMemory
Flujo de datos
#	Emisor	Receptor	Formato	Descripción
①	logic.js (web)	control_server.py	JSON via WS	{action:'walk',vx,vy,wz} (15 Hz)
②	logic.js (web)	control_server.py	JSON via WS	{action:'move',joint,value}
③	logic.js (web)	control_server.py	JSON via WS	{action:'led',groups,r,g,b}
④	logic.js (web)	control_server.py	JSON via WS	{action:'say',text}
⑤	logic.js (web)	control_server.py	JSON via WS	{action:'posture',value:'Sit}
⑥	logic.js (web)	control_server.py	JSON via WS	{action:'getInfo'} → stats
⑦	control_server.py	NAOqi	API interna	moveToward, setAngles, fadeRGB, etc.

2 · Archivos y responsabilidades
Archivo	Lenguaje	Rol	Por qué es necesario
index.html	HTML	Estructura de la UI (modos, joystick, menús)	Punto de entrada: se sirve desde python -m http.server.
styles.css	CSS	Layout responsive, estética NES, animaciones táctiles	Usabilidad y aspecto en móvil/PC
logic.js	JavaScript	Lógica de UI: WebSocket, joystick, botones, menús, envío	Control completo desde el navegador
control_server.py	Python 2.7	Recibe WS, despacha a NAOqi (walk, move, led, say, posture, getInfo)	Conecta navegador ↔ NAOqi

3 · Instalación en el NAO real (Python 2.7)
Copiar carpeta

bash
Copiar
Editar
scp -r remote_control/ nao@<IP_NAO>:/home/nao/remote_control
Servir la web

bash
Copiar
Editar
ssh nao@<IP_NAO>
cd ~/remote_control
python2 -m SimpleHTTPServer 8000 &   # o python -m http.server 8000 si tiene py3
Dependencias Python 2.7

bash
Copiar
Editar
pip2 install SimpleWebSocketServer pillow
Arrancar servidor de control

bash
Copiar
Editar
cd ~/remote_control
python2 control_server.py &
python2 video_stream_py2.py &   # stream MJPEG cámara top
Conectar desde móvil/PC
Abrir http://<IP_NAO>:8000 → UI aparece → controla el robot.

4 · Seguridad y buenas prácticas
Zona libre – mínimo 1 × 1 m despejado.

Watch-dog – control_server.py detiene marcha si no recibe walk en 0.6 s.

Stiffness OFF – para manipular articulaciones: motion.setStiffnesses("Body",0).

No mezclar clientes – evita que Choregraphe o scripts externos interfieran.

Menús restringidos – limita acceso a tu LAN confiable (firewall).

5 · Explicación detallada de scripts
5.1 logic.js
WebSocket con reconexión automática.

handleWS procesa msg.info y actualiza IP, batería y tabla de joints.

Modos: cambia mode y aplica clase .active.

Stand/Sit: manda {action:'posture',value}.

Menús: abre/ cierra, y para cámara inyecta src MJPEG.

Voz: envía {action:'say',text}.

LEDs: lee checkboxes .led-checkbox, envía {action:'led',groups,r,g,b} o apagado.

Joystick: calcula vx,vy, limita a círculo, envía cada 1/15 s según mode.

Polling de estado cada 1 s: {action:'getInfo'}.

5.2 control_server.py
SimpleWebSocketServer escucha en :6671.

RobotWS.handleMessage: parsea JSON y despacha a:

walk → motion.moveToward

move → motion.setAngles

led → leds.fadeRGB en cada grupo

say → tts.say

posture → posture.goToPosture

getInfo → lee batería, joints + temperaturas → devuelve JSON

Watchdog en hilo paralelo para stopMove si no hay walk en 0.6 s.

6 · Prueba rápida (check-list)
NAO encendido y en tu LAN.

Copia remote_control/ y lanza HTTP server.

Instala deps y lanza control_server.py & video_stream_py2.py.

Desde móvil: abre http://<IP_NAO>:8000.

Cambia modo, usa joystick para caminar, brazos, cabeza.

Envía voz, enciende/apaga LEDs por grupo.

Abre menú cámara → stream vivo.

Cierra página → tras 0.6 s la marcha se detiene.

© 2025 Control NAO – Universidad de La Sabana