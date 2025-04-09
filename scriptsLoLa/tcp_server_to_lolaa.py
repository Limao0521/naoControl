import socket
import msgpack
import threading
import queue
import time

LOLA_SOCKET_PATH = "/tmp/robocup"
BUFFER_SIZE = 896
TCP_PORT = 5050

clientes_gui = []
cola_datos = queue.Queue(maxsize=1)

def ciclo_lola():
    print("[LoLA] Conexión continua a /tmp/robocup...")
    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s_unix:
                s_unix.connect(LOLA_SOCKET_PATH)
                while True:
                    data = s_unix.recv(BUFFER_SIZE)
                    if not data:
                        continue
                    if cola_datos.full():
                        try:
                            cola_datos.get_nowait()  # Eliminar datos viejos si la cola está llena
                        except queue.Empty:
                            pass
                    cola_datos.put(data)
        except Exception as e:
            print("[ERROR LoLA]", e)
            time.sleep(1)  # Reintentar conexión tras 1 segundo si falla LoLA

def envio_datos_gui():
    print("[Servidor] Hilo de envío de datos a GUI iniciado.")
    while True:
        try:
            data = cola_datos.get()  # Esperar hasta que haya nuevos datos
            for c in clientes_gui[:]:
                try:
                    c.sendall(data)
                except Exception as e:
                    print("[ERROR enviando a GUI]", e)
                    clientes_gui.remove(c)
            time.sleep(0.1)  # Pausa breve para no saturar a la GUI (ajusta este valor)
        except Exception as e:
            print("[ERROR en hilo GUI]", e)

def manejar_cliente(conn, addr):
    print(f"[GUI] Cliente conectado desde {addr}")
    clientes_gui.append(conn)

def escuchar_control_remoto(conn, addr):
    print(f"[CONTROL] Cliente conectado desde {addr}")
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

def reenviar_a_lola(comando):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(LOLA_SOCKET_PATH)
            s.recv(BUFFER_SIZE)
            s.send(msgpack.packb(comando))
    except Exception as e:
        print("[ERROR reenviando a LoLA]", e)

def manejar_comandos_remotos():
    threading.Thread(target=ciclo_lola, daemon=True).start()
    threading.Thread(target=envio_datos_gui, daemon=True).start()
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

if __name__ == "__main__":
    manejar_comandos_remotos()

