#!/usr/bin/env python3
import socket
import msgpack

LOLA_SOCKET_PATH = "/tmp/robocup"
BUFFER_SIZE = 896
TCP_PORT = 5050

def enviar_a_lola(comando):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(LOLA_SOCKET_PATH)
            s.recv(BUFFER_SIZE)
            s.send(msgpack.packb(comando))
    except Exception as e:
        print("Error al enviar a LoLA:", e)

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(("0.0.0.0", TCP_PORT))
        server_socket.listen(1)
        print(f"[NAO] Esperando conexión en puerto {TCP_PORT}...")
        conn, addr = server_socket.accept()
        print(f"[NAO] Conectado desde {addr}")
        with conn:
            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    comando = msgpack.unpackb(data, raw=False)
                    enviar_a_lola(comando)
                except Exception as e:
                    print("Error de comunicación:", e)
                    break

if __name__ == "__main__":
    main()
