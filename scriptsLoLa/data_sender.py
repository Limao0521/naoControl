#!/usr/bin/env python3
import socket, msgpack, random

HOST = 'localhost'
PORT = 9999

def send_robot_command():
    command = {
        "Command": {
            "Position": [round(random.uniform(-1.0, 1.0), 2) for _ in range(25)],
            "Chest": [round(random.uniform(0.0, 1.0), 2) for _ in range(3)]
        }
    }
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        packed = msgpack.packb(command)
        s.sendall(packed)
        print("Comando enviado:")
        print(command)

def main():
    send_robot_command()

if __name__ == "__main__":
    main()
