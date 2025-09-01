# Solución al Error: Modelos LightGBM No Encontrados

## 🚨 Problema Actual
```
[ERROR] Scaler no encontrado: models_npz_automl/feature_scaler.npz
AttributeError: AdaptiveWalkLightGBM instance has no attribute '_load_golden_parameters'
```

## ✅ Soluciones

### 1. Actualizar el código (YA CORREGIDO)
El archivo `adaptive_walk_lightgbm_nao.py` ya fue actualizado para:
- ✅ Agregar método `_load_golden_parameters()` faltante
- ✅ Manejo robusto cuando no hay modelos
- ✅ Modo simulación cuando faltan archivos
- ✅ Compatibilidad total con Python 2.7

### 2. Copiar modelos al NAO

#### Opción A: Script Automático (Windows)
```powershell
# En tu PC (PowerShell)
cd "c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\robot_scripts"
.\copy_models_to_nao.ps1 -NAO_IP <IP_DEL_NAO>
```

#### Opción B: Copia Manual
```bash
# Desde tu PC, copiar modelos
scp -r c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\models_npz_automl\* nao@<IP_NAO>:/home/nao/models_npz_automl/

# Verificar que se copiaron
ssh nao@<IP_NAO> "ls -la /home/nao/models_npz_automl/"
```

#### Opción C: Verificar ubicación de modelos
Los modelos deben estar en tu PC en:
```
c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\models_npz_automl\
```

Archivos requeridos:
- `feature_scaler.npz`
- `lightgbm_model_StepHeight.npz`
- `lightgbm_model_MaxStepX.npz`
- `lightgbm_model_MaxStepY.npz`
- `lightgbm_model_MaxStepTheta.npz` 
- `lightgbm_model_Frequency.npz`

### 3. Probar el código actualizado

#### En el NAO:
```bash
# Copiar archivo actualizado
scp adaptive_walk_lightgbm_nao.py nao@<IP_NAO>:/home/nao/scripts/

# Probar sin modelos (debe funcionar ahora)
ssh nao@<IP_NAO>
cd /home/nao/scripts
python2 adaptive_walk_lightgbm_nao.py
# Debería mostrar: "¿Continuar en modo simulación? (y/n):"
```

## 🧪 Tests de Verificación

### Test 1: Verificar código actualizado
```bash
# En el NAO
python2 -c "from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM; print('OK')"
```
**Resultado esperado:** `OK` (sin errores)

### Test 2: Verificar modelos (si ya los copiaste)
```bash
# En el NAO
ls -la /home/nao/models_npz_automl/
```
**Resultado esperado:** 6 archivos .npz listados

### Test 3: Test completo con modelos
```bash
# En el NAO
python2 -c "
from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
walker = AdaptiveWalkLightGBM('models_npz_automl')
print('Modelos cargados:', len(walker.models))
params = walker.predict_gait_parameters()
print('Predicción test:', params)
"
```

## 🔄 Comandos para tu situación actual

### Paso 1: Copiar archivo actualizado al NAO
```bash
# Desde tu PC
scp "c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\robot_scripts\adaptive_walk_lightgbm_nao.py" nao@<IP_NAO>:/home/nao/scripts/
```

### Paso 2: Probar código actualizado
```bash
# En el NAO
ssh nao@<IP_NAO>
cd /home/nao/scripts
python2 adaptive_walk_lightgbm_nao.py
```
**Resultado esperado:** Modo simulación (sin crashes)

### Paso 3: Copiar modelos
```bash
# Verificar que existen en tu PC
ls "c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\models_npz_automl\"

# Copiarlos al NAO
scp -r "c:\Users\limao\Desktop\U SABANA\Semillero\NaoControl\naoControl\models_npz_automl\*" nao@<IP_NAO>:/home/nao/models_npz_automl/
```

### Paso 4: Test final
```bash
# En el NAO
python2 adaptive_walk_lightgbm_nao.py
```
**Resultado esperado:** Modelos cargados exitosamente

## 📊 Debugging

Si aún hay problemas:

### Verificar directorios en NAO:
```bash
ssh nao@<IP_NAO> "find /home/nao -name '*.npz' -type f"
```

### Verificar permisos:
```bash
ssh nao@<IP_NAO> "chmod 644 /home/nao/models_npz_automl/*.npz 2>/dev/null || true"
```

### Log detallado:
```bash
# En el NAO
python2 -c "
import os
print('Directorio actual:', os.getcwd())
print('Directorio models existe:', os.path.exists('models_npz_automl'))
if os.path.exists('models_npz_automl'):
    print('Archivos en models:', os.listdir('models_npz_automl'))
"
```

¡Con estos pasos deberías resolver el problema completamente!
