# Gestión de red integrada en NAO Control

## Resultado

El menú **Red** permite consultar interfaces y estado, escanear Wi-Fi, listar
perfiles guardados, conectar una red, desconectar un perfil y eliminarlo. El
gestor vive dentro del control WebSocket del NAO: se inicializa con el control
y no requiere procesos, variables de entorno o claves SSH en el PC.

```text
Panel Red del navegador
        |
        | ws://<NAO_IP>:6671
        v
Control server del NAO
        |
        +-- NetworkAdminService
        +-- confirmación táctil trasera
        +-- ALConnectionManager de NAOqi
```

Nemotron puede estar apagado. La función de red no usa la API NVIDIA, el
gateway del PC ni el puerto `6675`.

## Puertos

| Componente | Equipo | Dirección |
|---|---|---|
| Página de control | NAO | `http://<NAO_IP>:3000` |
| Control y gestión de red | NAO | `ws://<NAO_IP>:6671` |
| Cámara | NAO | `http://<NAO_IP>:8080/video.mjpeg` |
| Gateway Nemotron opcional | NAO | `ws://<NAO_IP>:6674` |

## Despliegue e inicio

Desde PowerShell, en la raíz del repositorio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\deploy-nao.ps1" -NaoIp <NAO_IP> -StartServices
```

Ese es el único comando requerido. El paquete incluye la página compilada,
`control_server`, `network_admin.py` y sus dependencias robot-side. El deploy no
copia `.env`, claves privadas ni credenciales NVIDIA al robot.

Después abre:

```text
http://<NAO_IP>:3000
```

No necesitas ejecutar comandos adicionales en el PC ni preparar claves para
usar el menú de red.

## Uso del panel

1. Mantén Ethernet conectado durante las primeras pruebas.
2. Abre el menú **Red** y verifica el estado y las direcciones actuales.
3. Pulsa **Escanear redes** y selecciona una red.
4. Introduce la contraseña y solicita la conexión; el campo se limpia al enviar.
5. Cuando el NAO lo indique en español, mantén presionado el sensor táctil
   trasero de la cabeza durante tres segundos continuos.

Las consultas `status`, `scan` y `profiles` no necesitan confirmación física.
`connect`, `disconnect` y `forget` siempre la necesitan. Soltar el sensor antes
de tres segundos reinicia el contador y agotar el tiempo deja la red intacta.

## Seguridad y credenciales

- El control acepta solo seis operaciones de red tipadas; no acepta comandos de
  shell ni nombres de métodos arbitrarios.
- La contraseña no se devuelve al navegador ni se escribe en logs.
- El servidor registra únicamente `action`, `operation` y `request_id`, nunca el
  JSON WebSocket completo.
- Los resultados persistidos reemplazan `passphrase`, `password`, `psk` y
  `secret` por `[REDACTED]`.
- Una falla al inicializar `ALConnectionManager` deshabilita el menú de red sin
  impedir el movimiento, habla o control web normal.

La página actual usa HTTP y WebSocket sin TLS. La contraseña está protegida
contra logs y persistencia, pero no contra captura de tráfico por otra máquina
en la misma red. Prueba y opera esta función mediante Ethernet directo o una red
de laboratorio confiable. TLS queda como endurecimiento futuro.

## Logs

En el NAO:

```sh
tail -F /home/nao/logs/naoControl/control.log /home/nao/logs/naoControl/network_admin.log
```

El primer archivo confirma si aparece `Gestor de red integrado disponible`. El
segundo contiene únicamente resultados redacted de operaciones mutables.

## Prueba física segura

1. Verifica `status`, `scan` y `profiles` sin cambiar la red.
2. Solicita una conexión y suelta el sensor antes de tres segundos; confirma que
   no se creó ni activó el perfil.
3. Repite manteniendo el sensor durante tres segundos.
4. Si el enlace se pierde, no repitas automáticamente la mutación: comprueba la
   nueva IP mediante Ethernet o el panel del robot.
5. Revisa ambos logs y confirma que no aparece la contraseña.
6. Prueba `disconnect` y `forget` solamente con un perfil de laboratorio.

## Recuperación

Un cambio correcto puede cerrar la página, cámara, SSH y Nemotron al cambiar la
dirección del NAO. El panel presenta ese caso como transporte perdido, no como
éxito confirmado. Conecta Ethernet, identifica la nueva dirección y vuelve a
abrir `http://<NAO_IP>:3000`.

## API utilizada

El adaptador robot-side usa `ALConnectionManager` de NAOqi 2.8: `state`,
`interfaces`, `scan`, `services`, `provisionedServices`, `connect`,
`setServiceInput`, `disconnect` y `forget`. La presencia física se obtiene de
`RearTactilTouched` mediante `ALMemory`.
