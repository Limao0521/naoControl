# 📊 Monitor NAO - Datos que Captura y Su Importancia

## 🎯 **Datos Principales que Necesitas (Parámetros de Gait)**

El monitor captura estos **5 parámetros críticos** que defines como los más importantes:

### **1. MaxStepX** 📏
- **Qué es:** Máxima longitud de paso hacia adelante/atrás (metros)
- **Valores típicos:** 0.02 - 0.08 m
- **Importancia:** Controla qué tan grandes son los pasos del NAO
- **Clave ALMemory:** `Motion/Walk/MaxStepX`

### **2. MaxStepY** 📏
- **Qué es:** Máxima longitud de paso lateral (metros)
- **Valores típicos:** 0.02 - 0.05 m
- **Importancia:** Controla movimientos de lado a lado
- **Clave ALMemory:** `Motion/Walk/MaxStepY`

### **3. MaxStepTheta** 🔄
- **Qué es:** Máximo ángulo de rotación por paso (radianes)
- **Valores típicos:** 0.1 - 0.5 rad (~6-30 grados)
- **Importancia:** Controla qué tan rápido puede girar
- **Clave ALMemory:** `Motion/Walk/MaxStepTheta`

### **4. StepHeight** ⬆️
- **Qué es:** Altura que levanta los pies (metros)
- **Valores típicos:** 0.01 - 0.04 m
- **Importancia:** Controla estabilidad al caminar
- **Clave ALMemory:** `Motion/Walk/StepHeight`

### **5. Frequency** ⏱️
- **Qué es:** Frecuencia de pasos (Hz)
- **Valores típicos:** 0.5 - 2.0 Hz
- **Importancia:** Velocidad del ciclo de caminata
- **Clave ALMemory:** `Motion/Walk/Frequency`

## 🔧 **Datos de Sensores (Para Análisis de Calidad)**

### **Sensores de Fuerza (FSR)**
- **FSR_Left:** Peso en pie izquierdo (kg)
- **FSR_Right:** Peso en pie derecho (kg)  
- **FSR_Total:** Peso total detectado (kg)
- **Uso:** Detectar estabilidad y balance

### **Acelerómetros (IMU)**
- **AccX, AccY, AccZ:** Aceleración en 3 ejes (m/s²)
- **Uso:** Detectar movimientos bruscos, caídas
- **Indicador:** Valores estables = caminata suave

### **Giroscopios**
- **GyroX, GyroY:** Velocidad angular (rad/s)
- **Uso:** Detectar rotaciones no deseadas
- **Indicador:** Valores bajos = caminata estable

### **Ángulos del Cuerpo**
- **AngleX, AngleY:** Inclinación del cuerpo (radianes)
- **Uso:** Detectar pérdida de balance
- **Indicador:** Cerca de 0 = postura correcta

## 📋 **Estado del Sistema**

### **Walking** 🏃
- **Qué es:** Boolean indicando si está caminando
- **Valores:** 0 (parado) / 1 (caminando)
- **Uso:** Saber cuándo se aplican los parámetros

## 📁 **Archivo CSV Generado**

### **Ubicación en el NAO:**
```
/home/nao/scripts/gait_params_log.csv
```

### **Columnas del CSV:**
```csv
timestamp,MaxStepX,MaxStepY,MaxStepTheta,StepHeight,Frequency,Walking,FSR_Left,FSR_Right,FSR_Total,AccX,AccY,AccZ,GyroX,GyroY,AngleX,AngleY
```

### **Ejemplo de fila:**
```csv
2025-09-01 14:30:25,0.04,0.03,0.2,0.02,1.0,1,2.1,2.3,4.4,0.001,0.002,-9.8,0.01,0.01,0.05,0.06
```

## 🎯 **Análisis de "Caminata Buena"**

### **Indicadores de caminata estable:**

#### **📏 Parámetros Balanceados:**
- `MaxStepX`: Entre 0.03-0.06 m
- `MaxStepY`: Entre 0.02-0.04 m  
- `StepHeight`: Entre 0.015-0.025 m
- `Frequency`: Entre 0.8-1.5 Hz

#### **⚖️ Balance Correcto:**
- `FSR_Left` ≈ `FSR_Right` (diferencia < 20%)
- `FSR_Total` estable (sin oscilaciones grandes)

#### **🎯 Estabilidad:**
- `AccX`, `AccY` < 2.0 m/s²
- `GyroX`, `GyroY` < 0.5 rad/s
- `AngleX`, `AngleY` < 0.1 rad (≈ 6°)

## 🚀 **Cómo Usar en el NAO**

### **1. Copiar al NAO:**
```bash
scp monitor_live_gait_params_local.py nao@IP_NAO:/home/nao/scripts/
```

### **2. Ejecutar en el NAO:**
```bash
ssh nao@IP_NAO
cd /home/nao/scripts
python monitor_live_gait_params_local.py
```

### **3. Obtener el CSV:**
```bash
scp nao@IP_NAO:/home/nao/scripts/gait_params_log.csv ./datos_nao.csv
```

## 📈 **Análisis Recomendado**

### **Para entrenar modelos:**
1. **Ejecutar monitor mientras NAO camina bien**
2. **Capturar 100+ muestras de cada configuración**
3. **Filtrar filas donde `Walking=1`**
4. **Analizar correlaciones entre parámetros y estabilidad**

### **Filtros de calidad:**
```python
# Datos de caminata estable
good_walk = df[
    (df['Walking'] == 1) &
    (df['FSR_Total'] > 3.0) &
    (df['AccX'].abs() < 2.0) &
    (df['AccY'].abs() < 2.0) &
    (df['AngleX'].abs() < 0.1) &
    (df['AngleY'].abs() < 0.1)
]
```

## ✅ **Verificación del Sistema**

### **El monitor debe mostrar:**
- ✅ Conexión a ALMemory y ALMotion
- ✅ Parámetros de gait en tiempo real
- ✅ Datos de sensores actualizándose
- ✅ Archivo CSV siendo generado
- ✅ Sin errores de conexión

### **Si hay problemas:**
- ❌ **"Error conectando proxies"** → Verificar NAOqi está corriendo
- ❌ **"N/A" en parámetros** → Robot no inicializado
- ❌ **"Walking=0" siempre** → Robot no está caminando

**¡El monitor está optimizado para Python 2.7 del NAO y captura exactamente los datos que necesitas!** 🤖✅
