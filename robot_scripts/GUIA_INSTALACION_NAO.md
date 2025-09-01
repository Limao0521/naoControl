# Guía Completa: Probar Adaptive Walk con LightGBM en NAO

## 🚀 Instalación Rápida

### Opción A: Script Automático (Windows)
```powershell
# En PowerShell como administrador
cd "c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\robot_scripts"
.\install_nao_adaptive_walk.ps1 -NAO_IP 192.168.1.100
```

### Opción B: Script Automático (Linux/Mac)
```bash
cd /path/to/robot_scripts
chmod +x install_nao_adaptive_walk.sh
./install_nao_adaptive_walk.sh 192.168.1.100
```

### Opción C: Instalación Manual

#### 1. Preparar el NAO
```bash
# Conectarse al NAO
ssh nao@<IP_DEL_NAO>

# Crear directorios
mkdir -p /home/nao/scripts
mkdir -p /home/nao/models_npz_automl
mkdir -p /home/nao/logs
mkdir -p /home/nao/Webs/ControllerWebServer
```

#### 2. Copiar archivos desde tu PC
```bash
# Scripts principales (OBLIGATORIOS)
scp adaptive_walk_lightgbm_nao.py nao@<IP_NAO>:/home/nao/scripts/
scp control_server.py nao@<IP_NAO>:/home/nao/scripts/
scp launcher.py nao@<IP_NAO>:/home/nao/scripts/
scp data_logger.py nao@<IP_NAO>:/home/nao/scripts/
scp logger.py nao@<IP_NAO>:/home/nao/scripts/

# Modelos LightGBM (OBLIGATORIOS)
scp -r ../models_npz_automl/* nao@<IP_NAO>:/home/nao/models_npz_automl/

# Interfaz web (OPCIONAL pero recomendado)
scp -r ../ControllerWebServer/* nao@<IP_NAO>:/home/nao/Webs/ControllerWebServer/

# Configurar permisos
ssh nao@<IP_NAO> "chmod +x /home/nao/scripts/*.py"
```

## 🧪 Verificación de Instalación

### Test de compatibilidad Python 2.7
```bash
# En el NAO
ssh nao@<IP_NAO>
cd /home/nao/scripts
python2 test_python2_compatibility.py
```
**Resultado esperado:** Todos los tests deben pasar ✓

### Verificar modelos LightGBM
```bash
# En el NAO
ls -la /home/nao/models_npz_automl/
# Debe mostrar:
# feature_scaler.npz
# lightgbm_model_Frequency.npz
# lightgbm_model_MaxStepTheta.npz
# lightgbm_model_MaxStepX.npz
# lightgbm_model_MaxStepY.npz
# lightgbm_model_StepHeight.npz
```

## 🎮 Cómo Usar el Sistema

### Método 1: Launcher Automático (RECOMENDADO)
```bash
# En el NAO
cd /home/nao/scripts
python2 launcher.py
```

**Cómo funciona:**
- El NAO dirá: *"Presiona mi cabeza tres segundos para activar modo control"*
- Presiona el **sensor táctil medio** de la cabeza por **3+ segundos**
- El NAO cambiará al modo control y dirá: *"nao control iniciado"*
- Para volver a Choregraphe: presiona 3+ segundos de nuevo

### Método 2: Control Server Manual
```bash
# En el NAO
cd /home/nao/scripts
python2 control_server.py
```

### Método 3: Adaptive Walk Directo (Solo testing)
```bash
# En el NAO
cd /home/nao/scripts
python2 adaptive_walk_lightgbm_nao.py
```

**Comandos disponibles:**
- `start` - Iniciar caminata adaptiva
- `stop` - Detener caminata
- `predict` - Mostrar predicción actual
- `quit` - Salir

## 🌐 Interfaz Web

### Acceder a la interfaz
1. Abrir navegador en: `http://<IP_DEL_NAO>:8000`
2. La interfaz debe cargar automáticamente

