# ⚠️ Solución: Motion Proxy No Disponible

## 🔍 **Tu problema actual:**
```
> start
[ERROR] Motion proxy no disponible
```

## ✅ **Código ya corregido**
El archivo `adaptive_walk_lightgbm_nao.py` ahora:
- ✅ Funciona en **modo simulación** cuando no hay conexión NAOqi
- ✅ Proporciona más información de debugging
- ✅ No se cuelga al intentar conectar

## 🚀 **Soluciones paso a paso**

### **Paso 1: Actualizar archivo en el NAO**
```bash
# Copiar archivo actualizado
scp adaptive_walk_lightgbm_nao.py nao@<IP_NAO>:/home/nao/scripts/
scp nao_connection_test.py nao@<IP_NAO>:/home/nao/scripts/
```

### **Paso 2: Probar diagnóstico de conexión**
```bash
# En el NAO
ssh nao@<IP_NAO>
cd /home/nao/scripts
python2 nao_connection_test.py
```

### **Paso 3: Probar adaptive walk actualizado**
```bash
# En el NAO
python2 adaptive_walk_lightgbm_nao.py
```

**Resultado esperado ahora:**
```
[WARN] Motion proxy no disponible - ejecutando en modo simulación
[SIMULATION] Simulando caminata con velocidades: x=0.020, y=0.000, theta=0.000
[SIMULATION] Parámetros de caminata que se aplicarían:
  StepHeight: 0.0200
  MaxStepX: 0.0400
  ...
```

## 🔧 **Posibles causas del problema**

### **Causa 1: NAO dormido**
```bash
# Despertar NAO
python2 -c "
from naoqi import ALProxy
motion = ALProxy('ALMotion', '127.0.0.1', 9559)
motion.wakeUp()
"
```

### **Causa 2: NAOqi no ejecutándose**
```bash
# Verificar estado NAOqi
ps aux | grep naoqi

# Reiniciar NAOqi si es necesario
sudo service naoqi restart
```

### **Causa 3: Robot en Autonomous Life**
```bash
# Deshabilitar Autonomous Life
python2 -c "
from naoqi import ALProxy
life = ALProxy('ALAutonomousLife', '127.0.0.1', 9559)
life.setState('disabled')
"
```

### **Causa 4: Problemas de permisos/conexión**
```bash
# Test básico de conexión
python2 -c "
from naoqi import ALProxy
try:
    motion = ALProxy('ALMotion', '127.0.0.1', 9559)
    print('Conexión OK, robot despierto:', motion.robotIsWakeUp())
except Exception as e:
    print('Error:', e)
"
```

## 🧪 **Tests específicos para tu caso**

### **Test 1: Verificar que el archivo está actualizado**
```bash
# En el NAO
grep -n "modo simulación" /home/nao/scripts/adaptive_walk_lightgbm_nao.py
```
**Debe mostrar líneas con "modo simulación"**

### **Test 2: Probar conexión directa**
```bash
# En el NAO
python2 -c "
import socket
sock = socket.socket()
sock.settimeout(5)
try:
    sock.connect(('127.0.0.1', 9559))
    print('Puerto 9559 accesible')
    sock.close()
except Exception as e:
    print('Puerto no accesible:', e)
"
```

### **Test 3: Verificar NAOqi**
```bash
# En el NAO
python2 -c "
try:
    from naoqi import ALProxy
    proxy = ALProxy('ALMotion', '127.0.0.1', 9559)
    print('NAOqi OK')
except Exception as e:
    print('NAOqi Error:', e)
"
```

## 🎯 **Comandos de emergencia**

### **Si el robot está "congelado":**
```bash
# Forzar despertar
sudo /etc/init.d/naoqi stop
sudo /etc/init.d/naoqi start

# Despertar físicamente
# Presiona botón del pecho del NAO por 3 segundos
```

### **Si NAOqi no responde:**
```bash
# Reinicio completo del sistema
sudo reboot
```

### **Si nada funciona:**
```bash
# Usar solo modo simulación (sin robot real)
python2 adaptive_walk_lightgbm_nao.py
# Seleccionar "y" para continuar en simulación
```

## 📊 **Próximos pasos recomendados**

1. **Copiar archivos actualizados al NAO**
2. **Ejecutar test de diagnóstico**
3. **Probar adaptive walk (debería funcionar en simulación)**
4. **Si hay problemas de conexión, seguir troubleshooting**
5. **Una vez solucionado, probar con robot real**

## 💡 **Para desarrollo/testing**

El modo simulación te permite:
- ✅ Probar la lógica del adaptive walk
- ✅ Verificar predicciones de LightGBM
- ✅ Debuggear sin riesgo al robot
- ✅ Desarrollar nuevas funciones

**¡El código actualizado debería resolver tu problema inmediatamente!**
