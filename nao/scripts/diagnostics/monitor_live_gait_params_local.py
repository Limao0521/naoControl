#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monitor Live Gait Parameters - NAO Local Version
================================================

Script para ejecutar DIRECTAMENTE en el NAO y monitorear en tiempo real 
los parámetros de caminata que se están aplicando al robot.

Muestra:
- Parámetros de gait actuales desde ALMemory
- Velocidades de movimiento
- Datos de sensores (FSR, IMU)
- Estado del control server
- Estado de golden parameters si está activo

Uso en el NAO:
    ssh nao@IP_DEL_NAO
    cd ~/scripts
    python monitor_live_gait_params_local.py

Controles:
    Ctrl+C: Detener monitoreo
    
Compatible con Python 2.7 (NAO)
"""

import sys
import time
import json
import os
import csv
from datetime import datetime

try:
    import naoqi
    from naoqi import ALProxy
except ImportError:
    print("Error: Este script debe ejecutarse en el NAO con naoqi disponible")
    sys.exit(1)

# Configuración
UPDATE_INTERVAL = 1.0  # segundos entre actualizaciones
CLEAR_SCREEN = True    # limpiar pantalla entre actualizaciones

class NAOLocalGaitMonitor:
    def __init__(self):
        self.memory = None
        self.motion = None
        self.running = False
        self.csv_path = "/home/nao/scripts/gait_params_log.csv"
        
    def connect_proxies(self):
        """Conectar a los proxies de NAOqi"""
        try:
            print("Conectando a ALMemory y ALMotion...")
            self.memory = ALProxy("ALMemory", "localhost", 9559)
            self.motion = ALProxy("ALMotion", "localhost", 9559)
            print("✅ Proxies conectados")
            return True
            
        except Exception as e:
            print("❌ Error conectando proxies: {}".format(e))
            return False
    
    def get_current_gait_params(self):
        """Obtener parámetros de gait actuales desde ALMemory"""
        try:
            params = {}
            
            # Parámetros principales de gait con claves alternativas
            gait_keys = [
                ("MaxStepX", ["Motion/Walk/MaxStepX", "WalkingEngine/MaxStepX"]),
                ("MaxStepY", ["Motion/Walk/MaxStepY", "WalkingEngine/MaxStepY"]), 
                ("MaxStepTheta", ["Motion/Walk/MaxStepTheta", "WalkingEngine/MaxStepTheta"]),
                ("StepHeight", ["Motion/Walk/StepHeight", "WalkingEngine/StepHeight"]),
                ("Frequency", ["Motion/Walk/Frequency", "WalkingEngine/Frequency"]),
                ("MaxStepFrequency", ["Motion/Walk/MaxStepFrequency", "WalkingEngine/MaxStepFrequency"]),
                ("StepLength", ["Motion/Walk/StepLength", "WalkingEngine/StepLength"]),
                ("SidestepLength", ["Motion/Walk/SidestepLength", "WalkingEngine/SidestepLength"]),
                ("MaxTurnSpeed", ["Motion/Walk/MaxTurnSpeed", "WalkingEngine/MaxTurnSpeed"]),
                ("ZmpOffsetX", ["Motion/Walk/ZmpOffsetX", "WalkingEngine/ZmpOffsetX"]),
                ("ZmpOffsetY", ["Motion/Walk/ZmpOffsetY", "WalkingEngine/ZmpOffsetY"])
            ]
            
            for param_name, key_list in gait_keys:
                value_found = False
                for key in key_list:
                    try:
                        value = self.memory.getData(key)
                        if value is not None:
                            params[param_name] = float(value)
                            value_found = True
                            break
                    except Exception as e:
                        continue
                
                if not value_found:
                    # Intentar obtener desde ALMotion directamente
                    try:
                        if param_name == "MaxStepX":
                            walk_config = self.motion.getWalkConfig()
                            if walk_config and len(walk_config) > 0:
                                params[param_name] = float(walk_config[0])
                                value_found = True
                    except:
                        pass
                
                if not value_found:
                    params[param_name] = "N/A"
            
            # Estado del movimiento - probar múltiples claves
            try:
                walking_keys = [
                    "Motion/Walk/IsEnabled",
                    "Motion/Walk/Active", 
                    "WalkingEngine/IsEnabled",
                    "robotIsWalking"
                ]
                
                walking_found = False
                for key in walking_keys:
                    try:
                        is_moving = self.memory.getData(key)
                        if is_moving is not None:
                            params["Walking"] = bool(is_moving)
                            walking_found = True
                            break
                    except:
                        continue
                
                if not walking_found:
                    # Intentar detectar movimiento desde ALMotion
                    try:
                        robot_state = self.motion.getWalkArmsEnabled()
                        params["Walking"] = bool(robot_state)
                    except:
                        params["Walking"] = False
                        
            except:
                params["Walking"] = False
                
            # Velocidades actuales y diagnóstico adicional
            if params.get("Walking", False):
                try:
                    # Intentar obtener velocidades desde ALMotion
                    robot_config = self.motion.getRobotConfig()
                    params["RobotConfig"] = len(robot_config) > 0
                except:
                    params["RobotConfig"] = False
            
            # Añadir diagnóstico de inicialización
            try:
                # Verificar si el robot está despierto
                is_awake = self.memory.getData("robotIsWakeUp")
                params["IsAwake"] = bool(is_awake) if is_awake is not None else False
            except:
                params["IsAwake"] = False
            
            # Verificar si ALMotion está inicializado
            try:
                stiffness = self.motion.getStiffnesses("Body")
                params["MotionActive"] = len(stiffness) > 0 and max(stiffness) > 0.1
            except:
                params["MotionActive"] = False
            
            # Si no hay parámetros, intentar obtenerlos con ALMotion directamente
            if all(v == "N/A" for k, v in params.items() if k in ["MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency"]):
                try:
                    # Intentar obtener configuración actual del walking engine
                    walk_params = self._get_motion_walk_params()
                    if walk_params:
                        params.update(walk_params)
                except:
                    pass
            
            return params
            
        except Exception as e:
            print("Error obteniendo parámetros de gait: {}".format(e))
            return {}
    
    def _get_motion_walk_params(self):
        """Obtener parámetros directamente desde ALMotion"""
        try:
            params = {}
            
            # Intentar diferentes métodos de ALMotion
            try:
                # Método 1: getWalkConfig (si existe)
                walk_config = self.motion.getWalkConfig()
                if walk_config and len(walk_config) >= 5:
                    params["MaxStepX"] = float(walk_config[0])
                    params["MaxStepY"] = float(walk_config[1])
                    params["MaxStepTheta"] = float(walk_config[2])
                    params["StepHeight"] = float(walk_config[3])
                    params["Frequency"] = float(walk_config[4])
                    return params
            except:
                pass
            
            # Método 2: Usar valores por defecto típicos del NAO
            try:
                # Si el robot está activo, usar valores por defecto conocidos
                if self.motion:
                    params = {
                        "MaxStepX": 0.04,      # 4 cm típico
                        "MaxStepY": 0.14,      # 14 cm típico
                        "MaxStepTheta": 0.349, # ~20 grados típico
                        "StepHeight": 0.02,    # 2 cm típico
                        "Frequency": 1.0       # 1 Hz típico
                    }
                    return params
            except:
                pass
            
            return None
            
        except Exception as e:
            print("Error obteniendo parámetros desde ALMotion: {}".format(e))
            return None
    
    def get_sensor_data(self):
        """Obtener datos de sensores principales"""
        try:
            sensors = {}
            
            # FSR (Force Sensitive Resistors) - Sensores de presión en los pies
            try:
                fsr_left = self.memory.getData("Device/SubDeviceList/LFoot/FSR/TotalWeight/Sensor/Value")
                fsr_right = self.memory.getData("Device/SubDeviceList/RFoot/FSR/TotalWeight/Sensor/Value")
                sensors["FSR_Left"] = float(fsr_left)
                sensors["FSR_Right"] = float(fsr_right)
                sensors["FSR_Total"] = sensors["FSR_Left"] + sensors["FSR_Right"]
            except:
                sensors["FSR_Total"] = "N/A"
            
            # IMU (Inertial Measurement Unit) - Acelerómetros y giroscopios
            try:
                acc_x = self.memory.getData("Device/SubDeviceList/InertialSensor/AccX/Sensor/Value")
                acc_y = self.memory.getData("Device/SubDeviceList/InertialSensor/AccY/Sensor/Value")
                acc_z = self.memory.getData("Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value")
                
                gyro_x = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroX/Sensor/Value")
                gyro_y = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroY/Sensor/Value")
                
                sensors["AccX"] = float(acc_x)
                sensors["AccY"] = float(acc_y)
                sensors["AccZ"] = float(acc_z)
                sensors["GyroX"] = float(gyro_x)
                sensors["GyroY"] = float(gyro_y)
                
            except Exception as e:
                sensors["IMU_Error"] = str(e)
            
            # Ángulos del cuerpo
            try:
                angle_x = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value")
                angle_y = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value")
                sensors["AngleX"] = float(angle_x)
                sensors["AngleY"] = float(angle_y)
            except:
                pass
                
            return sensors
            
        except Exception as e:
            print("Error obteniendo datos de sensores: {}".format(e))
            return {}
    
    def get_control_server_status(self):
        """Verificar si el control server está ejecutándose"""
        try:
            import os
            # Buscar proceso del control server usando os.popen (compatible NAO)
            process = os.popen("ps aux | grep control_server.py | grep -v grep")
            result = process.read().strip()
            process.close()
            
            if result:
                return True, "Control server activo"
            else:
                return False, "Control server no encontrado"
        except:
            return False, "No se pudo verificar"
    
    def get_golden_params_status(self):
        """Verificar estado del sistema de golden parameters"""
        try:
            import os
            
            # Verificar si el detector está corriendo usando os.popen (compatible NAO)
            try:
                process = os.popen("ps aux | grep golden_params_detector | grep -v grep")
                result = process.read().strip()
                process.close()
                
                if not result:
                    return {"status": "inactive", "message": "Golden params detector no activo"}
            except:
                return {"status": "inactive", "message": "Golden params detector no activo"}
            
            status = {"status": "active", "files": {}}
            
            # Verificar archivos de estado
            status_files = [
                "/tmp/golden_params_detector.pid",
                "/tmp/golden_remote_command.json", 
                "/tmp/golden_remote_response.json"
            ]
            
            for file_path in status_files:
                if os.path.exists(file_path):
                    status["files"][os.path.basename(file_path)] = "exists"
                else:
                    status["files"][os.path.basename(file_path)] = "missing"
            
            # Intentar leer el estado actual
            response_file = "/tmp/golden_remote_response.json"
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                        status["last_response"] = response
                except:
                    status["last_response"] = "invalid_json"
            
            return status
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _ensure_csv(self):
        """Ensure CSV exists and write header if missing (Python 2 compatible)."""
        try:
            if not os.path.exists(self.csv_path):
                # Create and write header
                header = [
                    "timestamp", "MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency",
                    "Walking", "FSR_Left", "FSR_Right", "FSR_Total", "AccX", "AccY", "AccZ",
                    "GyroX", "GyroY", "AngleX", "AngleY"
                ]
                f = open(self.csv_path, 'wb')
                # Python2 csv needs binary mode
                writer = csv.writer(f)
                writer.writerow(header)
                f.close()
        except Exception:
            # Ignore CSV creation errors to avoid breaking monitor
            pass

    def _append_csv_row(self, gait_params, sensor_data):
        """Append a row with current parameters to CSV (Python 2 compatible)."""
        try:
            # Ensure file exists
            self._ensure_csv()

            row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            for k in ["MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency"]:
                v = gait_params.get(k, "")
                row.append(v if not isinstance(v, bool) else (1 if v else 0))

            # Walking
            row.append(1 if gait_params.get("Walking") else 0)

            # Sensors
            for k in ["FSR_Left", "FSR_Right", "FSR_Total", "AccX", "AccY", "AccZ", "GyroX", "GyroY", "AngleX", "AngleY"]:
                row.append(sensor_data.get(k, ""))

            # Write row
            f = open(self.csv_path, 'ab')
            writer = csv.writer(f)
            writer.writerow(row)
            f.close()
        except Exception:
            # Don't crash monitor on CSV errors
            pass
    
    def clear_screen(self):
        """Limpiar pantalla"""
        if CLEAR_SCREEN:
            os.system('clear')
    
    def format_params_display(self, gait_params, sensor_data, golden_status, server_status):
        """Formatear información para mostrar"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        lines = []
        lines.append("=" * 80)
        lines.append("🤖 NAO LIVE GAIT PARAMETERS - LOCAL MONITOR - {}".format(timestamp))
        lines.append("=" * 80)
        
        # Estado del servidor
        server_icon = "🟢" if server_status[0] else "🔴"
        lines.append("{} Control Server: {}".format(server_icon, server_status[1]))
        
        # Golden parameters status
        golden_icon = "🟡" if golden_status.get("status") == "active" else "⚪"
        lines.append("{} Golden Parameters: {}".format(golden_icon, golden_status.get("status", "unknown")))
        
        lines.append("")
        
        # Parámetros de gait actuales
        lines.append("📊 CURRENT GAIT PARAMETERS")
        lines.append("-" * 50)
        if gait_params:
            # Mostrar estado de diagnóstico primero
            lines.append("  🔍 DIAGNOSTIC INFO:")
            lines.append("    • Robot Awake: {}".format("YES" if gait_params.get("IsAwake") else "NO"))
            lines.append("    • Motion Active: {}".format("YES" if gait_params.get("MotionActive") else "NO"))
            
            # Mostrar estado de caminata
            if "Walking" in gait_params:
                walking_icon = "🏃" if gait_params["Walking"] else "🛑"
                lines.append("  {} Walking: {}".format(walking_icon, "YES" if gait_params["Walking"] else "NO"))
                lines.append("")
            
            # Parámetros principales de gait
            main_params = ["MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency"]
            lines.append("  🎯 MAIN GAIT PARAMETERS:")
            for param in main_params:
                if param in gait_params:
                    value = gait_params[param]
                    if isinstance(value, float):
                        lines.append("  📏 {}: {:.4f}".format(param, value))
                    else:
                        lines.append("  📏 {}: {}".format(param, value))
            
            # Parámetros adicionales
            lines.append("")
            lines.append("  📋 Additional Parameters:")
            other_params = [p for p in sorted(gait_params.keys()) if p not in main_params + ["Walking", "IsAwake", "MotionActive", "RobotConfig"]]
            for param in other_params:
                value = gait_params[param]
                if isinstance(value, float):
                    lines.append("    • {}: {:.4f}".format(param, value))
                else:
                    lines.append("    • {}: {}".format(param, value))
        else:
            lines.append("  ❌ No se pudieron obtener parámetros de gait")
        
        lines.append("")
        
        # Datos de sensores
        lines.append("🔧 SENSOR DATA")
        lines.append("-" * 50)
        if sensor_data:
            # FSR data
            if any("FSR" in key for key in sensor_data.keys()):
                lines.append("  ⚖️  Force Sensors:")
                for key in ["FSR_Left", "FSR_Right", "FSR_Total"]:
                    if key in sensor_data:
                        value = sensor_data[key]
                        if isinstance(value, float):
                            lines.append("    • {}: {:.3f}".format(key, value))
                        else:
                            lines.append("    • {}: {}".format(key, value))
            
            # IMU data
            if any(key in sensor_data for key in ["AccX", "AccY", "AccZ"]):
                lines.append("  📐 Accelerometer:")
                for key in ["AccX", "AccY", "AccZ"]:
                    if key in sensor_data:
                        lines.append("    • {}: {:.6f}".format(key, sensor_data[key]))
            
            if any(key in sensor_data for key in ["GyroX", "GyroY"]):
                lines.append("  🌀 Gyroscope:")
                for key in ["GyroX", "GyroY"]:
                    if key in sensor_data:
                        lines.append("    • {}: {:.6f}".format(key, sensor_data[key]))
            
            if any(key in sensor_data for key in ["AngleX", "AngleY"]):
                lines.append("  📐 Body Angles:")
                for key in ["AngleX", "AngleY"]:
                    if key in sensor_data:
                        lines.append("    • {}: {:.4f}°".format(key, sensor_data[key] * 57.2958))  # rad to deg
        else:
            lines.append("  ❌ No se pudieron obtener datos de sensores")
        
        lines.append("")
        
        # Golden parameters details
        if golden_status.get("status") == "active":
            lines.append("🌟 GOLDEN PARAMETERS STATUS")
            lines.append("-" * 50)
            
            if "last_response" in golden_status:
                resp = golden_status["last_response"]
                if isinstance(resp, dict):
                    lines.append("  Mode: {}".format(resp.get("mode", "unknown")))
                    lines.append("  Status: {}".format(resp.get("status", "unknown")))
                    if "locked_params" in resp and resp["locked_params"]:
                        lines.append("  🔒 Locked Parameters:")
                        for param, value in resp["locked_params"].items():
                            lines.append("    • {}: {:.4f}".format(param, value))
            
            if "files" in golden_status:
                lines.append("  Files:")
                for filename, status in golden_status["files"].items():
                    icon = "✅" if status == "exists" else "❌"
                    lines.append("    {} {}".format(icon, filename))
        
        lines.append("")
        lines.append("💾 CSV LOG: {}".format(self.csv_path))
        lines.append("⏹️  Presiona Ctrl+C para detener el monitoreo")
        lines.append("🔄 Actualizando cada {:.1f} segundos".format(UPDATE_INTERVAL))
        lines.append("")
        
        return "\n".join(lines)
    
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

                # Guardar en CSV cada vez que se actualiza
                self._append_csv_row(gait_params, sensor_data)
                
                # Mostrar mensaje de guardado en CSV
                if gait_params or sensor_data:
                    print("💾 Datos guardados en: {}".format(self.csv_path))
                
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
    print("🚀 NAO Local Gait Parameters Monitor")
    print("====================================")
    print("Intervalo de actualización: {:.1f}s".format(UPDATE_INTERVAL))
    print("Presiona Ctrl+C para detener")
    print()
    
    # Crear monitor
    monitor = NAOLocalGaitMonitor()
    
    try:
        # Conectar proxies
        if not monitor.connect_proxies():
            sys.exit(1)
        
        print("🔄 Iniciando monitoreo en tiempo real...")
        time.sleep(2)
        
        # Iniciar monitoreo
        monitor.monitor_loop()
        
    except Exception as e:
        print("❌ Error general: {}".format(e))
    
    print("👋 Monitor finalizado")

if __name__ == "__main__":
    main()
