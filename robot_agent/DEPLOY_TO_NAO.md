# Despliegue al robot NAO (instrucciones en español)

Este documento describe qué archivos del backend/agent debes copiar al robot NAO, en qué rutas colocarlos y comandos paso a paso (tanto por terminal como por herramientas GUI). Está pensado para NAO con sistema operativo NAOqi (Linux embarcado) y acceso SSH/SCP. Asume que el robot acepta conexiones SSH y que tienes las credenciales (usuario: `nao`, contraseña o clave).

IMPORTANTE: No copies secretos (archivos con credenciales) sin cifrado. Estas instrucciones no habilitan autenticación fuerte por defecto; considera agregar una token simple en el `robot_agent` si el robot va a estar en una red insegura.

Resumen de contenido a copiar

- Código del agente (obligatorio):
  - `robot_agent/agent.py`
  - `robot_agent/requirements.txt`
  - (opcional) `robot_agent/*.py` adicionales si existen

- Archivos del backend que puedes querer ejecutar en el robot (solo si deseas ejecutar la lógica allí):
  - `nao/models/*` (si quieres ejecutar el predictor en el robot) — preferible mantener en el servidor host
  - `nao/scripts/*` (scripts NAO: `control_server.py`, `launcher.py`, `video_stream.py`, `logger.py`, etc.)

- Recursos y datos:
  - `models/` o `models_npz_automl/feature_scaler.npz` y `lightgbm_model_*.npz` (si correspondiera)


Rutas recomendadas en el robot

Recomiendo organizar los archivos en `/home/nao/nao_control/`:

- Agente (Python2 compatible):
  - `/home/nao/nao_control/agent/agent.py`
  - `/home/nao/nao_control/agent/requirements.txt`
  - otros módulos: `/home/nao/nao_control/agent/lib/`

- Modelos (opcional):
  - `/home/nao/nao_control/models/feature_scaler.npz`
  - `/home/nao/nao_control/models/lightgbm_model_Frequency.npz` (y demás modelos)
  - `/home/nao/nao_control/models/golden_parameters.csv`


Copiar archivos desde Windows (PowerShell) vía `scp` (ejemplos)

1) Copiar el agente al robot (PowerShell):

```powershell
# Asume usuario 'nao' y IP del robot 192.168.1.100
scp C:\Users\limao\Desktop\U\ SABANA\Semillero\NaoControl\naoControl\robot_agent\agent.py nao@192.168.1.100:/home/nao/nao_control/agent/agent.py
scp C:\Users\limao\Desktop\U\ SABANA\Semillero\NaoControl\naoControl\robot_agent\requirements.txt nao@192.168.1.100:/home/nao/nao_control/agent/requirements.txt
```

Si hay varias dependencias o archivos, puedes copiar la carpeta completa comprimida y descomprimir en el robot:

```powershell
# Crear un zip local
powershell -Command "Compress-Archive -Path 'C:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\robot_agent\*' -DestinationPath 'C:\Users\limao\Desktop\nao_agent.zip'"
scp C:\Users\limao\Desktop\nao_agent.zip nao@192.168.1.100:/home/nao/
```

Luego en el robot (SSH) descomprimir:

```bash
# en robot
cd /home/nao
unzip nao_agent.zip -d /home/nao/nao_control/agent
```

Usar WinSCP (GUI)

- Si prefieres GUI, usa WinSCP: conecta con `scp` o `sftp` al robot (host `192.168.1.100`, user `nao`), y arrastra la carpeta `robot_agent` a `/home/nao/nao_control/agent`.


Instalar dependencias en el robot (Python2)

1) Conéctate al robot por SSH:

```bash
ssh nao@192.168.1.100
```

2) Verifica la existencia de Python2 (NAO suele usar Python2.7).

```bash
python2 --version
```

3) Instala dependencias usando `pip` de Python2. En muchos NAO no hay `pip` instalado; si existe, usa:

```bash
cd /home/nao/nao_control/agent
pip2 install --user -r requirements.txt
```

