# Sistema de Caminata Adaptativa con XGBoost para NAO

Sistema de control adaptativo de marcha para robot NAO basado en modelos XGBoost que predice parámetros óptimos de caminata usando datos de sensores en tiempo real.

## � Sistema XGBoost

### Archivos del Sistema XGBoost

1. **`adaptive_walk_xgboost.py`** - Sistema principal de control adaptativo
2. **`train_xgboost_gait.py`** - Script de entrenamiento de modelos XGBoost
3. **`xgboost_replay_eval.py`** - Evaluación offline de modelos entrenados
4. **`data_logger_xgboost.py`** - Recolección de datos para entrenamiento

## 🚀 Inicio Rápido

### 1. Entrenar Modelos XGBoost

```bash
# Entrenar con optimización de hiperparámetros
python3 train_xgboost_gait.py --data "/path/to/datasets/*.csv" --out-dir models --optimize

# Entrenar básico (más rápido)
python3 train_xgboost_gait.py --data "dataset1.csv" "dataset2.csv" --out-dir models
```

### 2. Evaluar Modelos

```bash
# Evaluación offline
python2 xgboost_replay_eval.py --csv "/path/to/test/*.csv" --model-dir models

# Evaluación con aplicación al robot (¡cuidado!)
python2 xgboost_replay_eval.py --csv "test_data.csv" --apply --nao-ip 192.168.1.100
```

### 3. Ejecutar Sistema en Producción

```bash
# Modo de prueba (solo predicción)
python2 adaptive_walk_xgboost.py --test

# Modo producción (aplicar al robot)
python2 adaptive_walk_xgboost.py --nao-ip 192.168.1.100
```

## 🎯 Características Principales

✅ **Alta precisión** en predicción de parámetros de marcha  
✅ **Robustez** ante ruido y valores faltantes en sensores  
✅ **Interpretabilidad** mediante feature importance  
✅ **Eficiencia computacional** optimizada para tiempo real  
✅ **Flexibilidad** en configuración y ajuste de hiperparámetros  
✅ **Filtros avanzados** de suavizado y estabilización

## 🏗️ Arquitectura del Sistema

### Entrada (Features):
- **Sensores inerciales**: accel_x/y/z, gyro_x/y/z, angle_x/y
- **Sensores de presión**: lfoot_fl/fr/rl/rr, rfoot_fl/fr/rl/rr  
- **Velocidades**: vx, vy, wz, vtotal

### Salida (Parámetros de marcha):
- **StepHeight**: Altura del paso (0.01-0.05 m)
- **MaxStepX**: Paso máximo adelante/atrás (0.02-0.08 m)
- **MaxStepY**: Paso máximo lateral (0.08-0.20 m)
- **MaxStepTheta**: Rotación máxima (0.10-0.50 rad)
- **Frequency**: Frecuencia de marcha (0.50-1.20 Hz)

### Pipeline de Procesamiento:
1. **Lectura de sensores** → Vector de 20 features
2. **Normalización** → StandardScaler o normalización por muestra
3. **Predicción XGBoost** → 5 modelos independientes
4. **Desnormalización** → Valores en rangos físicos
5. **Filtros de suavizado** → EMA, deadband, rate limiting
6. **Aplicación al robot** → NAOqi setMoveConfig

## 📁 Estructura de Archivos

```
robot_scripts/
├── adaptive_walk_xgboost.py      # Sistema principal XGBoost
├── train_xgboost_gait.py         # Entrenamiento
├── xgboost_replay_eval.py        # Evaluación offline
├── data_logger_xgboost.py        # Recolección de datos
├── models/                       # Modelos entrenados
│   ├── xgboost_model.json       # Información de modelos
│   ├── model_StepHeight.json    # Modelo individual
│   ├── model_MaxStepX.json      # ...etc
│   ├── feature_scaler.pkl       # Escalador de features
│   └── training_report.txt      # Métricas de entrenamiento
└── README_XGBoost.md            # Esta documentación
```

## 🔧 Instalación

### Requisitos PC (entrenamiento):
```bash
pip install xgboost pandas numpy scikit-learn
```

### Requisitos Robot NAO (producción):
```bash
# En el robot NAO (Python 2.7)
pip install --user xgboost==0.90  # Versión compatible
```

## 📈 Métricas y Evaluación

### Entrenamiento:
- **MSE/MAE** en conjunto de entrenamiento y validación
- **R²** para calidad del ajuste
- **Overfitting ratio** (MSE_test/MSE_train)

### Evaluación Offline:
- **Errores normalizados** [0,1] para comparación directa
- **Errores físicos** en unidades reales (metros, radianes, Hz)
- **Tasa de éxito** en predicciones

### Ejemplo de Salida:
```
--- Errores en Unidades Físicas ---
StepHeight     MAE=0.002140m  Med=0.001823m  Max=0.008901m  n=1250
MaxStepX       MAE=0.003421m  Med=0.002901m  Max=0.012045m  n=1250
MaxStepY       MAE=0.005234m  Med=0.004123m  Max=0.018902m  n=1250
MaxStepTheta   MAE=0.001892rad Med=0.001456rad Max=0.008234rad n=1250
Frequency      MAE=0.012340Hz  Med=0.009876Hz  Max=0.045123Hz  n=1250

Calidad estimada del modelo: BUENA
```

## 🛠️ Personalización

### Ajuste de Hiperparámetros:
```python
# En train_xgboost_gait.py, modificar param_grid:
param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [4, 6, 8],
    'learning_rate': [0.05, 0.1, 0.15],
    # ... más parámetros
}
```

### Configuración de Filtros:
```python
# En adaptive_walk_xgboost.py, modificar CFG:
CFG = {
    'update_period_s': 0.8,    # Frecuencia de actualización
    'ema_alpha': 0.2,          # Suavizado exponencial
    'deadband': {...},         # Zonas muertas
    'rate_limit': {...},       # Limitadores de velocidad
}
```

## 🐛 Resolución de Problemas

### Error: "XGBoost no disponible"
```bash
# Instalar XGBoost compatible con Python 2.7
pip install --user xgboost==0.90
```

### Error: "No se encontraron modelos"
```bash
# Verificar rutas de modelos
ls ~/.local/share/adaptive_gait/
# Debe contener: xgboost_model.json, model_*.json, feature_scaler.pkl
```

### Baja precisión del modelo
1. **Más datos**: Recolectar más sesiones de entrenamiento
2. **Features**: Verificar calidad de sensores
3. **Hiperparámetros**: Usar `--optimize` en entrenamiento
4. **Rangos**: Verificar que PARAM_RANGES sean correctos

## 📞 Soporte

Para problemas específicos:
1. Revisar logs de error detallados con `--verbose`
2. Verificar `training_report.txt` para métricas de calidad
3. Usar herramientas de evaluación offline para benchmarking

---

*Sistema desarrollado para robots NAO con Python 2.7 y NAOqi. Optimizado para control adaptativo de marcha en tiempo real.*
