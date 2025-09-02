# ✅ Monitor NAO Modificado - Resumen Completo

## 🎯 **Modificaciones Realizadas**

### **1. Monitor Optimizado para NAO (`monitor_live_gait_params_local.py`)**

#### **✅ Cambios aplicados:**
- **Eliminadas dependencias externas:** Reemplazado `subprocess` por `os.popen` (compatible NAO)
- **Mejorada generación de CSV:** Guardado automático en cada actualización
- **Compatible Python 2.7:** Sin f-strings, compatible con NAO
- **Generación de CSV confiable:** Manejo de errores mejorado
- **Ubicación CSV:** `/home/nao/scripts/gait_params_log.csv`

#### **🔧 Funcionalidades:**
- ✅ **Captura los 5 parámetros críticos:** MaxStepX, MaxStepY, MaxStepTheta, StepHeight, Frequency
- ✅ **Datos de sensores:** FSR, IMU, ángulos corporales 
- ✅ **Estado de caminata:** Walking boolean
- ✅ **CSV automático:** Se guarda cada segundo
- ✅ **Compatible NAO:** Python 2.7, sin librerías externas

### **2. Scripts de Instalación**

#### **PowerShell (`install_monitor_nao.ps1`):**
```powershell
.\install_monitor_nao.ps1 192.168.1.100
```

#### **Bash (`install_monitor_nao.sh`):**
```bash
./install_monitor_nao.sh 192.168.1.100
```

#### **Funciones:**
- 📁 Crea directorio `/home/nao/scripts/`
- 📋 Copia el monitor al NAO
- 🔧 Configura permisos
- ✅ Verifica instalación
- 🚀 Opción de ejecutar inmediatamente

### **3. Analizador de Datos (`analyze_nao_gait_data.py`)**

#### **Uso:**
```bash
python analyze_nao_gait_data.py gait_params_log.csv
```

#### **Funciones:**
- 📊 **Filtra datos estables:** Solo caminata con sensores estables
- 📈 **Calcula promedios:** Parámetros óptimos de cada variable
- ⚖️ **Analiza estabilidad:** Varianza de sensores
- 💾 **Genera configuración:** Archivo `optimal_gait_params.txt`
- 📋 **Reporte completo:** Estadísticas y recomendaciones

## 📊 **Datos Capturados (Los Más Importantes)**

### **🎯 Parámetros de Gait (Los 5 críticos que pediste):**

| Parámetro | Descripción | Valores Típicos | ALMemory Key |
|-----------|-------------|-----------------|--------------|
| **MaxStepX** | Longitud paso adelante/atrás | 0.02-0.08 m | `Motion/Walk/MaxStepX` |
| **MaxStepY** | Longitud paso lateral | 0.02-0.05 m | `Motion/Walk/MaxStepY` |
| **MaxStepTheta** | Ángulo rotación por paso | 0.1-0.5 rad | `Motion/Walk/MaxStepTheta` |
| **StepHeight** | Altura levantamiento pie | 0.01-0.04 m | `Motion/Walk/StepHeight` |
| **Frequency** | Frecuencia de pasos | 0.5-2.0 Hz | `Motion/Walk/Frequency` |

### **🔧 Sensores de Calidad:**

| Sensor | Descripción | Uso |
|--------|-------------|-----|
| **FSR_Left/Right** | Peso en cada pie | Balance y estabilidad |
| **AccX/Y/Z** | Aceleración 3 ejes | Suavidad de movimiento |
| **GyroX/Y** | Velocidad angular | Estabilidad rotacional |
| **AngleX/Y** | Inclinación cuerpo | Postura correcta |
| **Walking** | Estado caminata | Cuándo aplicar parámetros |

## 🚀 **Flujo de Trabajo Completo**

### **Paso 1: Instalar en el NAO**
```bash
# Opción PowerShell
.\install_monitor_nao.ps1 192.168.1.100

# Opción Bash
./install_monitor_nao.sh 192.168.1.100
```

### **Paso 2: Ejecutar Monitor**
```bash
ssh nao@192.168.1.100
cd /home/nao/scripts
python monitor_live_gait_params_local.py
```

### **Paso 3: Recolectar Datos**
- ✅ **Hacer caminar al NAO** con diferentes configuraciones
- ✅ **Capturar 100+ muestras** de cada configuración estable
- ✅ **Dejar correr el monitor** mientras NAO camina bien

### **Paso 4: Obtener CSV**
```bash
scp nao@192.168.1.100:/home/nao/scripts/gait_params_log.csv ./datos_nao.csv
```

### **Paso 5: Analizar Datos**
```bash
python analyze_nao_gait_data.py datos_nao.csv
```

### **Paso 6: Usar Parámetros Óptimos**
- ✅ **Revisar `optimal_gait_params.txt`** generado
- ✅ **Usar valores promedio** como configuración base
- ✅ **Integrar con tu sistema** de control adaptativo

## 📋 **Estructura del CSV Generado**

```csv
timestamp,MaxStepX,MaxStepY,MaxStepTheta,StepHeight,Frequency,Walking,FSR_Left,FSR_Right,FSR_Total,AccX,AccY,AccZ,GyroX,GyroY,AngleX,AngleY
2025-09-01 14:30:25,0.04,0.03,0.2,0.02,1.0,1,2.1,2.3,4.4,0.001,0.002,-9.8,0.01,0.01,0.05,0.06
```

## 🎯 **Criterios de "Caminata Buena"**

### **Filtros automáticos del analizador:**
- ✅ **Walking = 1** (está caminando)
- ✅ **FSR_Total > 2.0** (peso detectado)
- ✅ **|AccX|, |AccY| < 3.0** (movimiento suave)
- ✅ **|AngleX|, |AngleY| < 0.15 rad** (postura estable)

### **Indicadores manuales:**
- ✅ **Balance:** FSR_Left ≈ FSR_Right (diferencia < 20%)
- ✅ **Estabilidad:** Baja varianza en sensores
- ✅ **Parámetros balanceados:** Dentro de rangos típicos

## 🔧 **Troubleshooting**

### **❌ "Error conectando proxies"**
```bash
# Verificar NAOqi
ssh nao@IP_NAO
naoqi-bin --verbose
```

### **❌ "N/A" en parámetros**
```bash
# Inicializar robot
ssh nao@IP_NAO
python -c "from naoqi import ALProxy; m=ALProxy('ALMotion','localhost',9559); m.wakeUp()"
```

### **❌ CSV vacío**
- Verificar permisos en `/home/nao/scripts/`
- Comprobar que el robot está caminando (`Walking=1`)

## ✅ **Resultado Final**

**Tienes un sistema completo para:**
1. 🤖 **Monitorear en tiempo real** los parámetros de gait del NAO
2. 📊 **Capturar automáticamente** los 5 parámetros críticos + sensores
3. 💾 **Generar CSV** con todos los datos de caminata
4. 📈 **Analizar automáticamente** para encontrar configuración óptima
5. 🎯 **Extraer parámetros** de cuando el NAO camina bien

**¡Todo optimizado para Python 2.7 del NAO y sin dependencias externas!** 🚀✅
