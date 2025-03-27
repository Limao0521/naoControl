#!/usr/bin/env python3
import socket, msgpack

HOST = 'localhost'
PORT = 9999

def read_robot_data():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        data = s.recv(1024)
        if data:
            robot_data = msgpack.unpackb(data, raw=False)
            return robot_data
    return None

def main():
    data = read_robot_data()
    print("Datos recibidos del robot simulador:")
    print(data)

if __name__ == "__main__":
    main()
