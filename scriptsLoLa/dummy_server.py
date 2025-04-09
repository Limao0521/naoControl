import socket
import msgpack

HOST = 'localhost'
PORT = 5050

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"Dummy server escuchando en {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            print(f"Conexión aceptada de {addr}")
            with conn:
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    try:
                        command = msgpack.unpackb(data, raw=False)
                        print("Comando recibido:", command)
                    except Exception as e:
                        print("Error al desempaquetar el mensaje:", e)

if __name__ == "__main__":
    main()
