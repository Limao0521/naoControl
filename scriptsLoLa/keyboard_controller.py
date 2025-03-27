# keyboard_controller.py
import tkinter as tk
import socket, msgpack

# Configuración de conexión (ajusta según corresponda)
NAO_HOST = 'localhost'
NAO_PORT = 5050  # 

def move_forward():
    """
    Función que envía un comando para mover al NAO hacia adelante.
    Aquí se deben incluir las comprobaciones de seguridad necesarias
    para asegurar que el robot se mueve de forma controlada.
    """
    print("Comando: Moverse hacia adelante (seguro)")
    # Ejemplo de comando; se puede adaptar a la estructura que utiliza tu sistema
    command = {"Command": {"Move": "forward"}}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((NAO_HOST, NAO_PORT))
            s.sendall(msgpack.packb(command))
    except Exception as e:
        print("Error enviando comando al NAO:", e)

class KeyboardController(tk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(borderwidth=2, relief="groove")
        self.label = tk.Label(self, text="Tecla presionada: Ninguna", font=("Arial", 12))
        self.label.pack(padx=10, pady=10)
        # Enlazar todas las pulsaciones de teclas en la ventana
        self.bind_all("<Key>", self.on_key_press)

    def on_key_press(self, event):
        # Convertir la tecla a mayúscula para facilitar la comparación
        key = event.char.upper()
        self.label.config(text=f"Tecla presionada: {key}")
        if key == "W":
            move_forward()
        # Aquí puedes agregar funciones para A, S, D
        elif key == "A":
            print("Comando: Girar a la izquierda")
            # Implementar función de giro izquierda, con seguridad
        elif key == "S":
            print("Comando: Moverse hacia atrás")
            # Implementar función de retroceso, con seguridad
        elif key == "D":
            print("Comando: Girar a la derecha")
            # Implementar función de giro derecha, con seguridad

if __name__ == "__main__":
    # Para probar el frame de forma independiente
    root = tk.Tk()
    root.title("Control Remoto NAO")
    kb_controller = KeyboardController(master=root)
    kb_controller.pack(padx=10, pady=10)
    root.mainloop()
