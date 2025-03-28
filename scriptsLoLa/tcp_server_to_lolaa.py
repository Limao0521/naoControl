#!/usr/bin/env python3
import socket
import threading
import sys

# Agregar msgpack local al path
sys.path.insert(0, "/home/nao/proyecto_control/msgpack")
import msgpack

LOLA_SOCKET_PATH = "/tmp/robocup"
BUFFER_SIZE = 896
TCP_PORT = 5050

clientes_gui = []

def reenviar_a_lola(comando):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(LOLA_SOCKET_PATH)
            s.recv(BUFFER_SIZE)  # sincronización
            s.send(msgpack.packb(comando))
    except Exception as e:
        print("[ERROR LoLA]", e)

def manejar_cliente(conn, addr):
    print(f"[GUI] Cliente conectado desde {addr}")
    clientes_gui.append(conn)
    try:
        while True:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s_unix:
                s_unix.connect(LOLA_SOCKET_PATH)
                data = s_unix.recv(BUFFER_SIZE)
                for c in clientes_gui:
                    try:
                        c.sendall(data)
                    except Exception as e:
                        print("[ERROR enviando a GUI]", e)
                        clientes_gui.remove(c)
    except Exception as e:
        print("[GUI Desconectado]", e)
        clientes_gui.remove(conn)
        conn.close()

def manejar_comandos_remotos():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind(("0.0.0.0", TCP_PORT))
        servidor.listen(5)
        print(f"[NAO] Escuchando conexiones TCP en puerto {TCP_PORT}...")
        while True:
            conn, addr = servidor.accept()
            tipo = conn.recv(16).decode().strip()
            if tipo == "GUI":
                threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True).start()
            elif tipo == "CONTROL":
                threading.Thread(target=escuchar_control_remoto, args=(conn, addr), daemon=True).start()
            else:
                print(f"[Desconocido] Tipo de conexión no reconocido: {tipo}")
                conn.close()

def escuchar_control_remoto(conn, addr):
    print(f"[CONTROL] Cliente de control conectado desde {addr}")
    with conn:
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                comando = msgpack.unpackb(data, raw=False)
                reenviar_a_lola(comando)
            except Exception as e:
                print("[ERROR CONTROL]", e)
                break

if __name__ == "__main__":
    manejar_comandos_remotos()
