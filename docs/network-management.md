# Gestión segura de red desde NAO Control

## Resultado

El menú **Red** permite consultar interfaces y estado, escanear Wi-Fi, conectar
una red, desconectar un perfil y eliminarlo. Las consultas salen desde la página
web hacia un broker que escucha exclusivamente en el PC local. Las operaciones
administrativas viajan del PC al NAO por SSH; nunca usan el WebSocket heredado
del control en el puerto 6671.

Los cambios requieren presencia física: después de solicitar conectar,
desconectar o eliminar, el NAO pide mantener presionado el sensor táctil trasero
de la cabeza durante tres segundos. Soltarlo antes reinicia el contador.

## Puertos y procesos

| Componente | Equipo | Dirección |
|---|---|---|
| Página de control | NAO | `http://<NAO_IP>:3000` |
| Control WebSocket | NAO | `ws://<NAO_IP>:6671` |
| Gateway Nemotron | NAO | `ws://<NAO_IP>:6674` |
| Broker de red | PC | `http://127.0.0.1:6675` |

El broker forma parte del mismo proceso Python 3 que ejecuta Nemotron. No se
debe publicar el puerto 6675 en la LAN ni cambiar su host de loopback.

## Configuración inicial, una sola vez

Desde PowerShell, en la raíz del repositorio:

```powershell
.\tools\setup-nao-network-admin.ps1 -NaoIp <NAO_IP>
```

El comando:

1. Crea, si hace falta, `%USERPROFILE%\.ssh\nao_control_ed25519`.
2. Pide la contraseña SSH normal del NAO para instalar únicamente la clave
   pública.
3. Verifica una conexión posterior sin contraseña y con comprobación estricta
   de la identidad del host.
4. Actualiza el `.env` ignorado por Git con la IP, la ruta de la clave, el
   origen permitido y `NAO_NETWORK_BROKER_ENABLED=true`.

El script conserva las demás variables del `.env` y no copia la clave privada
dentro del proyecto. Si el `.env` era nuevo, abre el archivo local y completa
`NVIDIA_API_KEY` y `NAO_GATEWAY_SECRET` antes de arrancar el gateway.

## Compilar y desplegar

Cuando cambie el frontend:

```powershell
cd NaoControlReact
npm ci
npm run build
cd ..
```

El despliegue completo al robot continúa siendo un solo comando:

```powershell
.\tools\deploy-nao.ps1 -NaoIp <NAO_IP> -StartServices
```

El instalador valida con Python 2 el gateway, el control server y
`network_admin.py` antes de considerar exitoso el despliegue. No copia `.env`,
la clave SSH privada ni credenciales NVIDIA.

En otra terminal inicia el gateway del PC y conserva sus logs visibles:

```powershell
.\.venv\Scripts\python.exe -u -m nao_gateway.main --env-file .env --registry config\action_registry.json
```

Debe aparecer:

```text
NAO network broker listening on http://127.0.0.1:6675
```

## Uso del panel

1. Abre `http://<NAO_IP>:3000` y selecciona el icono **Red**.
2. Comprueba el estado y las IP antes de realizar cambios.
3. Usa **Escanear redes** y selecciona la red deseada.
4. Escribe la contraseña y pulsa **Solicitar conexión**. El campo se limpia
   inmediatamente después del envío.
5. Cuando el NAO lo indique, mantén el sensor trasero durante tres segundos.

Desconectar y eliminar siempre muestran una advertencia. Si no se detecta
Ethernet, el panel señala que puede tratarse de la única ruta de administración.
La advertencia no sustituye la confirmación física.

## Logs sin credenciales

El resultado robot-side se registra en:

```sh
tail -F /home/nao/logs/naoControl/network_admin.log
```

Los eventos contienen operación, estado y fecha. Las claves `passphrase`,
`password`, `psk` y `secret` se reemplazan por `[REDACTED]`. El broker tampoco
devuelve `stderr` de SSH al navegador.

## Prueba física segura

La primera validación debe hacerse con Ethernet conectado y una red Wi-Fi de
prueba que no sea la única vía de acceso:

1. Probar `status`, `scan` y `profiles` sin cambios.
2. Solicitar conexión y soltar el sensor antes de tres segundos; el perfil no
   debe cambiar.
3. Repetir manteniendo el sensor tres segundos y confirmar la nueva IP.
4. Revisar logs del PC y del NAO para comprobar que no aparece la contraseña.
5. Probar desconectar y eliminar únicamente el perfil de prueba.

## Recuperación

Un cambio correcto puede cerrar HTTP, cámara, Nemotron y la sesión SSH. El panel
lo muestra como `transport_lost_after_apply`: significa que el enlace se perdió
durante la transición y se debe verificar el resultado por Ethernet o por la
nueva IP; no se interpreta automáticamente como éxito.

Si el robot fue reinstalado o cambió legítimamente su clave de host, verifica
primero que sea el mismo NAO y después retira exclusivamente la entrada de esa
IP:

```powershell
ssh-keygen -R <NAO_IP>
.\tools\setup-nao-network-admin.ps1 -NaoIp <NAO_IP>
```

Si queda inaccesible por Wi-Fi, conecta Ethernet, identifica la dirección
link-local mostrada por el robot y vuelve a ejecutar el setup y despliegue con
esa IP.

## API utilizada en el robot

El helper usa la API oficial NAOqi 2.8 de `ALConnectionManager`: `state`,
`interfaces`, `scan`, `services`, `provisionedServices`, `connect`,
`setServiceInput`, `disconnect` y `forget`. La contraseña se entrega mediante
el evento `NetworkServiceInputRequired`, como establece la documentación de
[SoftBank Robotics](http://doc.aldebaran.com/2-8/naoqi/connectionmanager/alconnectionmanager-api.html).