### Comandos WebSocket importantes

#### Activar Adaptive Walk LightGBM
```json
{
  "action": "adaptiveLightGBM",
  "enabled": true
}
```

#### Caminar con adaptación automática
```json
{
  "action": "walk",
  "vx": 0.3,
  "vy": 0.0,
  "wz": 0.0
}
```

#### Obtener estadísticas
```json
{
  "action": "getLightGBMStats"
}
```

#### Iniciar logging de datos
```json
{
  "action": "startLogging",
  "duration": 300,
  "frequency": 10
}
```

## 📊 Monitoreo y Debugging

### Ver logs en tiempo real
```bash
# En el NAO
tail -f /home/nao/logs/adaptive_data_*.csv
```

### Verificar estado del sistema
```bash
# Ver procesos activos
ps aux | grep python2

# Ver puertos en uso
netstat -an | grep -E "6671|8000|8080"

# Ver logs del sistema
tail -f /var/log/naoqi/servicemanager.log
```

### Test manual de predicción
```bash
# En el NAO
cd /home/nao/scripts
python2 -c "
from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
walker = AdaptiveWalkLightGBM('models_npz_automl')
params = walker.predict_gait_parameters()
print('Predicción:', params)
"
```

## 🛠️ Solución de Problemas

### Error: "No such file or directory"
```bash
# Verificar que los archivos están en el lugar correcto
ls -la /home/nao/scripts/
ls -la /home/nao/models_npz_automl/
```

### Error: "SyntaxError: invalid syntax"
- **Causa:** f-strings no soportados en Python 2.7
- **Solución:** Usar la versión corregida del archivo

### Error: "No se pueden cargar modelos"
```bash
# Verificar modelos
ls -la /home/nao/models_npz_automl/*.npz
# Verificar permisos
chmod 644 /home/nao/models_npz_automl/*.npz
```

### Error: "Puerto 6671 ocupado"
```bash
# Matar procesos previos
pkill -f control_server.py
pkill -f launcher.py
# Reiniciar
python2 launcher.py
```

### NAO no responde
```bash
# Despertar robot
python2 -c "
from naoqi import ALProxy
motion = ALProxy('ALMotion', '127.0.0.1', 9559)
motion.wakeUp()
"
```

## 🎯 Flujo de Trabajo Recomendado

### 1. Primera instalación
1. Ejecutar script de instalación
2. Verificar test de compatibilidad  
3. Probar launcher automático
4. Verificar interfaz web

### 2. Uso diario
1. Conectar al NAO: `ssh nao@<IP>`
2. Ejecutar launcher: `python2 launcher.py`
3. Activar modo control: presionar cabeza 3+ segundos
4. Usar interfaz web para controlar

### 3. Testing y desarrollo
1. Iniciar logging: comando `startLogging` en web
2. Caminar con diferentes parámetros
3. Monitorear logs: `tail -f /home/nao/logs/adaptive_data_*.csv`
4. Analizar datos con scripts de análisis

### 4. Troubleshooting
1. Verificar conexión NAOqi
2. Revisar logs del sistema
3. Probar componentes individualmente
4. Reiniciar servicios si es necesario

## 📋 Checklist de Verificación

- [ ] SSH funciona al NAO
- [ ] Directorios creados en el NAO
- [ ] Scripts copiados y con permisos ejecutables
- [ ] Modelos LightGBM copiados (6 archivos .npz)
- [ ] Test de compatibilidad Python 2.7 pasa
- [ ] Launcher se ejecuta sin errores
- [ ] Control server se conecta (puerto 6671)
- [ ] Interfaz web carga (puerto 8000)
- [ ] Adaptive walk predice parámetros
- [ ] NAO puede caminar con adaptación
- [ ] Logging de datos funciona

¡Con esta guía deberías poder instalar y usar el sistema completo de adaptive walk con LightGBM en tu NAO!
