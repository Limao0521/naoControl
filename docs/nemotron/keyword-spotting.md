# Activación por palabra clave: “NAO”

El clasificador `nao_classifier.onnx` se ejecuta en el PC gateway con Python
3.11, ONNX Runtime y openWakeWord. El NAO V6 no puede ejecutar ese modelo
directamente porque usa Python 2.7 y no dispone de ese runtime.

## Flujo

1. Mantén el bumper de entrada para pasar el NAO a modo inteligente.
2. En modo Gemma LAN, el gateway de PC se conecta al NAO de forma autenticada.
3. Con KWS activado, el micrófono de ese PC evalúa la palabra **NAO** con
   umbral `0.995` y dos aciertos consecutivos.
4. Una detección firmada inicia la grabación de audio del NAO. Los ojos pasan a
   verde igual que con el bumper manual.
5. Si la grabación comenzó por palabra clave, presiona cualquier vez el bumper
   de grabación para detenerla y enviar el turno. El flujo manual de
   mantener/soltar el bumper sigue funcionando sin cambios.

La palabra clave inicia **grabación**, no entra por sí sola al modo inteligente.
Así se conserva la confirmación física para habilitar las funciones del agente.

## Preparación única

Desde la raíz de `naoControl`:

```powershell
.\tools\import-nao-kws-model.ps1
```

El script usa por defecto el modelo del proyecto de investigación indicado y
copia solo `nao_classifier.onnx` y `openwakeword_encoder` a
`pc_gateway\models\kws`. Esos artefactos quedan excluidos de Git pero sí viajan
en el bundle autenticado hacia el PC gateway al desplegar.

Después despliega el NAO y prepara/actualiza el PC gateway una vez:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\deploy-nao.ps1" -NaoIp <IP_NAO> -StartServices
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\setup-nemotron-pc-host.ps1" -NaoIp <IP_NAO>
```

En `%LOCALAPPDATA%\naoControlGatewayHost\.env` agrega:

```dotenv
NAO_KWS_ENABLED=true
NAO_KWS_THRESHOLD=0.995
NAO_KWS_BLOCKSIZE=16000
```

No copies allí claves ni el modelo manualmente: el modelo llega en el bundle
firmado desde el NAO. Reinicia el gateway al terminar el setup o vuelve a
entrar a modo inteligente para que reciba el bundle nuevo.

## Diagnóstico

En el PC gateway:

```powershell
Get-Content "$env:LOCALAPPDATA\naoControlGatewayHost\logs\gateway.log" -Wait
```

Debes ver `KWS enabled threshold=0.995` y luego `KWS score=...`. Una detección
correcta registra `KWS keyword_detected`; en el NAO se observa
`CAPTURE_STARTED` en `intelligence.log`.

Si aparece `KWS disabled`, verifica que el modelo y el encoder se importaron,
que el `.env` tiene `NAO_KWS_ENABLED=true` y que el PC gateway usa Python 3.11
con las dependencias instaladas.
