@echo off
title Instalador Nao Control
color 0A
echo.
echo ========================================
echo    INSTALADOR NAO CONTROL
echo ========================================
echo.

REM Solicitar IP del robot NAO
:ask_ip
set /p NAO_IP="Ingrese la IP del robot NAO: "
if "%NAO_IP%"=="" (
    echo Error: Debe ingresar una IP valida.
    goto ask_ip
)

REM Validacion basica - solo verificar que contenga puntos
echo %NAO_IP% | findstr "." >nul
if errorlevel 1 (
    echo Error: Formato de IP invalido. Ejemplo: 192.168.1.100
    goto ask_ip
)

echo.
echo IP del robot NAO: %NAO_IP%

REM Solicitar usuario
:ask_user
set /p NAO_USER="Ingrese el nombre de usuario: "
if "%NAO_USER%"=="" (
    echo Error: Debe ingresar un nombre de usuario.
    goto ask_user
)

REM Solicitar contraseña del usuario
:ask_password
set /p NAO_PASSWORD="Ingrese la clave del usuario %NAO_USER%: "
if "%NAO_PASSWORD%"=="" (
    echo Error: Debe ingresar una contraseña.
    goto ask_password
)

echo.
echo Usuario: %NAO_USER%
echo Nota: Se solicitara la contraseña de root para operaciones que requieran permisos elevados

echo.
echo ========================================
echo    INICIANDO INSTALACION
echo ========================================
echo.

REM Verificar que existan los archivos necesarios
if not exist "payload\" (
    echo Error: No se encuentra la carpeta 'payload'
    pause
    exit /b 1
)

if not exist "rc.local" (
    echo Error: No se encuentra el archivo 'rc.local'
    pause
    exit /b 1
)

REM Verificar conectividad con el robot NAO
echo [1/5] Verificando conectividad con el robot NAO...
ping -n 1 %NAO_IP% >nul 2>&1
if errorlevel 1 (
    echo Error: No se puede conectar al robot NAO en la IP %NAO_IP%
    echo Verifique que:
    echo - El robot este encendido
    echo - La IP sea correcta
    echo - Esten en la misma red
    pause
    exit /b 1
)
echo Conectividad OK

REM Crear directorio temporal para scripts
mkdir temp_install 2>nul

REM Verificar conexion SSH
echo [2/5] Verificando conexion SSH...
ssh -t -o ConnectTimeout=10 -o StrictHostKeyChecking=no %NAO_USER%@%NAO_IP% "echo 'Conexion SSH exitosa'"
if errorlevel 1 (
    echo Error: No se puede conectar por SSH
    echo Verifique el usuario, contraseña y conectividad
    rmdir /s /q temp_install
    pause
    exit /b 1
)
echo Conexion SSH OK

REM Transferir contenido de la carpeta payload directamente
echo [3/5] Transfiriendo archivos de payload...
scp -r -o ConnectTimeout=30 -o StrictHostKeyChecking=no payload\* %NAO_USER%@%NAO_IP%:/data/home/nao/
if errorlevel 1 (
    echo Error: No se pudieron transferir los archivos de payload
    rmdir /s /q temp_install
    pause
    exit /b 1
)
echo Archivos de payload transferidos

REM Eliminar rc.local existente y transferir el nuevo
echo [4/5] Actualizando rc.local...
scp -o ConnectTimeout=30 -o StrictHostKeyChecking=no rc.local %NAO_USER%@%NAO_IP%:/home/%NAO_USER%/temp_rc.local
if errorlevel 1 (
    echo Error: No se pudo transferir rc.local
    rmdir /s /q temp_install
    pause
    exit /b 1
)

REM Reemplazar rc.local en /data con permisos de root usando su
echo IMPORTANTE: A continuacion se solicitara la contraseña de root para actualizar rc.local
ssh -t -o ConnectTimeout=10 -o StrictHostKeyChecking=no %NAO_USER%@%NAO_IP% "su -c 'cp /home/%NAO_USER%/temp_rc.local /data/rc.local && chmod +x /data/rc.local && rm /home/%NAO_USER%/temp_rc.local'"
if errorlevel 1 (
    echo Error: No se pudo actualizar rc.local
    rmdir /s /q temp_install
    pause
    exit /b 1
)
echo rc.local actualizado

REM Reiniciar el robot
echo [5/5] Reiniciando robot NAO...
echo IMPORTANTE: A continuacion se solicitara la contraseña de root para reiniciar el robot
ssh -t -o ConnectTimeout=10 -o StrictHostKeyChecking=no %NAO_USER%@%NAO_IP% "su -c 'reboot'" 2>nul
if errorlevel 1 (
    echo Nota: El robot se esta reiniciando (es normal que aparezca un error aqui)
)

REM Limpiar archivos temporales
rmdir /s /q temp_install

echo.
echo ========================================
echo    INSTALACION COMPLETADA
echo ========================================
echo.
echo El robot NAO se esta reiniciando...
echo Los servicios de Nao Control se iniciaran automaticamente.
echo.
echo Detalles de la instalacion:
echo - IP del robot: %NAO_IP%
echo - Usuario: %NAO_USER%
echo - Archivos payload transferidos a: /data/home/nao/
echo - rc.local actualizado en: /data/rc.local
echo - Robot reiniciado para aplicar cambios
echo.
echo Presione cualquier tecla para finalizar...
pause >nul

REM Limpiar variables por seguridad
set NAO_IP=
set NAO_USER=
set NAO_PASSWORD=
