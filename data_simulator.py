#!/usr/bin/env python3
import socket, msgpack, random, time

HOST = 'localhost'
PORT = 9999

# Generar datos simulados para posición y temperatura
def generate_robot_data():
    position = [round(random.uniform(-1.5, 1.5), 2) for _ in range(25)]
    temperature = [round(random.uniform(30.0, 45.0), 1) for _ in range(25)]
    return {"Position": position, "Temperature": temperature}

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"[Simulador] Escuchando en {HOST}:{PORT}")
        conn, addr = s.accept()
        print(f"[Simulador] Cliente conectado desde {addr}")

        with conn:
            try:
                tipo = conn.recv(16).decode().strip()
                if tipo != "GUI":
                    print("[Simulador] Cliente no es GUI, cerrando conexión.")
                    return
                print("[Simulador] Cliente identificado como GUI.")

                while True:
                    data = generate_robot_data()
                    packed = msgpack.packb(data)
                    conn.sendall(packed)
                    time.sleep(1)
            except Exception as e:
                print("[Simulador] Error en conexión:", e)

if __name__ == "__main__":
    main()
