# Prueba física NAO + Nemotron

## Distribución

- El NAO ejecuta NAOqi, control web, cámara, captura de audio, bumpers y el límite local de acciones.
- El PC ejecuta el orquestador Python 3 y llama a NVIDIA por HTTPS.
- `.env` y `NVIDIA_API_KEY` permanecen exclusivamente en el PC.
- PC y NAO autentican los mensajes con HMAC mediante `NAO_GATEWAY_SECRET`.

La instalación del robot vive en `/home/nao/naoControl`. Sus logs están en
`/home/nao/logs/naoControl` y sus PID en `/home/nao/run/naoControl`.

## Despliegue desde Windows

Desde la raíz del repositorio, una sola orden empaqueta el runtime del robot,
la configuración no secreta y la web compilada; los copia al NAO, conserva
`robot_gateway.secret` existente y valida los módulos Python críticos:

```powershell
.\tools\deploy-nao.ps1 -NaoIp <IP_ACTUAL_DEL_NAO>
```

Para que el mismo comando arranque control web, cámara y gateway al terminar:

```powershell
.\tools\deploy-nao.ps1 -NaoIp <IP_ACTUAL_DEL_NAO> -StartServices
```

El script nunca transfiere `.env`, `.git`, `.venv` ni la clave NVIDIA y tampoco
modifica `autoload.ini`. Sin `-StartServices`, el launcher táctil sigue siendo
el responsable de iniciar los servicios con la presión larga central.

## Operación

1. Al reiniciar, `autoload.ini` ejecuta el launcher residente. Con el sistema
   detenido, mantener el sensor táctil central de la cabeza durante 3 segundos
   inicia web control, cámara y gateway Nemotron juntos. Otra pulsación larga
   los detiene para dejar el robot preparado para Choregraphe.
2. La interfaz web queda disponible en `http://<ip-del-nao>:3000` y se conecta
   al WebSocket de control del mismo robot en el puerto `6671`.
3. Preparar una sola vez el PC con
   `tools\setup-nemotron-pc-host.ps1 -NaoIp <IP_ACTUAL_DEL_NAO>`. Desde ese PC,
   abrir el control web y guardar el proveedor para que el NAO infiera su IPv4.
4. Mantener presionado el bumper izquierdo 1.5 s. El NAO solicita al lanzador
   autenticado del PC descargar el gateway desde el robot y ejecutarlo; solo
   entonces entra al modo inteligente. Otra pulsación larga sale del modo.
5. Ya en modo inteligente, mantener el bumper derecho mientras se habla y soltarlo al terminar.
6. Presionar ambos bumpers para solicitar parada de emergencia.

Durante la prueba, abre el menú **Nemotron** de la interfaz. Mientras el bumper
está presionado debe indicar **Escuchando**; después de soltarlo pasa a
**Procesando audio e imagen** y finalmente muestra la transcripción, el texto
de respuesta y el resultado de cada acción. La transcripción es por lotes, no
palabra por palabra.

Para seguir los logs locales del gateway Nemotron (bumpers, captura y diagnóstico
WAV) por SSH en tiempo real:

```sh
ssh -t nao@<IP_ACTUAL_DEL_NAO> "tail -F /home/nao/logs/naoControl/intelligence.log"
```

En el PC, el componente que llama a NVIDIA se inicia automáticamente. Sus logs
muestran el transcript, contexto visual, decisión y resultado de cada acción:

```powershell
Get-Content "$env:LOCALAPPDATA\naoControlGatewayHost\logs\gateway.log" -Wait
```

El PC imprime `TRANSCRIPTION` y el resultado de Nemotron. El robot imprime
`audio_diagnostics` con tamaño, frecuencia, canales y RMS, sin conservar ni
mostrar la grabación. Un RMS muy bajo o cero confirma que el problema está antes
de NVIDIA (micrófono/canal); una transcripción distinta de la voz confirma que
la captura llega a NVIDIA pero debe revisarse el canal o el entorno acústico.

La petición multimodal usa `audio_url` con un WAV en base64 y desactiva el modo
de razonamiento para las respuestas JSON breves. Así se reserva la salida para
`transcript`/`scene_summary` y para `{speech, tool_calls}`, en lugar de agotarla
en la traza de razonamiento.

Las acciones se solicitan mediante el tool calling nativo de Nemotron. Por
ejemplo, una orden de sentarse debe producir `set_posture` con `posture: Sit`;
la respuesta hablada nunca se toma como autorización para mover el robot.

Cada resultado de acción registra ahora el nombre, los argumentos no sensibles,
el estado y la razón de rechazo. Para una orden de postura debe verse en el PC
una línea como `action=set_posture arguments={'posture': 'Stand', 'speed': 0.35}
status=accepted reason=None`. `accepted` significa que NAOqi inició la tarea
asíncrona sin bloquear el canal de control; el movimiento o la locución pueden
seguir ejecutándose después de recibir ese resultado. Si aparece
`status=rejected`, la misma razón se
imprime también en `intelligence.log`; usar ese valor antes de cambiar el
registro de acciones o los límites físicos.

