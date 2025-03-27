#!/usr/bin/env python3
import socket, msgpack, random, time

HOST = 'localhost'
PORT = 9999

def generate_robot_data():
    # Genera 25 valores para posición (movimientos razonables)
    position = [round(random.uniform(-1.0, 1.0), 2) for _ in range(25)]
    # Genera 25 valores para temperatura (por ejemplo, grados Celsius)
    temperature = [round(random.uniform(30.0, 40.0), 1) for _ in range(25)]
    return {"Position": position, "Temperature": temperature}

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"Simulador de datos corriendo en {HOST}:{PORT}")
        conn, addr = s.accept()
        with conn:
            print("Cliente conectado:", addr)
            while True:
                data = generate_robot_data()
                packed = msgpack.packb(data)
                try:
                    conn.sendall(packed)
                except BrokenPipeError:
                    print("El cliente se desconectó")
                    break
                time.sleep(1)

if __name__ == "__main__":
    main()
