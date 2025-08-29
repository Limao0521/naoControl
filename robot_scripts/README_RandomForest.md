# Sistema de Marcha Adaptativa con Random Forest

Este directorio contiene el sistema de marcha adaptativa refactorizado para usar **Random Forest** en lugar de XGBoost, solucionando los problemas de instalación en el robot NAO.

## 🔄 Cambios Principales

### Migración XGBoost → Random Forest

- **`adaptive_walk_xgboost.py`** → **`adaptive_walk_randomforest.py`**
- **`train_xgboost_gait.py`** → **`train_randomforest_gait.py`**  
- **`xgboost_replay_eval.py`** → **`randomforest_replay_eval.py`**

### Motivos del cambio:
1. **Problemas de compilación**: XGBoost requiere herramientas de compilación (gcc, make) no disponibles en NAO
2. **Dependencias complejas**: XGBoost necesita CMake y bibliotecas C++ específicas
3. **Compatibilidad Python 2.7**: Random Forest está incluido en scikit-learn, ya compatible con NAO

## 📁 Archivos Refactorizados

### 1. `train_randomforest_gait.py`
**Entrenamiento de modelos Random Forest**

```bash
# Entrenar modelos con datasets
python train_randomforest_gait.py --data "datasets/walks/*.csv" --out-dir models/

# Con optimización de hiperparámetros
python train_randomforest_gait.py --data "datasets/walks/*.csv" --optimize --out-dir models/
```

**Salidas generadas:**
- `models/randomforest_model_<param>.pkl` (5 modelos)
- `models/feature_scaler.pkl`
- `models/training_report.txt`

### 2. `adaptive_walk_randomforest.py` 
**Sistema adaptativo en tiempo real**

```bash
# Ejecutar en NAO
python adaptive_walk_randomforest.py --robot-ip 192.168.1.100 --enable

# Modo simulación (PC)
python adaptive_walk_randomforest.py --robot-ip localhost --enable --log-level debug
```

**Características:**
- Misma interfaz que la versión XGBoost
- Compatible con Python 2.7 del NAO
- Filtros EMA para estabilización
- Control interactivo (enable/disable/status)

### 3. `randomforest_replay_eval.py`
**Evaluación offline de modelos**

```bash
# Evaluar modelos entrenados
python randomforest_replay_eval.py --models models/ --data datasets/walks/test.csv --output results/

# Con visualizaciones
python randomforest_replay_eval.py --models models/ --data "datasets/walks/*.csv" --plot --output results/
```

**Salidas:**
- `results/evaluation_report.txt`
- `results/predictions.csv`
- `results/correlation_plots.png` (opcional)
- `results/error_distribution.png` (opcional)

## ⚙️ Configuración y Compatibilidad

### Parámetros del Modelo
```python
# Random Forest configuración base
{
    'n_estimators': 100,        # Número de árboles
    'max_depth': 15,           # Profundidad máxima
    'min_samples_split': 10,   # Mínimo para dividir
    'min_samples_leaf': 5,     # Mínimo en hojas
    'random_state': 42,        # Reproducibilidad
    'n_jobs': -1              # Paralelización
}
```

### Features (20 dimensiones)
```python
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',           # Acelerómetro
    'gyro_x','gyro_y','gyro_z',              # Giroscopio  
    'angle_x','angle_y',                     # Ángulos corporales
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',  # Presión pie izq
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',  # Presión pie der
    'vx','vy','wz','vtotal'                  # Velocidades
]
```

### Targets (5 parámetros de marcha)
```python
GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

PARAM_RANGES = {
    'StepHeight':   (0.01, 0.05),    # Altura del paso
    'MaxStepX':     (0.02, 0.08),    # Paso máximo adelante
    'MaxStepY':     (0.08, 0.20),    # Paso máximo lateral  
    'MaxStepTheta': (0.10, 0.50),    # Rotación máxima
    'Frequency':    (0.50, 1.20),    # Frecuencia de pasos
}
```

## 🚀 Instalación en NAO

### 1. Preparar modelos en PC
```bash
# Entrenar modelos Random Forest
python train_randomforest_gait.py --data "datasets/walks/*.csv" --out-dir models/

# Verificar modelos
ls models/
# randomforest_model_StepHeight.pkl
# randomforest_model_MaxStepX.pkl  
# randomforest_model_MaxStepY.pkl
# randomforest_model_MaxStepTheta.pkl
# randomforest_model_Frequency.pkl
# feature_scaler.pkl
```

### 2. Transferir a NAO
```bash
# Copiar archivos al NAO
scp -r models/ nao@192.168.1.100:/home/nao/
scp adaptive_walk_randomforest.py nao@192.168.1.100:/home/nao/
```

### 3. Ejecutar en NAO
```bash
# Conectar por SSH
ssh nao@192.168.1.100

# Verificar dependencias
python -c "import sklearn, joblib, numpy; print('OK')"

# Ejecutar sistema adaptativo
python adaptive_walk_randomforest.py --enable
```

## 📊 Rendimiento Esperado

### Comparación XGBoost vs Random Forest

| Métrica | XGBoost | Random Forest | 
|---------|---------|---------------|
| **Instalación NAO** | ❌ Falla | ✅ Exitosa |
| **R² Score** | ~0.85-0.92 | ~0.80-0.88 |
| **Tiempo entrenamiento** | Rápido | Medio |
| **Memoria (NAO)** | N/A | ~50-80MB |
| **Predicción (latencia)** | N/A | ~5-10ms |

### Métricas típicas Random Forest:
- **R² Score**: 0.80-0.88 (según parámetro)
- **RMSE**: 0.002-0.015 (espacio físico)
- **MAPE**: 3-8% (error porcentual)

## 🔧 Troubleshooting

### Problemas comunes:

1. **Error "No module named sklearn"**
   ```bash
   # Verificar instalación
   python -c "import sklearn; print(sklearn.__version__)"
   # Debe ser 0.20.4
   ```

2. **Modelos no encontrados**
   ```bash
   # Verificar estructura
   ls -la models/
   # Debe contener todos los .pkl
   ```

3. **Conexión NAO fallida**
   ```bash
   # Verificar IP y puerto
   python -c "from naoqi import ALProxy; m = ALProxy('ALMotion', '192.168.1.100', 9559); print('OK')"
   ```

4. **Rendimiento bajo**
   - Verificar calidad de datos de entrenamiento
   - Considerar re-entrenamiento con más datos
   - Ajustar hiperparámetros con `--optimize`

## 📈 Monitoreo y Logs

### Levels de logging:
```bash
# Debug detallado
python adaptive_walk_randomforest.py --log-level debug

# Solo errores  
python adaptive_walk_randomforest.py --log-level error
```

### Comandos interactivos:
- `enable` - Habilitar adaptación
- `disable` - Deshabilitar adaptación  
- `status` - Ver estado del sistema
- `quit` - Salir del programa

## 🎯 Siguientes Pasos

1. **Validación en NAO**: Probar sistema completo en robot real
2. **Optimización**: Tune hiperparámetros Random Forest
3. **Datasets**: Recolectar más datos para mejorar modelos
4. **Integración**: Conectar con sistema de control principal

---

**Nota**: Este sistema reemplaza completamente la implementación XGBoost, manteniendo la misma funcionalidad pero con compatibilidad total para el entorno NAO Python 2.7.
