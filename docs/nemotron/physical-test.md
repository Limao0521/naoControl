# Prueba física NAO + Nemotron

## Distribución

- El NAO ejecuta NAOqi, control web, cámara, captura de audio, bumpers y el límite local de acciones.
- El PC ejecuta el orquestador Python 3 y llama a NVIDIA por HTTPS.
- `.env` y `NVIDIA_API_KEY` permanecen exclusivamente en el PC.
- PC y NAO autentican los mensajes con HMAC mediante `NAO_GATEWAY_SECRET`.

La instalación del robot vive en `/home/nao/naoControl`. Sus logs están en
`/home/nao/logs/naoControl` y sus PID en `/home/nao/run/naoControl`.

## Operación

1. Al reiniciar, `autoload.ini` ejecuta el launcher residente. Con el sistema
   detenido, mantener el sensor táctil central de la cabeza durante 3 segundos
   inicia web control, cámara y gateway Nemotron juntos. Otra pulsación larga
   los detiene para dejar el robot preparado para Choregraphe.
2. La interfaz web queda disponible en `http://<ip-del-nao>:3000` y se conecta
   al WebSocket de control del mismo robot en el puerto `6671`.
3. En el PC, desde la raíz del repositorio, ejecutar
   `.venv\\Scripts\\python.exe -m nao_gateway.main`.
4. Mantener presionado el bumper izquierdo 1.5 s para entrar o salir del modo inteligente.
5. Ya en modo inteligente, mantener el bumper derecho mientras se habla y soltarlo al terminar.
6. Presionar ambos bumpers para solicitar parada de emergencia.

Para arrancar los servicios del robot y ver sus logs por SSH en tiempo real:

```sh
ssh -t nao@169.254.31.157 "sh /home/nao/naoControl/nao/scripts/runtime/start_nemotron.sh && tail -F /home/nao/logs/naoControl/intelligence.log /home/nao/logs/naoControl/camera.log"
```

En una terminal del PC se inicia el componente que llama a NVIDIA y muestra el
transcript, contexto visual, decisión y resultado de cada acción:

```powershell
.\.venv\Scripts\python.exe -u -m nao_gateway.main --env-file .env --registry config\action_registry.json
```

Indicadores: azul significa modo inteligente listo, verde grabación, naranja
procesamiento, blanco control web y rojo parada de emergencia.

## Límites de esta prueba

El modelo solo recibe herramientas habilitadas en `config/action_registry.json`.
No se permiten comandos libres ni locomoción. Las acciones se validan en el PC y
otra vez en el NAO. La pérdida del PC o de NVIDIA no autoriza ninguna acción.

Los comportamientos estándar `wave`, `yes`, `no` y `thinking` están disponibles.
Los paquetes personalizados deben instalarse con Choregraphe y conservar el ID
de paquete configurado en `config/behavior_registry.json`.

## Límites de confianza y activos

Los límites son NVIDIA/Internet, PC/NAO por Ethernet y gateway/NAOqi dentro del
robot. Los activos protegidos son la clave NVIDIA, el secreto HMAC, audio e
imágenes, y la seguridad física. Controles: TLS a NVIDIA, secreto fuera de Git,
mensajes firmados con caducidad y protección de replay, registro explícito de
acciones, rangos de articulaciones, presupuesto por turno y parada local.

Para la demo debe haber un operador junto al robot, espacio despejado y acceso
inmediato a ambos bumpers. El WebSocket de control web heredado no debe exponerse
a redes distintas del enlace Ethernet directo durante esta prueba.
