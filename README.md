Sistema de Comunicación entre Robot NAOv6 y GUI de Monitoreo 

1. Archivos del Proyecto 

El sistema se compone de los siguientes scripts en Python: 

• gui_display.py 

• data_simulator.py 

• nao_combined_server.py 

2. Descripción de Archivos 

2.1 gui_display.py 

Este archivo contiene la interfaz gráfica que permite visualizar en tiempo real los datos del robot NAO (posición y temperatura de articulaciones). Permite seleccionar entre modo Simulador o Robot Real y establece conexión por medio de protocolo TCP/IP, requiriendo una IP y un puerto. 

Características: 

- Visualización por grupos de articulaciones. 

- Conexión por TCP/IP con el robot o con el simulador local. 

- Entrada manual de IP y puerto si se selecciona Robot Real. 

- Envía 'GUI' como identificador al servidor del robot para recibir datos. 

2.2 data_simulator.py 

Simula datos realistas de un robot NAO para pruebas locales. Abre un socket TCP en localhost:9999 y envía periódicamente paquetes con datos de posición y temperatura en formato msgpack. 

2.3 nao_combined_server.py 

Este servidor debe ejecutarse dentro del robot NAO. Cumple una doble función: envía continuamente datos al GUI y recibe comandos desde un control remoto físico por TCP/IP, que son reenviados al sistema LoLA del robot mediante el socket local /tmp/robocup. 

Características: 

- Escucha en un puerto TCP (por defecto 5050). 

- Distingue el tipo de conexión (GUI o CONTROL) mediante el primer mensaje. 

- Recibe mensajes msgpack desde el cliente remoto y los reenvía a LoLA. 

- Reenvía los datos de LoLA hacia cualquier GUI conectada. 

3. Flujo del Sistema 

1. El GUI se conecta por TCP/IP al NAO (puerto configurado) y se identifica como 'GUI'. 
 2. El robot le envía datos en tiempo real (posición, temperatura). 
 3. El control remoto también se conecta al NAO y se identifica como 'CONTROL'. 
 4. El servidor del robot reenvía los comandos recibidos desde el control al subsistema LoLA. 
 5. La GUI muestra los valores en tiempo real agrupados por zona corporal. 

4. Anexos 

Repositorio de GitHub: https://github.com/Limao0521/scriptsLoLa 

 
