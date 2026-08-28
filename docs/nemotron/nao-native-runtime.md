# Nemotron autónomo dentro del NAO

Nemotron ya no necesita un gateway ejecutándose en un PC. El razonamiento y la
percepción pesados siguen ocurriendo en NVIDIA Cloud, pero el cliente ligero,
la captura, la validación y la ejecución viven dentro del robot.

```text
bumper → audio + cámara → HTTPS desde NAO → NVIDIA Nemotron
       ← respuesta + tools ← validación local ← NAOqi
```

## Comportamiento por proveedor

- **Nemotron NVIDIA:** funciona de forma autónoma en el NAO. Requiere una red
  con salida a Internet y la clave NVIDIA configurada una vez en el robot.
- **Gemma LAN autenticado:** conserva el gateway de PC, porque el servidor del
  modelo está alojado en otra máquina. La IP de destino y el launcher solo son
  relevantes en este modo.

Al entrar en modo inteligente con Nemotron, el bumper no intenta contactar el
puerto 6676 ni exige una IP de PC. Al soltar el bumper de grabación, un hilo
local procesa el turno para no bloquear la lectura de sensores. La
transcripción, respuesta y acciones se guardan en el mismo estado que consulta
la interfaz web.

## Configuración inicial única

Después de desplegar el proyecto, ejecute una sola vez desde cualquier equipo
que pueda acceder por SSH al robot:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\configure-nao-nemotron.ps1" -NaoIp <IP_DEL_NAO>
```

También puede hacer despliegue y configuración inicial en un solo comando:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\deploy-nao.ps1" -NaoIp <IP_DEL_NAO> -StartServices -ConfigureNemotron
```

El script reutiliza `NVIDIA_API_KEY` del `.env` ignorado del antiguo launcher,
si existe; de lo contrario la solicita ocultándola. La clave se transmite por
SCP y queda en:

```text
/home/nao/naoControl/config/nvidia_api_key
```

El archivo usa permisos `0600`, no se incluye en Git, no entra al paquete de
despliegue y los despliegues posteriores lo preservan. Después de esta
configuración no se instala ni se mantiene ningún componente en ese PC.

## Transporte HTTPS

El runtime intenta primero HTTPS con la biblioteca estándar de Python del NAO.
Si esa pila TLS falla y existe un `curl` ejecutable, lo usa como respaldo. La
clave no aparece en argumentos de proceso: el respaldo utiliza archivos
temporales `0600` y los elimina al terminar.

La compatibilidad TLS definitiva debe probarse en el robot físico. Si su imagen
de NAOqi no negocia TLS con NVIDIA y tampoco dispone de un `curl` moderno, se
puede incluir un binario autocontenido en `nao/vendor/curl/curl`; el runtime lo
detecta automáticamente y no requiere instalación en el PC.

## Arranque diario

1. Encienda el NAO.
2. Espere a que se conecte a Wi-Fi o Ethernet con Internet.
3. El launcher de autoload inicia automáticamente el control web, la cámara y
   el runtime inteligente. El sensor central de la cabeza sigue permitiendo
   detenerlos o iniciarlos manualmente con una pulsación de tres segundos.
4. Entre en modo inteligente con el bumper configurado.
5. Mantenga el bumper de grabación, hable y suéltelo.

No hay comando, terminal, launcher ni proceso que iniciar diariamente en un
PC. Los logs quedan en:

```sh
tail -F /home/nao/logs/naoControl/intelligence.log
```

## Seguridad y límites

El contenido del micrófono y la cámara sale directamente del NAO hacia NVIDIA.
Las acciones propuestas por el modelo se comparan con el registro local y se
rechazan si la transcripción no contiene una petición física explícita. Una
emergencia y los límites de postura/velocidad siguen controlados localmente.

La autonomía diaria depende de dos recursos externos inevitables: conectividad
a Internet y disponibilidad de NVIDIA. Gemma LAN depende además del computador
que ejecuta su servidor.
