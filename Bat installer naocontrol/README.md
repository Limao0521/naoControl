# Instalador Nao Control

## Requisitos Previos

Antes de ejecutar el instalador, asegúrese de tener SSH habilitado en su sistema Windows:

1. **Cliente OpenSSH** - Para las conexiones SSH y transferencia de archivos (SCP)
   - En Windows 10/11 viene incluido por defecto
   - Si no funciona, habilítelo en:
     - Configuración → Aplicaciones → Características opcionales
     - Busque "Cliente OpenSSH" e instálelo
     - Reinicie el símbolo del sistema

2. **Verificar instalación**:
   - Abra un símbolo del sistema (cmd)
   - Escriba `ssh -V` y presione Enter
   - Escriba `scp` y presione Enter
   - Si ambos comandos responden, está correctamente configurado

## Instrucciones de Uso

1. **Preparación:**
   - Coloque el instalador (`installer_nao_control.bat`) en la misma carpeta que contiene:
     - Carpeta `payload/` (con todos los scripts)
     - Archivo `rc.local`

2. **Configuración del Robot NAO:**
   - Asegúrese de que el robot NAO esté encendido
   - Verifique que su computadora y el robot estén en la misma red
   - Anote la IP del robot NAO

3. **Ejecución:**
   - Haga clic derecho en `installer_nao_control.bat`
   - Seleccione "Ejecutar como administrador"
   - Siga las instrucciones en pantalla:
     - Ingrese la IP del robot NAO
     - Ingrese el nombre de usuario del robot NAO
     - Ingrese la contraseña del usuario
     - Ingrese la contraseña del usuario root (para operaciones que requieren permisos elevados)

## ¿Qué hace el instalador?

El instalador automáticamente:

1. ✅ Verifica la conectividad con el robot NAO
2. ✅ Prueba la conexión SSH con las credenciales del usuario proporcionadas
3. ✅ Crea los directorios necesarios en el robot (`/data/home/nao`) usando permisos de root
4. ✅ Transfiere todos los archivos de la carpeta `payload/` al robot
5. ✅ Reemplaza el archivo `rc.local` existente con la nueva versión usando permisos de root
6. ✅ Establece los permisos correctos para `rc.local`
7. ✅ Reinicia el robot para aplicar los cambios usando permisos de root

## Estructura de Archivos Requerida

```
📁 Carpeta del Instalador/
├── installer_nao_control.bat
├── rc.local
└── 📁 payload/
    ├── 📁 scripts/
    │   ├── control_server.py
    │   ├── launcher.py
    │   └── video_stream.py
    ├── 📁 SimpleWebSocketServer-0.1.2/
    │   └── ...
    └── 📁 Webs/
        └── 📁 ControllerWebServer/
            └── ...
```

## Solución de Problemas

### Error: "No se puede conectar al robot NAO"
- Verifique que el robot esté encendido
- Confirme que la IP sea correcta
- Asegúrese de estar en la misma red

### Error: "No se puede conectar por SSH"
- Verifique que el nombre de usuario y contraseña sean correctos
- Asegúrese de que SSH esté habilitado en el robot

### Error: "No se pudieron crear directorios o transferir archivos"
- Verifique que la contraseña del usuario root sea correcta
- Asegúrese de que el usuario root tenga permisos para realizar las operaciones

### Error: "SSH no está disponible"
- Habilite Cliente OpenSSH en Windows 10/11:
  - Configuración → Aplicaciones → Características opcionales
  - Instale "Cliente OpenSSH"
- Reinicie el símbolo del sistema

### Error: "plink no se reconoce como comando"
- Ya no es necesario PuTTY, el instalador usa SSH nativo de Windows
- Si ve este error, use la versión actualizada del instalador

## Notas Importantes

- ⚠️ El instalador requiere tanto las credenciales del usuario como las del usuario root
- ⚠️ Las operaciones que requieren permisos elevados se ejecutan usando `su` con la contraseña de root
- ⚠️ El instalador reemplazará completamente el archivo `rc.local` existente
- ⚠️ El robot se reiniciará automáticamente al final de la instalación
- ⚠️ Los servicios se iniciarán automáticamente después del reinicio
- ✅ El proceso es completamente automatizado y no requiere intervención manual

## Verificación Post-Instalación

Después de la instalación y reinicio del robot:

1. Los archivos estarán ubicados en `/data/home/nao/`
2. El servicio se iniciará automáticamente mediante `rc.local`
3. Puede verificar los logs en `/home/nao/launcher.log` y `/home/nao/rc.local.log`
