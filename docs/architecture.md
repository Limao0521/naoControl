# Arquitectura vigente de NAO Control

Esta es la arquitectura activa del repositorio. Las carpetas antiguas de ML,
experimentos y behaviors se mantienen, pero no son requisito para conversar con
el agente ni para el control web básico.

```text
Navegador ──WebSocket :6671──> Control Server ──NAOqi :9559──> motores, voz, LEDs
     │                              │
     └── HTTP :3000 <── React ──────┘

bumpers ─> gateway_server :6674 ─> audio + cámara + estado del turno
       ├─ Nemotron: HTTPS directo desde el NAO a NVIDIA
       └─ Gemma: WebSocket firmado al gateway de PC ─> HTTP /v1 del PC con Gemma
```

## Responsabilidad por componente

| Ruta | Responsabilidad |
| --- | --- |
| `tools/deploy-nao.ps1` | Empaqueta el runtime, lo copia por SCP, preserva secretos y reinicia servicios cuando se solicita. |
| `nao/scripts/runtime/start_nemotron.sh` | Inicia control, web, cámara, publicación del bundle y gateway inteligente. |
| `nao/scripts/runtime/launcher.py` | Autoload y pulsación larga central para iniciar/detener el control; emite una sola notificación final localizada. |
| `nao/scripts/runtime/service_supervisor.py` | Comprueba y controla los PID de los servicios desplegados. |
| `nao/scripts/runtime/control_server/server.py` | WebSocket del control manual en `6671`; compone NAOqi, comandos y gestor de red. No anuncia TTS por sí mismo. |
| `nao/scripts/runtime/control_server/command_factory.py` | Registro central de acciones de la interfaz. |
| `nao/scripts/runtime/control_server/commands/*.py` | Implementan acciones manuales: movimiento, voz, LEDs, posturas, red y consultas. |
| `nao/scripts/runtime/control_server/commands/nemotron_commands.py` | Expone estado de la conversación y guarda de forma validada proveedor, idioma, endpoint Gemma y PC gateway inferido. |
| `nao/scripts/runtime/control_server/facades/nao_facade.py` | Única fachada de NAOqi; inicializa proxies y aplica el idioma persistido del TTS al arrancar. |
| `nao/scripts/runtime/intelligence/gateway_server.py` | Lee bumpers, captura audio, sincroniza cámara, cambia modos, controla LEDs y distribuye cada turno al proveedor. |
| `nao/scripts/runtime/intelligence/mode_manager.py` | Máquina de estados: control web, listo, capturando, procesando y emergencia. |
| `nao/scripts/runtime/intelligence/audio_capture.py` | Grabación WAV limitada y diagnóstico de audio. |
| `nao/scripts/runtime/intelligence/native_nemotron.py` | Cliente cloud que hace percepción/transcripción y decisión Nemotron dentro del NAO. |
| `nao/scripts/runtime/intelligence/action_executor.py` | Traduce tools permitidas a llamadas NAOqi y aplica límites de postura, LEDs y behaviors. |
| `nao/scripts/runtime/intelligence/provider_config.py` | Archivo no secreto de proveedor/idioma/endpoint, actualización atómica y textos de sistema ES/EN. |
| `nao/scripts/runtime/interaction_state.py` | Conserva solo el último turno, su transcripción, respuesta, acciones y latencia con reloj del NAO. |
| `pc_gateway/src/nao_gateway/main.py` | Entrada del gateway Python 3 para Gemma LAN. |
| `pc_gateway/src/nao_gateway/agent_host.py` | Ejecuta percepción/decisión remota, publica el estado y solicita tools al NAO. |
| `pc_gateway/src/nao_gateway/providers.py` | Selecciona y reemplaza clientes Nemotron/Gemma sin exponer credenciales. |
| `pc_gateway/src/nao_gateway/kws.py` | Detector ONNX opcional de la palabra “NAO” en el micrófono del PC; emite solo un evento autenticado, nunca audio. |
| `pc_gateway/models/kws/` | Clasificador y encoder openWakeWord importados localmente; se excluyen de Git y se incluyen en el bundle del gateway. |
| `NaoControlReact/src/components/NemotronMenu.js` | Panel para proveedor, idioma, IP Gemma, transcripción, respuesta, acciones y latencia. |
| `NaoControlReact/src/services/nemotronApi.js` | Cliente WebSocket estricto del panel inteligente. |
| `config/action_registry.json` | Espacio de acciones permitido; el modelo nunca recibe permisos fuera de este registro. |
| `config/behavior_registry.json` | Behaviors instalados y autorizados en el NAO. |

## Datos y secretos

- El NAO conserva selección, idioma y endpoint sin secreto en
  `/home/nao/naoControl/config/intelligence_provider.json`.
- La clave NVIDIA vive solo en el NAO para el modo cloud.
- La clave Gemma permanece solo en el `.env` del PC gateway. No pasa por la
  interfaz ni se copia al robot.
- `interaction_state.json` guarda únicamente el último turno, no audio,
  imágenes ni historial conversacional.

## Latencia mostrada

El panel muestra **Tiempo hasta iniciar la voz**. Se mide con el reloj del
NAO desde que se suelta el bumper y termina la grabación hasta que el comando
de voz es aceptado por NAOqi. Incluye la transmisión y la inferencia del
proveedor (local o nube); no depende de que los relojes del NAO y del PC estén
sincronizados.

## Palabra clave

El modelo KWS se ejecuta únicamente en el PC gateway (Python 3.11). Cuando el
NAO ya está en modo inteligente, una detección de “NAO” inicia la grabación del
NAO; una pulsación del bumper la detiene. La guía de preparación está en
[`keyword-spotting.md`](nemotron/keyword-spotting.md).
