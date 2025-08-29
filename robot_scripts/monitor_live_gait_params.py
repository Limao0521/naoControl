#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monitor Live Gait Parameters via SSH
====================================

Script para monitorear en tiempo real los parámetros de caminata que se están
aplicando al robot NAO a través de SSH.

Muestra:
- Parámetros de gait actuales (CURRENT_GAIT)
- Parámetros aplicados (GAIT_APPLIED) 
- Velocidades de movimiento (vx, vy, wz)
- CAPS aplicados
- Estado del sistema adaptativo
- Estado de golden parameters si está activo

Uso:
    python monitor_live_gait_params.py [IP_DEL_NAO]

Ejemplo:
    python monitor_live_gait_params.py 172.19.32.26

Requerimientos:
    - SSH habilitado en el NAO
    - paramiko: pip install paramiko
    - Usuario/contraseña del NAO configurados
"""

import sys
import time
import json
import os
import threading
from datetime import datetime

try:
    import paramiko
except ImportError:
    print("Error: paramiko no está instalado")
    print("Instalar con: pip install paramiko")
    sys.exit(1)

# Configuración SSH
DEFAULT_NAO_IP = "172.19.32.26"
NAO_USERNAME = "nao"
NAO_PASSWORD = "nao"  # Cambiar si tienes otra contraseña
NAO_SCRIPTS_PATH = "/home/nao/scripts"

# Configuración de monitoreo
UPDATE_INTERVAL = 1.0  # segundos entre actualizaciones
CLEAR_SCREEN = True    # limpiar pantalla entre actualizaciones

class NAOGaitMonitor:
    def __init__(self, nao_ip):
        self.nao_ip = nao_ip
        self.ssh = None
        self.running = False
        
    def connect(self):
        """Establecer conexión SSH con el NAO"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            print("Conectando a NAO en {}...".format(self.nao_ip))
            self.ssh.connect(
                hostname=self.nao_ip,
                username=NAO_USERNAME,
                password=NAO_PASSWORD,
                timeout=10
            )
            print("✅ Conexión SSH establecida")
            return True
            
        except Exception as e:
            print("❌ Error de conexión SSH: {}".format(e))
            return False
    
    def disconnect(self):
        """Cerrar conexión SSH"""
        if self.ssh:
            self.ssh.close()
            print("🔌 Conexión SSH cerrada")
    
    def execute_command(self, command):
        """Ejecutar comando en el NAO y obtener resultado"""
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                return None, error
            return output, None
            
        except Exception as e:
            return None, str(e)
    
    def get_control_server_status(self):
        """Verificar si el control server está ejecutándose"""
        command = "ps aux | grep control_server.py | grep -v grep"
        output, error = self.execute_command(command)
        
        if output:
            return True, "Control server activo"
        else:
            return False, "Control server no encontrado"
    
    def get_current_gait_params(self):
        """Obtener parámetros de gait actuales desde ALMemory"""
        commands = [
            # Parámetros principales de gait
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"MaxStepX:\\", m.getData(\\"Motion/Walk/MaxStepX\\"))"',
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"MaxStepY:\\", m.getData(\\"Motion/Walk/MaxStepY\\"))"',
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"MaxStepTheta:\\", m.getData(\\"Motion/Walk/MaxStepTheta\\"))"',
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"StepHeight:\\", m.getData(\\"Motion/Walk/StepHeight\\"))"',
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"Frequency:\\", m.getData(\\"Motion/Walk/Frequency\\"))"',
            
            # Estado del robot
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"Moving:\\", m.getData(\\"Motion/Walk/IsEnabled\\"))"',
        ]
        
        results = {}
        for cmd in commands:
            output, error = self.execute_command(cmd)
            if output and not error:
                try:
                    parts = output.split(": ")
                    if len(parts) == 2:
                        param_name = parts[0]
                        param_value = float(parts[1])
                        results[param_name] = param_value
                except:
                    pass
        
        return results
    
    def get_golden_params_status(self):
        """Verificar estado del sistema de golden parameters"""
        # Verificar si el detector está corriendo
        command = "ps aux | grep golden_params_detector | grep -v grep"
        output, error = self.execute_command(command)
        
        if not output:
            return {"status": "inactive", "message": "Golden params detector no activo"}
        
        # Verificar archivos de estado
        status_files = [
            "/tmp/golden_params_detector.pid",
            "/tmp/golden_remote_command.json",
            "/tmp/golden_remote_response.json"
        ]
        
        results = {"status": "active", "files": {}}
        for file_path in status_files:
            cmd = "test -f {} && echo 'exists' || echo 'missing'".format(file_path)
            output, error = self.execute_command(cmd)
            results["files"][file_path] = output.strip() if output else "error"
        
        # Intentar leer el estado actual
        cmd = "cat /tmp/golden_remote_response.json 2>/dev/null || echo 'no_response'"
        output, error = self.execute_command(cmd)
        if output and output != "no_response":
            try:
                response = json.loads(output)
                results["last_response"] = response
            except:
                results["last_response"] = "invalid_json"
        
        return results
    
    def get_sensor_data(self):
        """Obtener datos de sensores principales"""
        commands = [
            # FSR (Force Sensitive Resistors)
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"FSR_Total:\\", sum(m.getData(\\"Device/SubDeviceList/LFoot/FSR/TotalWeight/Sensor/Value\\")) + sum(m.getData(\\"Device/SubDeviceList/RFoot/FSR/TotalWeight/Sensor/Value\\")))"',
            
            # IMU
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"IMU_AccX:\\", m.getData(\\"Device/SubDeviceList/InertialSensor/AccX/Sensor/Value\\"))"',
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"IMU_AccY:\\", m.getData(\\"Device/SubDeviceList/InertialSensor/AccY/Sensor/Value\\"))"',
            'python -c "import naoqi; m=naoqi.ALProxy(\\"ALMemory\\", \\"localhost\\", 9559); print(\\"IMU_GyroX:\\", m.getData(\\"Device/SubDeviceList/InertialSensor/GyroX/Sensor/Value\\"))"',
        ]
        
        results = {}
        for cmd in commands:
            output, error = self.execute_command(cmd)
            if output and not error:
                try:
                    parts = output.split(": ")
                    if len(parts) == 2:
                        param_name = parts[0]
                        param_value = float(parts[1])
                        results[param_name] = param_value
                except:
                    pass
        
        return results
    
    def clear_screen(self):
        """Limpiar pantalla"""
        if CLEAR_SCREEN:
            os.system('cls' if os.name == 'nt' else 'clear')
    
    def format_params_display(self, gait_params, sensor_data, golden_status, server_status):
        """Formatear información para mostrar"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        display = []
        display.append("=" * 80)
        display.append("🤖 NAO LIVE GAIT PARAMETERS MONITOR - {} - IP: {}".format(timestamp, self.nao_ip))
        display.append("=" * 80)
        
        # Estado del servidor
        server_icon = "🟢" if server_status[0] else "🔴"
        display.append("{} Control Server: {}".format(server_icon, server_status[1]))
        
        # Golden parameters status
        golden_icon = "🟡" if golden_status["status"] == "active" else "⚪"
        display.append("{} Golden Parameters: {}".format(golden_icon, golden_status["status"]))
        
        display.append("")
        
        # Parámetros de gait actuales
        display.append("📊 GAIT PARAMETERS (Current ALMemory Values)")
        display.append("-" * 50)
        if gait_params:
            for param, value in sorted(gait_params.items()):
                if param == "Moving":
                    icon = "🏃" if value else "🛑"
                    display.append("  {} {}: {}".format(icon, param, "Yes" if value else "No"))
                else:
                    display.append("  📏 {}: {:.4f}".format(param, value))
        else:
            display.append("  ❌ No se pudieron obtener parámetros de gait")
        
        display.append("")
        
        # Datos de sensores
        display.append("🔧 SENSOR DATA")
        display.append("-" * 50)
        if sensor_data:
            for sensor, value in sorted(sensor_data.items()):
                if "FSR" in sensor:
                    display.append("  ⚖️  {}: {:.3f}".format(sensor, value))
                elif "IMU" in sensor:
                    display.append("  📐 {}: {:.6f}".format(sensor, value))
        else:
            display.append("  ❌ No se pudieron obtener datos de sensores")
        
        display.append("")
        
        # Golden parameters details
        if golden_status["status"] == "active":
            display.append("🌟 GOLDEN PARAMETERS STATUS")
            display.append("-" * 50)
            
            if "last_response" in golden_status:
                resp = golden_status["last_response"]
                if isinstance(resp, dict):
                    display.append("  Mode: {}".format(resp.get("mode", "unknown")))
                    display.append("  Status: {}".format(resp.get("status", "unknown")))
                    if "locked_params" in resp and resp["locked_params"]:
                        display.append("  🔒 Locked Parameters:")
                        for param, value in resp["locked_params"].items():
                            display.append("    • {}: {:.4f}".format(param, value))
            
            display.append("  Files status:")
            for file_path, status in golden_status.get("files", {}).items():
                icon = "✅" if status == "exists" else "❌"
                display.append("    {} {}".format(icon, os.path.basename(file_path)))
        
        display.append("")
        display.append("⏹️  Presiona Ctrl+C para detener el monitoreo")
        display.append("🔄 Actualizando cada {:.1f} segundos".format(UPDATE_INTERVAL))
        
        return "\n".join(display)
    
    def monitor_loop(self):
        """Loop principal de monitoreo"""
        self.running = True
        
        try:
            while self.running:
                self.clear_screen()
                
                # Obtener datos del robot
                gait_params = self.get_current_gait_params()
                sensor_data = self.get_sensor_data()
                golden_status = self.get_golden_params_status()
                server_status = self.get_control_server_status()
                
                # Mostrar información
                display = self.format_params_display(gait_params, sensor_data, golden_status, server_status)
                print(display)
                
                # Esperar antes de la siguiente actualización
                time.sleep(UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoreo detenido por el usuario")
            self.running = False
        except Exception as e:
            print("\n❌ Error en el monitoreo: {}".format(e))
            self.running = False

def main():
    """Función principal"""
    # Obtener IP del NAO desde argumentos o usar default
    if len(sys.argv) > 1:
        nao_ip = sys.argv[1]
    else:
        nao_ip = DEFAULT_NAO_IP
        print("Usando IP por defecto: {}".format(nao_ip))
        print("Para usar otra IP: python {} <IP_DEL_NAO>".format(sys.argv[0]))
        print()
    
    # Crear monitor
    monitor = NAOGaitMonitor(nao_ip)
    
    try:
        # Conectar al NAO
        if not monitor.connect():
            sys.exit(1)
        
        # Iniciar monitoreo
        print("🚀 Iniciando monitoreo en tiempo real...")
        print("   IP: {}".format(nao_ip))
        print("   Intervalo: {:.1f}s".format(UPDATE_INTERVAL))
        print("   Presiona Ctrl+C para detener")
        print()
        time.sleep(2)
        
        monitor.monitor_loop()
        
    finally:
        monitor.disconnect()

if __name__ == "__main__":
    main()
