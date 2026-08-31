# Operación y diagnóstico

## Uso diario

1. Enciende el NAO y conéctalo a Ethernet o Wi-Fi.
2. Abre `http://<IP_NAO>:3000` desde un PC de la misma red.
3. El control web y el gestor de red ya están activos. Mantén tres segundos el
   sensor central de la cabeza solo para detener o volver a iniciar el control.
4. En **Sistema inteligente**, selecciona Nemotron o Gemma, define idioma y,
   para Gemma, escribe la IP del PC que expone `http://IP:8080/v1`.
5. Guarda. El PC desde donde abriste la interfaz queda inferido como gateway
   solo si seleccionaste Gemma; no escribas esa IP manualmente.
6. Usa el bumper de entrada al modo inteligente y el bumper de captura según
   el flujo configurado. El panel muestra lo escuchado, respondido, las tools y
   el tiempo hasta que empezó la voz.

Si preparaste KWS, decir “NAO” en el micrófono del PC gateway también inicia la
grabación mientras el NAO está listo; el bumper la detiene. Consulta
[`keyword-spotting.md`](nemotron/keyword-spotting.md).

## Proveedores

| Modo | Requisito diario |
| --- | --- |
| Nemotron NVIDIA | Internet desde el NAO y clave NVIDIA previamente instalada en el robot. |
| Gemma LAN | PC modelo encendido con endpoint `/v1`, PC gateway preparado una sola vez y ambos alcanzables en LAN. |

Cambiar de proveedor no migra ni revela claves. La configuración solo acepta
IPv4 privadas o link-local y fija el puerto/model endpoint de Gemma en `8080/v1`.

## Despliegue

Desde la raíz del repositorio en PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\deploy-nao.ps1" -NaoIp <IP_NAO> -StartServices
```

El primer `ssh/scp` solicita la contraseña del robot. Si cambia de IP,
reemplaza únicamente `<IP_NAO>`; no cambies rutas ni claves. Después del
despliegue, recarga la página sin caché (`Ctrl+F5`).

## Logs

En el NAO:

```sh
tail -F /home/nao/logs/naoControl/intelligence.log \
        /home/nao/logs/naoControl/control.log \
        /home/nao/logs/naoControl/web.log
```

Para Gemma, en el PC gateway:

```powershell
Get-Content "$env:LOCALAPPDATA\naoControlGatewayHost\logs\gateway.log" -Wait
```

## Qué revisar cuando falle

- **No entra al modo inteligente:** mira el texto de rechazo en
  `intelligence.log`; puede ser batería, red, Nemotron sin configurar o gateway
  Gemma inalcanzable.
- **Proveedor no disponible:** verifica que el endpoint Gemma responda
  `/v1/models` desde el PC gateway y que su clave siga solo en el `.env` local.
- **No hay transcripción:** confirma `audio_diagnostics` y `TRANSCRIPTION` en
  el log inteligente.
- **No hay voz o la latencia no aparece:** revisa que el último turno tenga
  respuesta y la acción `say` haya sido aceptada; la métrica se guarda tras esa
  aceptación.
- **El idioma es incorrecto:** guarda de nuevo idioma en el panel. El cambio se
  aplica a modelo, TTS y mensajes del sistema; al reiniciar, se recupera del
  archivo de configuración del NAO.
