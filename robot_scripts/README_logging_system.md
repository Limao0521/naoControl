# Sistema de Logging CSV y Reentrenamiento

Este documento explica el sistema de logging CSV integrado en `adaptive_walk_randomforest.py` y las herramientas de análisis y reentrenamiento.

## Qué se registra

El sistema registra automáticamente en CSV:

- **Timestamp**: Marca temporal Unix y formato legible
- **Features**: Los 20 valores de sensores (accel_x, gyro_y, lfoot_fl, etc.)
- **Predicciones normalizadas**: Valores 0-1 que predice el modelo (pred_norm_*)
- **Parámetros aplicados**: Valores reales enviados al robot (applied_*)
- **Success**: Si la predicción fue exitosa o falló
- **Inference time**: Tiempo de inferencia en milisegundos

## Estructura de archivos CSV

```
logs/adaptive_data_YYYYMMDD_HHMMSS.csv
```

Ejemplo de headers:
```
timestamp,datetime,feat_accel_x,feat_accel_y,...,pred_norm_StepHeight,...,applied_StepHeight,...,success,inference_time_ms
```

## Uso del sistema

### 1. Ejecutar con logging CSV (por defecto habilitado)

```bash
# En el NAO
python adaptive_walk_randomforest.py --models-dir /home/nao/models --log-dir /home/nao/logs --log-level info

# Deshabilitar CSV si no se desea
python adaptive_walk_randomforest.py --disable-csv --models-dir /home/nao/models
```

### 2. Analizar logs recolectados

```bash
# Generar estadísticas y gráficos
python analyze_logs.py --log-dir logs --output-dir analysis

# Salida:
# analysis/statistics.txt       - Estadísticas descriptivas
# analysis/time_series.png      - Evolución temporal
# analysis/distributions.png    - Histogramas de parámetros
# analysis/correlations.png     - Matriz correlaciones
```

### 3. Reentrenar modelos con nuevos datos

```bash
# Reentrenar usando parámetros aplicados como target
python retrain_from_logs.py --log-dir logs --output-dir models_retrained --use-applied

# Usar predicciones normalizadas como target (modelo auto-supervisado)
python retrain_from_logs.py --log-dir logs --output-dir models_retrained

# Configurar hiperparámetros
python retrain_from_logs.py --log-dir logs --output-dir models_retrained --n-estimators 200 --max-depth 15
```

### 4. Exportar modelos reentrenados a NPZ

```bash
# Exportar los nuevos modelos para el NAO
python tools/export_rf_to_npz.py --models-dir models_retrained --scaler models_retrained/feature_scaler.pkl --out-dir models_retrained_npz
```

### 5. Desplegar modelos actualizados

```bash
# Copiar al NAO
scp models_retrained_npz/*.npz nao@<NAO_IP>:/home/nao/models_v2/

# En el NAO, usar nuevos modelos
python adaptive_walk_randomforest.py --models-dir /home/nao/models_v2 --log-dir /home/nao/logs_v2
```

## Estrategias de reentrenamiento

### Estrategia 1: Supervisión por parámetros aplicados
- Usar `--use-applied` en `retrain_from_logs.py`
- El modelo aprende la relación: features → parámetros aplicados
- Útil si los parámetros aplicados son "correctos" (evaluados por performance)

### Estrategia 2: Auto-supervisión
- No usar `--use-applied` (por defecto)
- El modelo aprende: features → predicciones normalizadas
- Refuerza patrones existentes, útil para estabilizar

### Estrategia 3: Incremental
- Combinar datos originales + nuevos logs
- Copiar CSVs de entrenamiento original a `logs/` y usar `retrain_from_logs.py`

## Métricas de evaluación

El reentrenamiento reporta:
- **MSE**: Error cuadrático medio
- **MAE**: Error absoluto medio  
- **R²**: Coeficiente de determinación
- **N train/test**: Tamaños de conjuntos

Ejemplo de salida:
```
Modelo: StepHeight
  MSE: 0.000124
  MAE: 0.008932
  R²:  0.8745
  Entrenamiento: 1204 muestras
  Test: 301 muestras
```

## Mejores prácticas

1. **Logging continuo**: Mantener CSV habilitado para recopilar datos de operación real
2. **Análisis periódico**: Ejecutar `analyze_logs.py` semanalmente para detectar patrones
3. **Reentrenamiento iterativo**: Cada X horas de operación, reentrenar y evaluar métricas
4. **Validación**: Comparar performance antes/después de desplegar modelos reentrenados
5. **Backup**: Guardar modelos anteriores antes de actualizar

## Troubleshooting

### CSV no se crea
- Verificar permisos de escritura en `--log-dir`
- Revisar logs: "CSV logging iniciado" debe aparecer

### Pocos datos para reentrenar
- Aumentar tiempo de recolección
- Verificar `success=True` en CSV (filtrar errores de inferencia)
- Reducir frecuencia de muestreo si hay demasiados datos

### Performance degradada tras reentrenamiento
- Revisar métricas R² (debe ser > 0.7)
- Verificar que features no tengan valores anómalos
- Considerar filtrar outliers antes de reentrenar

### Archivos muy grandes
- Implementar rotación de logs (por fecha/tamaño)
- Comprimir CSVs antiguos
- Usar muestreo si hay redundancia temporal
