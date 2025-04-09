#!/usr/bin/env python3
import tkinter as tk
import socket, msgpack, time, threading

# Parámetros de conexión (ajusta según corresponda; para pruebas se usa el dummy server)
NAO_HOST = 'localhost'
NAO_PORT = 5050

def is_safe_to_move():
    """
    Realiza las comprobaciones de seguridad necesarias antes de enviar un comando.
    Aquí se podrían verificar:
      - Estado de sensores de inclinación y presión.
      - Nivel de batería.
      - Estado de rigidez y estabilidad.
      - Que no exista otro movimiento en curso que pueda generar conflicto.
    En este ejemplo se simula que siempre es seguro.
    """
    # TODO: Implementar comprobaciones reales.
    return True 

def send_command(position_array):
    """
    Envía un comando en el formato requerido por LoLA:
      {"Command": {"Position": [25 valores flotantes]}}
    """
    command = {"Command": {"Position": position_array}}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((NAO_HOST, NAO_PORT))
            s.sendall(msgpack.packb(command))
    except Exception as e:
        print("Error enviando comando al NAO:", e)

def walk_forward():
    """
    Ejecuta una secuencia completa de caminata hacia adelante.
    Se simula un ciclo que alterna los movimientos de las piernas.
    
    La lista de 25 joints (índices):
      - Joints 14 a 19: Pierna izquierda 
          14: LHipYawPitch, 15: LHipRoll, 16: LHipPitch, 17: LKneePitch, 18: LAnklePitch, 19: LAnkleRoll
      - Joints 20 a 24: Pierna derecha 
          20: RHipRoll, 21: RHipPitch, 22: RKneePitch, 23: RAnklePitch, 24: RAnkleRoll
    """
    if not is_safe_to_move():
        print("Movimiento no seguro. Abortando caminata.")
        return

    # Postura neutral: todos los joints en 0.0 (postura de reposo)
    posture_neutral = [0.0] * 25

    # --- Secuencia para el paso con la pierna derecha ---
    # Fase 1: Desplazar peso a la pierna izquierda
    posture_shift_left = posture_neutral.copy()
    posture_shift_left[16] = -0.1   # LHipPitch ligeramente hacia atrás
    posture_shift_left[21] = 0.1    # RHipPitch ligeramente hacia adelante
    print("Ejecutando: Desplazar peso a la pierna izquierda")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_shift_left)
    time.sleep(0.5)

    # Fase 2: Levantar la pierna derecha
    posture_right_lift = posture_shift_left.copy()
    posture_right_lift[22] = 0.5    # Aumentar RKneePitch para levantar la pierna
    posture_right_lift[23] = -0.3   # Ajustar RAnklePitch para despejar el pie
    print("Ejecutando: Levantar la pierna derecha")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_right_lift)
    time.sleep(0.5)

    # Fase 3: Mover la pierna derecha hacia adelante
    posture_right_forward = posture_right_lift.copy()
    posture_right_forward[21] = 0.3   # RHipPitch: aumentar el ángulo para mover la pierna hacia adelante
    posture_right_forward[22] = 0.3   # Reducir el ángulo de la rodilla para avanzar
    print("Ejecutando: Mover la pierna derecha hacia adelante")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_right_forward)
    time.sleep(0.5)

    # Fase 4: Bajar la pierna derecha (pisar)
    posture_right_down = posture_neutral.copy()
    print("Ejecutando: Bajar la pierna derecha")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_right_down)
    time.sleep(0.5)

    # --- Secuencia para el paso con la pierna izquierda ---
    # Fase 5: Desplazar peso a la pierna derecha
    posture_shift_right = posture_neutral.copy()
    posture_shift_right[16] = 0.1    # LHipPitch: ligeramente hacia adelante
    posture_shift_right[21] = -0.1   # RHipPitch: ligeramente hacia atrás
    print("Ejecutando: Desplazar peso a la pierna derecha")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_shift_right)
    time.sleep(0.5)

    # Fase 6: Levantar la pierna izquierda
    posture_left_lift = posture_shift_right.copy()
    posture_left_lift[17] = 0.5     # Aumentar LKneePitch para levantar la pierna
    posture_left_lift[18] = -0.3    # Ajustar LAnklePitch para despejar el pie
    print("Ejecutando: Levantar la pierna izquierda")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_left_lift)
    time.sleep(0.5)

    # Fase 7: Mover la pierna izquierda hacia adelante
    posture_left_forward = posture_left_lift.copy()
    posture_left_forward[16] = 0.3   # LHipPitch: aumentar el ángulo para mover la pierna hacia adelante
    print("Ejecutando: Mover la pierna izquierda hacia adelante")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_left_forward)
    time.sleep(0.5)

    # Fase 8: Bajar la pierna izquierda (pisar)
    posture_left_down = posture_neutral.copy()
    print("Ejecutando: Bajar la pierna izquierda")
    if not is_safe_to_move():
        print("Condiciones de seguridad no cumplidas, abortando.")
        return
    send_command(posture_left_down)
    time.sleep(0.5)

    print("Ciclo de caminata completado.")

class KeyboardController(tk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(borderwidth=2, relief="groove")
        self.label = tk.Label(self, text="Tecla presionada: Ninguna", font=("Arial", 12))
        self.label.pack(padx=10, pady=10)
        self.bind_all("<Key>", self.on_key_press)

    def on_key_press(self, event):
        key = event.char.upper()
        self.label.config(text=f"Tecla presionada: {key}")
        if key == "W":
            print("Comando: Moverse hacia adelante (caminata)")
            # Se lanza la secuencia de caminata en un hilo para no bloquear la GUI
            threading.Thread(target=walk_forward, daemon=True).start()
        elif key == "A":
            print("Comando: Girar a la izquierda")
            # Aquí implementarías la función para girar a la izquierda con seguridad
        elif key == "S":
            print("Comando: Moverse hacia atrás")
            # Aquí implementarías la función para retroceder con seguridad
        elif key == "D":
            print("Comando: Girar a la derecha")
            # Aquí implementarías la función para girar a la derecha con seguridad

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Control Remoto NAO - Teclado")
    kb_controller = KeyboardController(master=root)
    kb_controller.pack(padx=10, pady=10)
    root.mainloop()
