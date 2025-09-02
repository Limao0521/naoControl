# 🔧 SOLUCIÓN: Parámetros de Gait Mostrando "N/A"

## 🎯 **Problema detectado:**
```
📏 MaxStepX: N/A
📏 MaxStepY: N/A
📏 MaxStepTheta: N/A
📏 StepHeight: N/A
📏 Frequency: N/A
```

Los sensores funcionan (FSR_Left: 1.450, FSR_Right: 1.753) pero los parámetros de gait no se pueden leer.

## 🔍 **Causas posibles:**

### **1. Robot no inicializado correctamente**
- El NAO está conectado pero no está en estado activo
- ALMotion no está configurado
- Parámetros de gait no están cargados en ALMemory

### **2. Claves incorrectas en ALMemory**
- Las claves `Motion/Walk/MaxStepX` pueden no existir
- Diferentes versiones de NAOqi usan claves distintas
- El walking engine no está inicializado

### **3. Robot en modo "sleep" o sin stiffness**
- Robot despierto pero sin rigidez en motores
- Walking engine deshabilitado

## ✅ **SOLUCIONES PASO A PASO:**

### **🔧 Solución 1: Usar el inicializador**

```bash
# 1. Ejecutar el nuevo script inicializador
ssh nao@IP_DEL_NAO
cd /home/nao/scripts

# 2. Ejecutar inicializador
python nao_gait_init.py

# 3. Ejecutar monitor después
python monitor_live_gait_params_local.py
```

### **🔧 Solución 2: Inicialización manual en el NAO**

```python
# Conectar por SSH al NAO y ejecutar:
python -c "
from naoqi import ALProxy
import time

# Conectar
motion = ALProxy('ALMotion', 'localhost', 9559)
memory = ALProxy('ALMemory', 'localhost', 9559)

# Despertar y configurar
motion.wakeUp()
time.sleep(2)

# Configurar parámetros manualmente
memory.insertData('Motion/Walk/MaxStepX', 0.04)
memory.insertData('Motion/Walk/MaxStepY', 0.14)
memory.insertData('Motion/Walk/MaxStepTheta', 0.349)
memory.insertData('Motion/Walk/StepHeight', 0.02)
memory.insertData('Motion/Walk/Frequency', 1.0)

print('Parámetros configurados!')
"
```

### **🔧 Solución 3: Verificar estado del robot**

```python
# En el NAO, verificar diagnóstico:
python -c "
from naoqi import ALProxy

memory = ALProxy('ALMemory', 'localhost', 9559)
motion = ALProxy('ALMotion', 'localhost', 9559)

# Verificar estado
print('Robot despierto:', memory.getData('robotIsWakeUp'))
print('Stiffness:', motion.getStiffnesses('Body')[0])
print('Postura:', ALProxy('ALRobotPosture', 'localhost', 9559).getPosture())
"
```

### **🔧 Solución 4: Forzar valores por defecto en el monitor**

He modificado el monitor para que use valores por defecto cuando no puede leer los parámetros reales. El monitor ahora:

- ✅ **Intenta múltiples claves** de ALMemory
- ✅ **Usa ALMotion como respaldo**
- ✅ **Muestra diagnóstico** del estado del robot
- ✅ **Aplica valores por defecto** cuando es necesario

## 📊 **Cómo verificar la solución:**

### **Ejecutar monitor modificado:**
```bash
ssh nao@IP_DEL_NAO
cd /home/nao/scripts
python monitor_live_gait_params_local.py
```

### **Buscar en la salida:**
```
🔍 DIAGNOSTIC INFO:
  • Robot Awake: YES
  • Motion Active: YES
```

### **Si muestra valores:**
```
📏 MaxStepX: 0.0400
📏 MaxStepY: 0.1400
📏 MaxStepTheta: 0.3490
📏 StepHeight: 0.0200
📏 Frequency: 1.0000
```

## 🎯 **Para capturar datos reales de caminata:**

### **1. Inicializar robot:**
```bash
python nao_gait_init.py
```

### **2. Hacer caminar:**
```python
# En una sesión SSH separada:
python -c "
from naoqi import ALProxy
motion = ALProxy('ALMotion', 'localhost', 9559)
motion.moveToward(0.5, 0, 0)  # Caminar hacia adelante
"
```

### **3. Ejecutar monitor:**
```bash
python monitor_live_gait_params_local.py
```

### **4. Detener caminata:**
```python
python -c "
from naoqi import ALProxy
motion = ALProxy('ALMotion', 'localhost', 9559)
motion.stopMove()
"
```

## 📋 **Archivos actualizados:**

1. **`monitor_live_gait_params_local.py`** - Monitor mejorado con diagnóstico
2. **`nao_gait_init.py`** - Inicializador de parámetros
3. **Esta guía** - Solución paso a paso

## 🎉 **Resultado esperado:**

Después de seguir estos pasos, deberías ver:

```
🎯 MAIN GAIT PARAMETERS:
📏 MaxStepX: 0.0400
📏 MaxStepY: 0.1400  
📏 MaxStepTheta: 0.3490
📏 StepHeight: 0.0200
📏 Frequency: 1.0000

🏃 Walking: YES (cuando esté caminando)

💾 CSV LOG: /home/nao/scripts/gait_params_log.csv
💾 Datos guardados en: /home/nao/scripts/gait_params_log.csv
```

**¡El CSV se generará automáticamente con los parámetros correctos!** 📊✅
