# dummy_server.py
import socket, msgpack

HOST = 'localhost'
PORT = 5050

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"Dummy server escuchando en {HOST}:{PORT}")
    conn, addr = s.accept()
    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            comando = msgpack.unpackb(data, raw=False)
            print("Comando recibido:", comando)
