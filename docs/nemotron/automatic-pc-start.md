# Inicio automático del gateway Nemotron en el PC

## Arquitectura operativa

El NAO conserva el código Python 3 del gateway dentro de
`/home/nao/naoControl/pc_gateway`. Al iniciar los servicios crea un bundle sin
`.env`, claves NVIDIA ni secretos y lo publica en el puerto `6677`.

El PC mantiene únicamente un lanzador pequeño en segundo plano. Cuando el
bumper izquierdo solicita entrar al modo inteligente:

1. El NAO comprueba primero las condiciones de seguridad física.
2. Lee la IP guardada desde el menú **Red**.
3. Firma una solicitud de arranque con el mismo secreto HMAC del gateway.
4. El lanzador del PC verifica firma, vigencia y protección contra replay.
5. El PC descarga el bundle directamente del NAO y verifica el SHA-256 firmado.
6. Ejecuta ese código con Python 3 y fuerza `NAO_GATEWAY_URL` hacia el NAO que
   originó la petición.
7. Solo después de recibir `ready`, el robot anuncia «Modo inteligente listo».

Si el PC no está preparado, la IP no está configurada o la descarga falla, el
NAO permanece en modo de control web y lo informa en español.

## Preparar un PC nuevo

El PC necesita Python 3.11 o posterior, acceso a Internet para NVIDIA y una
copia local segura del `.env`. Desde la raíz del repositorio, abre PowerShell
como administrador y ejecuta una sola vez:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\setup-nemotron-pc-host.ps1" -NaoIp <NAO_IP>
```

El script:

- crea `%LOCALAPPDATA%\naoControlGatewayHost`;
- instala el lanzador y sus dependencias en un entorno virtual aislado;
- copia el `.env` local sin mostrar sus valores;
- obtiene por SCP el secreto HMAC del robot y lo guarda sin imprimirlo;
- registra el lanzador en el inicio de sesión del usuario;
- abre únicamente TCP `6676` para el perfil privado y la subred local;
- inicia el proceso oculto y muestra las IPv4 disponibles del PC.

Si no existe `.env`, crea una copia de `.env.example`, la abre en Notepad y se
detiene. Completa allí las credenciales y vuelve a ejecutar el mismo comando.

## Configurar el destino y probar

1. Despliega el NAO con `deploy-nao.ps1 -StartServices`.
2. Abre `http://<NAO_IP>:3000` y entra en **Red**.
3. Introduce una de las IPv4 mostradas por el setup del PC.
4. Pulsa **Guardar IP del PC** y mantén el sensor táctil trasero durante tres
   segundos.
5. Mantén el bumper izquierdo 1.5 segundos. El robot debe anunciar que el modo
   inteligente está listo.
6. Mantén el bumper derecho mientras hablas y suéltalo para enviar el turno.

## Logs

En el PC:

```powershell
Get-Content "$env:LOCALAPPDATA\naoControlGatewayHost\logs\launcher.log" -Wait
Get-Content "$env:LOCALAPPDATA\naoControlGatewayHost\logs\gateway.log" -Wait
```

En el NAO:

```sh
tail -F /home/nao/logs/naoControl/intelligence.log \
        /home/nao/logs/naoControl/pc_bundle.log
```

## Límites de confianza

El lanzador no acepta comandos remotos ni URLs elegidas por el navegador. La
IP del NAO y la URL del bundle se derivan de la conexión entrante, el nombre del
archivo es fijo y la extracción rechaza rutas externas, enlaces y dispositivos.
El código del bundle no contiene secretos; `.env` permanece en el PC.

Los puertos `6676` y `6677` usan HTTP dentro de la LAN. La orden de inicio está
autenticada y el bundle tiene integridad HMAC/SHA-256, pero los metadatos no se
cifran. Usa Ethernet directo o una red privada confiable durante esta etapa.