Las operaciones largas (`say`, `set_posture` y `run_behavior`) se lanzan con el
sistema de tareas asíncronas de NAOqi. Así, una postura que tarde o no pueda
terminar no impide responder heartbeats. Si el enlace se pierde de todos modos,
el gateway del PC conserva el proceso y vuelve a conectar cada dos segundos.
Las acciones corporales solo se autorizan cuando la transcripción contiene una
petición explícita compatible; una conversación normal no permite que el modelo
añada movimientos espontáneos. Las variantes naturales `te levantes`,
`levantarte`, `sentarte` y `agacharte` se comparan con la postura concreta que
el modelo solicita, por lo que una petición de levantarse no autoriza sentarse.
Las negaciones directas, por ejemplo `no quiero que te levantes`, se rechazan
antes de buscar la variante afirmativa para que el verbo contenido en una
negación nunca habilite movimiento.

Para `run_behavior`, la intención también debe corresponder al ID solicitado:
`saluda`/`wave`, `asiente`/`yes`, `niega`/`no`, `piensa`/`thinking`, las danzas
con `baila` o el nombre de la danza, `toca saxofón`/`play_saxophone` y `tai chi`
o `taichi`. La palabra genérica `baila` solo autoriza IDs `dance_*`; nunca
autoriza saxofón, taichí o un saludo.

Al iniciar el runtime, `ALTextToSpeech` selecciona el idioma `Spanish`. Si esa
voz no está instalada en el robot, `intelligence.log` registra la advertencia y
la instalación debe completarse desde las preferencias de voz de NAO/Choregraphe.

Ante una saturación temporal de NVIDIA (`ReadTimeout`, 502, 503 o 504), el PC
reintenta hasta tres veces con esperas de 1 y 2 segundos. El log identifica la
etapa afectada como `PERCEPTION_FAILED` (audio/imagen) o `DECISION_FAILED`
(respuesta estructurada), para no confundir una indisponibilidad de nube con una
captura de micrófono fallida.

La cámara usa un servidor MJPEG concurrente: un navegador o un lector que cierre
su flujo no bloquea la instantánea solicitada por el agente. Si la cámara no
responde dentro de su límite, el turno continúa en modo audio, registra
`VISION_UNAVAILABLE` y no inventa contexto visual.

Indicadores: azul significa modo inteligente listo, verde grabación, naranja
procesamiento, blanco control web y rojo parada de emergencia.

## Límites de esta prueba

El modelo solo recibe herramientas habilitadas en `config/action_registry.json`.
No se permiten comandos libres ni locomoción. Las acciones se validan en el PC y
otra vez en el NAO. La pérdida del PC o de NVIDIA no autoriza ninguna acción.

Los comportamientos permitidos se prueban con el ID exacto: `wave`, `yes`, `no`,
`thinking`, `dance_siu`, `dance_gangnam`, `dance_macarena`, `play_saxophone` y
`taichi`. Los paquetes deben instalarse con Choregraphe y conservar el ID de
paquete configurado en `config/behavior_registry.json`. Si aparece
`unknown_behavior` o `facade_failed`, instalar el paquete faltante desde
Choregraphe y repetir la prueba.

## Matriz de verificación física

| Acción | Orden explícita | Resultado esperado |
|---|---|---|
| FaceLeds rojo | `set_led(group=FaceLeds, color=red)` | Rojo mediante `fadeRGB` |
| ChestLeds verde | `set_led(group=ChestLeds, color=green)` | Verde mediante `fadeRGB` |
| EarLeds azul | `set_led(group=EarLeds, color=blue)` | Azul mediante intensidad `1.0` |
| EarLeds apagado | `set_led(group=EarLeds, color=off)` | Apagado mediante intensidad `0.0` |
| Postura | `set_posture(posture=Stand, speed=0.35)` | NAO inicia la transición |
| Behaviors | Una orden para cada ID permitido | Se ejecuta el behavior registrado |

Los colores distintos de `blue` y `off` en `EarLeds` deben rechazarse con
`invalid_ear_led_color`; no deben afirmarse como ejecutados.

## Límites de confianza y activos

Los límites son NVIDIA/Internet, PC/NAO por Ethernet y gateway/NAOqi dentro del
robot. Los activos protegidos son la clave NVIDIA, el secreto HMAC, audio e
imágenes, y la seguridad física. Controles: TLS a NVIDIA, secreto fuera de Git,
mensajes firmados con caducidad y protección de replay, registro explícito de
acciones, rangos de articulaciones, presupuesto por turno y parada local.

Para la demo debe haber un operador junto al robot, espacio despejado y acceso
inmediato a ambos bumpers. El WebSocket de control web heredado no debe exponerse
a redes distintas del enlace Ethernet directo durante esta prueba. El panel
Nemotron solo entrega la conversación al origen que coincide con la IP del PC
confirmada mediante el sensor táctil trasero.
