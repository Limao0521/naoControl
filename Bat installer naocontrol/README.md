# Instalador NAO Control

Instalador automatizado para el sistema NaoControl en robots NAO. Este script batch facilita la instalación completa del sistema de control remoto en robots NAO de forma automática y segura.

## 📋 Descripción

El `installer_nao_control.bat` es un instalador automatizado que:

- ✅ Verifica la conectividad con el robot NAO
- ✅ Transfiere automáticamente todos los archivos necesarios
- ✅ Configura el sistema para proceder al inicio manual
- ✅ Reinicia el robot para aplicar los cambios
- ✅ Proporciona instrucciones para un primer inicio

## 🚀 Requisitos Previos

### Hardware
- Robot NAO encendido y funcional
- Equipo Windows con acceso a red (el script bat es solo compatible con Windows OS)

### Red
- Robot NAO y equipo Windows en la misma red
- Conectividad SSH habilitada en el robot (habilitada por defecto)

### Credenciales
- Usuario del robot NAO (generalmente `nao`)
- Contraseña del usuario NAO
- Contraseña de root del robot NAO (generalmente `root`)

### Archivos Necesarios
- `payload/` - Carpeta con archivos del sistema NaoControl
- `rc.local` - Archivo de configuración de inicio automático

## 📁 Estructura de Archivos Requerida para la correcta instalacion

```
Bat installer naocontrol/
├── installer_nao_control.bat    # Instalador principal
├── rc.local                     # Configuración de inicio
├── README.md                    # Esta documentación
└── payload/                     # Archivos del sistema
    ├── scripts/                 # Scripts de control
    ├── SimpleWebSocketServer-0.1.2/  # libreria del Servidor WebSocket
    └── Webs/                    # Interfaz web
```

## 🔧 Uso del Instalador

### Ejecución

1. Extraer el .zip 
2. Ejecutar el archivo `installer_nao_control.bat `
3. Seguir los pasos descritos por el instalador

### Proceso Interactivo

El instalador solicitará la siguiente información:

1. **IP del robot NAO**
   ```
   Ingrese la IP del robot NAO: ej. [172.19.32.23]
   ```

2. **Nombre de usuario**
   ```
   Ingrese el nombre de usuario: ej. [nao]
   ```

3. **Contraseñas** (se solicitan durante el proceso de instalacion):
   - Contraseña del usuario NAO (para conexiones SSH/SCP)
   - Contraseña de root (para operaciones administrativas)

### Fases de Instalación

#### **[1/5] Verificación de Conectividad**
- Prueba de conectividad de red con el robot NAO
- Validación de que el robot está encendido y accesible

#### **[2/5] Verificación SSH**
- Prueba de conexión SSH con credenciales del usuario
- Validación de acceso remoto al robot

#### **[3/5] Transferencia de Payload**
- Copia de todos los archivos del directorio `payload/`
- Destino: `/data/home/nao/` en el robot NAO

#### **[4/5] Configuración del Sistema**
- Transferencia del archivo `rc.local`
- Actualización de `/data/rc.local` con permisos de root
- Configuración de inicio automático

#### **[5/5] Reinicio del Robot**
- Reinicio automático del robot NAO
- Aplicación de todos los cambios realizados

## 💡 Mensajes de Autenticación

El instalador proporciona mensajes claros sobre cuándo necesita cada contraseña:

### Contraseña del Usuario NAO
```
Por favor ingrese la contraseña del usuario nao:
```
*Se solicita para conexiones SSH y transferencias SCP*

### Contraseña de Root
```
Por favor ingrese la contraseña del usuario nao, luego cuando aparezca "Password:" ingrese la contraseña de root:
```
*Se solicita para operaciones administrativas (su)*

## ⚠️ Solución de Problemas

### Error: No se encuentra la carpeta 'payload'
**Causa**: Archivos faltantes
**Solución**: Verificar que existe la carpeta `payload/` en el mismo directorio del instalador

### Error: No se puede conectar al robot NAO
**Causas posibles**:
- Robot NAO apagado
- IP incorrecta
- Problemas de red

**Soluciones**:
- Verificar que el robot esté encendido
- Comprobar la IP correcta del robot
- Asegurar que ambos dispositivos estén en la misma red

### Error: No se puede conectar por SSH
**Causas posibles**:
- Credenciales incorrectas
- SSH deshabilitado en el robot
- Problemas de conectividad

**Soluciones**:
- Verificar usuario y contraseña
- Comprobar configuración SSH del robot
- Probar conexión manual con SSH

### Error: No se pudo actualizar rc.local
**Causas posibles**:
- Contraseña de root incorrecta
- Permisos insuficientes

**Soluciones**:
- Verificar contraseña de root
- Asegurar acceso administrativo al robot

## 🔄 Proceso de Desinstalación

Para revertir los cambios (manual):

1. **Conectar por SSH** al robot NAO
2. **Eliminar archivos** instalados:
   ```bash
   sudo rm -rf /data/home/nao/scripts
   sudo rm -rf /data/home/nao/SimpleWebSocketServer-0.1.2
   sudo rm -rf /data/home/nao/Webs
   ```
3. **Restaurar rc.local** original si es necesario



## 🔧 Características Técnicas

### Comandos Utilizados
- `ping` - Verificación de conectividad
- `ssh` - Conexión remota y ejecución de comandos
- `scp` - Transferencia segura de archivos
- `su` - Escalación de privilegios

### Configuraciones SSH
- `ConnectTimeout=10` - Timeout de conexión
- `StrictHostKeyChecking=no` - Omitir verificación de host keys

### Directorios de Destino
- **Payload**: `/data/home/nao/`
- **Configuración**: `/data/rc.local`

## 📝 Notas Importantes

- ⚠️ **Backup**: Se recomienda hacer respaldo del `rc.local` original antes de la instalación
- 🔄 **Reinicio**: El robot se reinicia automáticamente al finalizar
- 🔐 **Seguridad**: Las variables de contraseña se limpian al finalizar el script
- 📂 **Archivos temporales**: Se crean y limpian automáticamente durante la instalación

---

## 👨‍💻 Autoría

**Andrés Azcona**
*Estudiante de Ingeniería Informática | Semillero de Robótica Aplicada*
Universidad de La Sabana
---

*Instalador NAO Control v1.0 - Automatización de Instalación para Robots NAO*
