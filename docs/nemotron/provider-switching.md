# Cambio de proveedor: Nemotron y Gemma local

El control inteligente puede usar NVIDIA Nemotron en la nube o un servidor
Gemma local o autenticado dentro de la red privada. El audio, la cámara, la
validación de herramientas y la ejecución NAOqi son compartidos; cambiar el
proveedor no cambia el espacio de acciones ni permite acceso directo al robot.

## Configuración del PC

La configuración sensible permanece en el `.env` del runtime del launcher del
PC. No se copia al NAO ni se envía al navegador.

```dotenv
INTELLIGENCE_PROVIDER=nemotron
NVIDIA_API_KEY=<clave configurada solo en este PC>
GEMMA_BASE_URL=http://127.0.0.1:8080/v1
GEMMA_API_KEY=
GEMMA_MODEL=
```

- `INTELLIGENCE_PROVIDER` es el proveedor usado mientras el NAO todavía no ha
  sincronizado su selección persistida.
- `NVIDIA_API_KEY` es obligatoria para activar Nemotron. Puede omitirse si este
  PC usará exclusivamente Gemma y el valor inicial es `gemma_local`.
- `GEMMA_BASE_URL` admite loopback o una IPv4 literal de las redes privadas
  `10.0.0.0/8`, `172.16.0.0/12` y `192.168.0.0/16`. No admite destinos públicos
  ni nombres DNS remotos. La interfaz web no puede modificarla.
- `GEMMA_API_KEY` puede quedar vacía para loopback. Es obligatoria para una IP
  privada LAN y se envía como `Authorization: Bearer ...`.
- `GEMMA_MODEL` vacío consulta `GET /v1/models` y toma el primer modelo activo.

Para Gemma en el mismo PC, inicie primero el servidor local y compruebe:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/v1/models | ConvertTo-Json -Depth 10
```

### Gemma autenticado en otro PC

La configuración operativa actual usa:

```dotenv
GEMMA_BASE_URL=http://172.23.12.52:8080/v1
GEMMA_API_KEY=<clave privada del servidor Gemma>
```

Estas variables pertenecen al PC que ejecuta el gateway, en:

```text
%LOCALAPPDATA%\naoControlGatewayHost\.env
```

No copie la clave al repositorio, al NAO ni a la interfaz web. Para validar la
red sin revelar la clave, una petición sin cabecera debe responder `HTTP 401`;
el gateway valida después `/v1/models` usando la credencial del `.env`.

El gateway no inicia Docker ni el modelo Gemma. El launcher del puerto 6676
solo instala y ejecuta el gateway recibido desde el NAO.

## Cambiar desde la interfaz

1. Inicie el control web y abra `http://<IP_DEL_NAO>:3000`.
2. Abra el panel **Nemotron**, cuyo contenido se titula **Sistema inteligente**.
3. En **Proveedor de inteligencia**, seleccione **Nemotron NVIDIA** o
   **Gemma LAN autenticado**.
4. En **Idioma de respuesta**, seleccione **Español** o **English**. Este valor
   controla tanto la respuesta del modelo como la voz del NAO.
5. Pulse **Guardar configuración**.
6. Compruebe por separado **Seleccionado**, **Activo** y la disponibilidad.

La selección se guarda en:

```text
/home/nao/naoControl/config/intelligence_provider.json
```

El archivo contiene únicamente identificadores, el idioma y estado limitado;
no contiene claves ni URLs. El gateway del NAO publica el cambio por el
WebSocket firmado.
El PC comprueba el proveedor y lo activa antes del siguiente turno. No se
cambia de modelo a mitad de una interacción.

Si Gemma no está iniciado, no es alcanzable o rechaza la clave, **Seleccionado**
puede indicar Gemma mientras
**Activo** continúa mostrando Nemotron junto con el error. Inicie Gemma y pulse
**Guardar configuración** de nuevo para repetir la comprobación.

## Diagnóstico

En el PC, el launcher guarda:

```text
%LOCALAPPDATA%\NaoControl\Nemotron\logs\gateway.log
%LOCALAPPDATA%\NaoControl\Nemotron\logs\gateway-error.log
```

En el NAO:

```sh
tail -F /home/nao/logs/naoControl/intelligence.log
```

El estado web nunca devuelve las claves NVIDIA/Gemma, el endpoint Gemma ni el contenido
del `.env`.

## LEDs del modo inteligente

- ojos azules: listo;
- ojos verdes: grabando;
- ojos naranjas: procesando;
- ojos rojos: error o emergencia;
- color de ojos pedido explícitamente: visible durante tres segundos y luego
  restaurado al indicador del modo;
- pecho: el color pedido permanece;
- oídos: físicamente solo admiten azul o apagado.

Una nueva captura cancela cualquier restauración pendiente para impedir que un
temporizador antiguo sobrescriba el verde de grabación.

## Reversión

Seleccione **Nemotron NVIDIA** y guarde. Si la interfaz no está disponible,
elimine únicamente `intelligence_provider.json`; al reiniciar el servicio se
recupera la selección predeterminada `nemotron`. No elimine
`robot_gateway.secret` ni `.env`.
