#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import socket, msgpack, threading, time, subprocess, os, sys
import keyboard_controller  # Importamos el módulo del controlador de teclado

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

# Utilidad para obtener el índice de cada articulación
JOINT_INDEX = {name: i for i, name in enumerate(JOINT_NAMES)}

# Configuración por defecto para el simulador
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

        frame_mode = ttk.LabelFrame(self, text="Selecciona el modo de conexión")
        frame_mode.pack(padx=10, pady=10, fill="x")

        rb_sim = ttk.Radiobutton(frame_mode, text="Simulador (TCP/IP)", variable=self.selected_mode, value="simulador", command=self.toggle_fields)
        rb_real = ttk.Radiobutton(frame_mode, text="Robot Real (TCP/IP)", variable=self.selected_mode, value="real", command=self.toggle_fields)
        rb_sim.pack(anchor="w", padx=5, pady=2)
        rb_real.pack(anchor="w", padx=5, pady=2)

        self.frame_ip_port = ttk.LabelFrame(self, text="Datos del Robot Real")
        self.frame_ip_port.pack(padx=10, pady=5, fill="x")

        ttk.Label(self.frame_ip_port, text="Dirección IP:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self.entry_ip = ttk.Entry(self.frame_ip_port, textvariable=self.robot_ip, width=20)
        self.entry_ip.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self.frame_ip_port, text="Puerto:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.entry_port = ttk.Entry(self.frame_ip_port, textvariable=self.robot_port, width=10)
        self.entry_port.grid(row=1, column=1, padx=5, pady=2)

        btn_start = ttk.Button(self, text="Iniciar", command=self.on_start)
        btn_start.pack(pady=10)

        self.toggle_fields()

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
# Interfaz Gráfica Principal (Monitor) con integración del control por teclado
###############################################################################
class RobotDataGUI(tk.Tk):
    def __init__(self, mode, host, port):
        super().__init__()
        self.title("Monitor y Control del Robot")
        self.mode = mode
        self.host = host
        self.port = port
        self.running = True

        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True)

        data_frame = ttk.Frame(container)
        data_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.position_labels = {}
        self.temperature_labels = {}
        self.frames = {}

        for group, joints in JOINT_GROUPS.items():
            frame = ttk.LabelFrame(data_frame, text=group)
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

        kb_container = ttk.Frame(container)
        kb_container.pack(side="right", fill="y", padx=10, pady=10)
        kb_label = ttk.Label(kb_container, text="Control de Movimiento (WASD)", font=("Arial", 12))
        kb_label.pack(pady=5)

        self.keyboard_controller = keyboard_controller.KeyboardController(master=kb_container)
        self.keyboard_controller.pack(fill="both", expand=True)

        threading.Thread(target=self.update_data, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_data(self):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((self.host, self.port))
                s.sendall(b"GUI\n")
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
        battery = robot_data.get("Battery", [])

    # Actualización de articulaciones (sin cambios)
    for joint, idx in JOINT_INDEX.items():
        if idx < len(positions):
            self.position_labels[joint].config(text=f"Pos: {positions[idx]}")
        if idx < len(temperatures):
            self.temperature_labels[joint].config(text=f"Temp: {temperatures[idx]}")

    # Actualización de batería (nuevo código)
    if len(battery) >= 4:
        self.battery_labels["Charge"].config(text=f"Carga: {battery[0]:.2f}%")
        self.battery_labels["Current"].config(text=f"Corriente: {battery[1]:.2f} A")
        self.battery_labels["Status"].config(text=f"Estado: {battery[2]:.2f}")
        self.battery_labels["Temperature"].config(text=f"Temperatura: {battery[3]:.2f} °C")


    def on_close(self):
        self.running = False
        self.destroy()

###############################################################################
def main():
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

    gui = RobotDataGUI(mode=config.mode, host=host, port=port)
    gui.mainloop()

    if sim_proc is not None:
        sim_proc.kill()

if __name__ == "__main__":
    main()