Si `pip2` no está disponible, puedes usar `easy_install` o instalar pip en el robot (requiere acceso a repositorios o copiar wheel files).


Iniciar el agente en background

Recomiendo usar `nohup` o `tmux` para mantener el agente corriendo:

```bash
# desde SSH en robot
cd /home/nao/nao_control/agent
# usar nohup para ejecutar en background y redirigir logs
nohup python2 agent.py > agent.log 2>&1 &

# verificar proceso
ps aux | grep agent.py

# ver logs
tail -f agent.log
```

Si el robot tiene `systemd` (poco común) puedes crear un servicio; lo más simple es añadir una entrada a `crontab` para reiniciar el agente en cada arranque:

```bash
crontab -e
# añadir la línea (ejemplo):
@reboot /usr/bin/python2 /home/nao/nao_control/agent/agent.py > /home/nao/nao_control/agent/agent.log 2>&1
```



Copiar modelos (.npz) al robot (opcional)

Si deseas ejecutar los modelos en el robot (no recomendado si el robot es viejo o tiene pocos recursos), copia la carpeta `nao/models/` a `/home/nao/nao_control/models`:

```powershell
scp C:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\nao\models\* nao@192.168.1.100:/home/nao/nao_control/models/
```

Verifica en el robot:

```bash
ls -la /home/nao/nao_control/models
```


Verificación rápida de endpoints

Desde tu PC (PowerShell) puedes ejecutar `Invoke-WebRequest` o `curl` para comprobar que el agente responde. El `robot_agent` por defecto escucha en el puerto 5000 (ajusta si lo cambias):

```powershell
# Prueba posture
Invoke-WebRequest -Uri http://192.168.1.100:5000/posture -Method GET

# Probar comportamiento siu (behavior)
Invoke-WebRequest -Uri http://192.168.1.100:5000/behavior/siu -Method POST

# Alternativamente con curl si está instalado
curl http://192.168.1.100:5000/health
```

Comandos útiles desde el robot para interacción con NAOqi

En `agent.py` se usan proxies como `ALMotion`, `ALRobotPosture` y `ALBehaviorManager`. Puedes ejecutar Python2 interactivo en el robot para probar proxies:

```bash
python2
>>> from naoqi import ALProxy
>>> motion = ALProxy('ALMotion', '127.0.0.1', 9559)
>>> motion.getSummary()
```


Seguridad mínima y recomendaciones

- Aísla la red del robot cuando sea posible.
- Considera usar claves SSH en lugar de contraseña para `ssh/scp`.
- Si vas a exponer un agente HTTP en la red pública, añade al menos un simple token (comprobar en `agent.py` antes de ejecutar acciones críticas).


Problemas comunes y soluciones

- Error: «pip2: command not found» — instala pip en el robot o copia paquetes wheel y usa `pip` local.
- Error: falta de permisos al escribir en `/home/nao` — asegúrate de usar el usuario `nao` o `sudo` si es necesario (NAO suele usar `nao`).
- El agente no responde después de reinicio — asegúrate de que el `crontab` o el servicio se configuró correctamente y que `python2` está en la ruta.


Checklist rápido

- [ ] Copiar `agent.py` y `requirements.txt` a `/home/nao/nao_control/agent`
- [ ] Instalar dependencias: `pip2 install -r requirements.txt`
- [ ] Copiar modelos (opcional) a `/home/nao/nao_control/models`
- [ ] Iniciar agente: `nohup python2 agent.py > agent.log 2>&1 &`
- [ ] Verificar endpoint: `curl http://<NAO_IP>:5000/health`


Soporte y pasos siguientes

Si quieres, puedo:

- Generar un script `deploy_to_nao.ps1` (PowerShell) que haga `scp` y `ssh` automáticamente.
- Añadir autenticación por token simple al `robot_agent/agent.py`.
- Crear un `systemd` unit o script de inicio más robusto si el robot lo soporta.

---
Documento generado automáticamente por el asistente de desarrollo local.
