# NAO: instrucciones rápidas de despliegue

Resumen corto para desplegar todo el runtime en la cabeza del NAO (modo autónomo):

1. Copiar la carpeta `nao/` al robot en `/home/nao/nao_control/` (o copiar su contenido a `/home/nao/scripts/` para mantener compatibilidad con `launcher.py`).

2. Instalar dependencias (si `pip2` está disponible):

```bash
ssh nao@<NAO_IP>
cd /home/nao/nao_control
pip2 install --user -r nao/requirements-robot.txt
```

3. Iniciar el `launcher` para arrancar `control_server`, `logger` y `video_stream`:

```bash
cd /home/nao/nao_control/nao/scripts
# opción (directa):
nohup python2 launcher.py > /home/nao/launcher.log 2>&1 &
# o arrancar scripts individualmente
nohup python2 control_server.py > control_server.log 2>&1 &
nohup python2 video_stream.py > video_stream.log 2>&1 &
nohup python2 logger.py > logger.log 2>&1 &
```

4. Verificar que los procesos corren y que `control_server` atiende web sockets y `video_stream` sirve MJPEG.

5. Si quieres inferencia ML en el NAO: copia `nao/models/` a `/home/nao/nao_control/models/` y asegúrate de que `adaptive_walk_lightgbm_nao.py` apunte al directorio correspondiente.

6. Consideraciones:
- Preservar `#!/usr/bin/env python2` en todos los scripts.
- Evitar instalar paquetes compilados (LightGBM) en el NAO si no existen ruedas compatibles.
- Para reinicio automático usa `crontab` o el `rc.local`/service incluido en `nao/installer/payload_scripts/`.
