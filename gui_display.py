#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import socket, msgpack, threading, time, subprocess, os, sys

# Lista completa de 25 articulaciones en el orden esperado por LoLA
JOINT_NAMES = [
    "HeadYaw", "HeadPitch",
    "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw", "LHand",
    "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "RHand",
    "LHipYawPitch", "LHipRoll", "LHipPitch", "LKneePitch", "LAnklePitch", "LAnkleRoll",
    "RHipRoll", "RHipPitch", "RKneePitch", "RAnklePitch", "RAnkleRoll"
]

# Definir grupos de articulaciones para la visualización
JOINT_GROUPS = {
    "Cabeza": ["HeadYaw", "HeadPitch"],
    "Brazos Izquierdo": ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw", "LHand"],
    "Brazos Derecho": ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "RHand"],
    "Piernas": ["LHipYawPitch", "LHipRoll", "LHipPitch", "LKneePitch", "LAnklePitch", "LAnkleRoll",
                "RHipRoll", "RHipPitch", "RKneePitch", "RAnklePitch", "RAnkleRoll"]
}

# Utilidad para obtener el índice de cada articulación (basado en JOINT_NAMES)
JOINT_INDEX = {name: i for i, name in enumerate(JOINT_NAMES)}

# Valores por defecto para conexión TCP
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 9999

###############################################################################
# Ventana de Configuración
###############################################################################
class ConfigWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Configuración de Conexión")
        self.resizable(False, False)
        self.selected_mode = tk.StringVar(value="simulador")
        self.robot_ip = tk.StringVar()
        self.robot_port = tk.IntVar(value=5050)

        # Opción de conexión: Simulador o Robot Real
        frame_mode = ttk.LabelFrame(self, text="Selecciona el modo de conexión")
        frame_mode.pack(padx=10, pady=10, fill="x")

        rb_sim = ttk.Radiobutton(frame_mode, text="Simulador (TCP/IP)", variable=self.selected_mode, value="simulador", command=self.toggle_fields)
        rb_real = ttk.Radiobutton(frame_mode, text="Robot Real (TCP/IP)", variable=self.selected_mode, value="real", command=self.toggle_fields)
        rb_sim.pack(anchor="w", padx=5, pady=2)
        rb_real.pack(anchor="w", padx=5, pady=2)

        # Campos de IP y puerto (solo se usan para Robot Real)
        self.frame_ip_port = ttk.LabelFrame(self, text="Datos del Robot Real")
        self.frame_ip_port.pack(padx=10, pady=5, fill="x")

        ttk.Label(self.frame_ip_port, text="Dirección IP:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.entry_ip = ttk.Entry(self.frame_ip_port, textvariable=self.robot_ip, width=20)
        self.entry_ip.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.frame_ip_port, text="Puerto:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.entry_port = ttk.Entry(self.frame_ip_port, textvariable=self.robot_port, width=10)
        self.entry_port.grid(row=1, column=1, padx=5, pady=2)

        # Botón de iniciar
        btn_start = ttk.Button(self, text="Iniciar", command=self.on_start)
        btn_start.pack(pady=10)

        self.toggle_fields()  # ocultar al inicio si es simulador

    def toggle_fields(self):
        state = "normal" if self.selected_mode.get() == "real" else "disabled"
        for child in self.frame_ip_port.winfo_children():
            child.configure(state=state)

    def on_start(self):
        self.mode = self.selected_mode.get()
        self.ip = self.robot_ip.get()
        self.port = self.robot_port.get()
        self.destroy()

###############################################################################
# Interfaz Gráfica Principal (Monitor)
###############################################################################
class RobotDataGUI(tk.Tk):
    def __init__(self, mode, host, port):
        super().__init__()
        self.title("Monitor de Datos del Robot")
        self.mode = mode
        self.host = host
        self.port = port
        self.running = True

        # Diccionarios para almacenar las etiquetas por cada articulación
        self.position_labels = {}
        self.temperature_labels = {}

        # Crear marcos para cada grupo de articulaciones
        self.frames = {}
        for group, joints in JOINT_GROUPS.items():
            frame = ttk.LabelFrame(self, text=group)
            frame.pack(padx=10, pady=5, fill="x")
            self.frames[group] = frame
            for joint in joints:
                subframe = ttk.Frame(frame)
                subframe.pack(fill="x", padx=5, pady=2)
                lbl_joint = ttk.Label(subframe, text=f"{joint}: ", width=15)
                lbl_joint.pack(side="left")
                lbl_pos = ttk.Label(subframe, text="Pos: N/A", width=12)
                lbl_pos.pack(side="left", padx=5)
                lbl_temp = ttk.Label(subframe, text="Temp: N/A", width=12)
                lbl_temp.pack(side="left", padx=5)
                self.position_labels[joint] = lbl_pos
                self.temperature_labels[joint] = lbl_temp

        # Inicia el hilo para actualizar datos
        threading.Thread(target=self.update_data, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_data(self):
        # Esperar un momento para asegurar la conexión
        time.sleep(1)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((self.host, self.port))
            except Exception as e:
                print(f"Error al conectar a {self.host}:{self.port}", e)
                return
            while self.running:
                try:
                    data = s.recv(1024)
                    if data:
                        robot_data = msgpack.unpackb(data, raw=False)
                        self.after(0, self.update_labels, robot_data)
                except Exception as e:
                    print("Error durante la recepción de datos:", e)
                    break

    def update_labels(self, robot_data):
        positions = robot_data.get("Position", [])
        temperatures = robot_data.get("Temperature", [])
        # Para cada articulación, usar el índice de JOINT_INDEX para actualizar
        for joint, idx in JOINT_INDEX.items():
            if idx < len(positions):
                self.position_labels[joint].config(text=f"Pos: {positions[idx]}")
            if idx < len(temperatures):
                self.temperature_labels[joint].config(text=f"Temp: {temperatures[idx]}")

    def on_close(self):
        self.running = False
        self.destroy()

###############################################################################
# Función principal: Inicia la Configuración y luego la GUI
###############################################################################
def main():
    # Mostrar ventana de configuración
    config = ConfigWindow()
    config.mainloop()

    if config.mode == "simulador":
        host = DEFAULT_HOST
        port = DEFAULT_PORT
        simulator_script = os.path.join(os.path.dirname(__file__), "data_simulator.py")
        sim_proc = subprocess.Popen([sys.executable, simulator_script])
    else:
        host = config.ip
        port = config.port
        sim_proc = None

    # Inicia la GUI principal con los parámetros configurados
    gui = RobotDataGUI(mode=config.mode, host=host, port=port)
    gui.mainloop()

    if sim_proc is not None:
        sim_proc.kill()

if __name__ == "__main__":
    main()