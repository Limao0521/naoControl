#!/usr/bin/env python3
import socket
import msgpack
import threading
import queue
import time

# Ruta al socket UNIX donde LoLA envía datos constantemente
LOLA_SOCKET_PATH = "/tmp/robocup"
BUFFER_SIZE = 896
TCP_PORT = 5050

# Lista para almacenar conexiones GUI activas
clientes_gui = []

# Cola intermedia para desacoplar lectura y envío a GUI
cola_datos = queue.Queue(maxsize=1)

def ciclo_lola():
    """
    Hilo dedicado a leer constantemente desde LoLA sin interrupciones.
    Mantiene una sola conexión permanente con LoLA para garantizar sincronización.
    Los datos más recientes se almacenan en una cola intermedia (cola_datos).
    """
    print("[LoLA] Hilo iniciado: leyendo continuamente de /tmp/robocup...")
    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s_unix:
                s_unix.connect(LOLA_SOCKET_PATH)
                while True:
                    data = s_unix.recv(BUFFER_SIZE)
                    if not data:
                        continue  # Si no hay datos, se continúa esperando
                    # Si la cola está llena, elimina el dato viejo y añade el nuevo inmediatamente
                    if cola_datos.full():
                        try:
                            cola_datos.get_nowait()
                        except queue.Empty:
                            pass
                    cola_datos.put(data)
        except Exception as e:
            print("[ERROR ciclo LoLA]", e)
            # Si se pierde la conexión con LoLA, espera antes de reconectar
            time.sleep(1)

def envio_datos_gui():
    """
    Hilo dedicado a enviar los datos recibidos desde LoLA hacia las GUIs conectadas.
    Toma los datos de la cola intermedia (cola_datos) y los envía con pausas controladas.
    Esto evita saturar las conexiones GUI con demasiados paquetes por segundo.
    """
    print("[Servidor] Hilo iniciado: enviando datos a GUIs conectadas.")
    while True:
        try:
            # Espera hasta recibir datos desde el ciclo LoLA
            data = cola_datos.get()
            # Envía inmediatamente el dato recibido a todas las GUIs conectadas
            for c in clientes_gui[:]:  # Copia de lista para evitar errores al modificarla
                try:
                    c.sendall(data)
                except Exception as e:
                    print("[ERROR enviando a GUI]", e)
                    clientes_gui.remove(c)
            # Pausa breve entre envíos (ajustable según necesidades del proyecto)
            time.sleep(0.1)  # 100ms por defecto
        except Exception as e:
            print("[ERROR en el hilo envío GUI]", e)

def manejar_cliente(conn, addr):
    """
    Función para manejar nuevas conexiones GUI entrantes.
    Simplemente registra el cliente conectado para envío de datos.
    """
    print(f"[GUI] Nueva conexión desde {addr}")
    clientes_gui.append(conn)

def escuchar_control_remoto(conn, addr):
    """
    Función dedicada a recibir comandos de control remoto externos.
    Desempaqueta mensajes msgpack recibidos y los envía inmediatamente a LoLA.
    """
    print(f"[CONTROL] Nuevo cliente de control remoto conectado desde {addr}")
    with conn:
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                comando = msgpack.unpackb(data, raw=False)
                reenviar_a_lola(comando)
            except Exception as e:
                print("[ERROR CONTROL REMOTO]", e)
                break

def reenviar_a_lola(comando):
    """
    Función encargada de reenviar comandos recibidos desde control remoto hacia LoLA.
    Cumple la sincronización requerida por LoLA realizando una lectura antes del envío.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(LOLA_SOCKET_PATH)
            s.recv(BUFFER_SIZE)  # Lectura obligatoria para sincronización
            s.send(msgpack.packb(comando))
    except Exception as e:
        print("[ERROR reenviando comando a LoLA]", e)

def manejar_comandos_remotos():
    """
    Función principal del servidor.
    Escucha continuamente nuevas conexiones TCP en el puerto indicado.
    Distingue conexiones tipo "GUI" o "CONTROL" y las maneja en hilos separados.
    """
    # Iniciar hilos para lectura LoLA y envío a GUI
    threading.Thread(target=ciclo_lola, daemon=True).start()
    threading.Thread(target=envio_datos_gui, daemon=True).start()

    # Crear servidor TCP/IP para recibir conexiones externas
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind(("0.0.0.0", TCP_PORT))
        servidor.listen(5)
        print(f"[NAO] Servidor TCP escuchando en puerto {TCP_PORT}...")
        while True:
            conn, addr = servidor.accept()
            tipo = conn.recv(16).decode().strip()
            if tipo == "GUI":
                threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True).start()
            elif tipo == "CONTROL":
                threading.Thread(target=escuchar_control_remoto, args=(conn, addr), daemon=True).start()
            else:
                print(f"[Servidor] Tipo de conexión desconocido: {tipo}")
                conn.close()

if __name__ == "__main__":
    manejar_comandos_remotos()
