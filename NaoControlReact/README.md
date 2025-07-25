# NAO Control React

Esta es la versión refactorizada en React de la aplicación de control para el robot NAO. La aplicación mantiene toda la funcionalidad original pero ahora está construida con React utilizando hooks modernos.

## Características

- ✅ **Control por Joystick**: Interfaz de joystick virtual para mover el robot
- ✅ **Múltiples Modos**: Control de caminata, brazos y cabeza
- ✅ **Comandos de Postura**: Botones para Stand y Sit
- ✅ **Control de Voz**: Enviar texto para que el robot hable
- ✅ **Control de LEDs**: Cambiar colores de diferentes grupos de LEDs
- ✅ **Cámara en Vivo**: Visualizar el feed de la cámara del robot
- ✅ **Estadísticas**: Ver información del robot y estado de las articulaciones
- ✅ **Cambio de Idioma**: Configurar idioma TTS
- ✅ **Conectividad WebSocket**: Conexión automática con reconexión
- ✅ **Responsive Design**: Optimizado para móviles y escritorio

## Estructura del Proyecto

```
src/
├── components/           # Componentes React
│   ├── NaoController.js  # Componente principal
│   ├── Joystick.js      # Componente del joystick
│   ├── ModePanel.js     # Panel de modos de control
│   ├── ControlButtons.js # Botones Stand/Sit
│   ├── ExtrasNav.js     # Navegación de funciones extra
│   └── [Menu]*.js       # Componentes de menús
├── hooks/               # React Hooks personalizados
│   ├── useWebSocket.js  # Hook para conectividad WebSocket
│   └── useJoystick.js   # Hook para lógica del joystick
└── *.css               # Estilos correspondientes

```

## Mejoras Implementadas

### Arquitectura
- **Componentes Modulares**: Cada función está en su propio componente
- **Hooks Personalizados**: Lógica reutilizable extraída a hooks
- **Estado Reactivo**: Manejo de estado con React hooks
- **Separación de Responsabilidades**: UI y lógica claramente separadas

### Funcionalidad
- **Reconexión Automática**: WebSocket se reconecta automáticamente
- **Indicador de Estado**: Muestra el estado de conexión en tiempo real
- **Touch Optimizado**: Mejor soporte para dispositivos táctiles
- **Prevención de Errores**: Validación antes de enviar comandos

### UX/UI
- **Fullscreen Responsive**: La interfaz ahora ocupa el 100% del ancho y alto de la pantalla
- **Detección Automática de Cámara**: La IP de la cámara se detecta automáticamente
- **Feedback Visual**: Estados activos y hover mejorados
- **Gestos Táctiles**: Soporte completo para touch en el joystick
- **Accesibilidad**: Mejor navegación con teclado
- **Manejo de Errores**: Mensaje de error y botón de reintento para la cámara

## Comandos Disponibles

### `npm start`
Inicia el servidor de desarrollo en [http://localhost:3000](http://localhost:3000)

### `npm run build`
Construye la aplicación para producción en la carpeta `build`

### `npm test`
Ejecuta las pruebas en modo interactivo

## Configuración

### WebSocket
Por defecto, la aplicación se conecta al puerto 6671 en el mismo host. Puedes modificar esto en `src/components/NaoController.js`:

```javascript
const { isConnected, sendMessage, lastMessage } = useWebSocket(6671);
```

### Cámara
La URL de la cámara se detecta automáticamente basándose en la IP actual del navegador:

```javascript
// Se genera automáticamente como: http://[IP_ACTUAL]:8080/video.mjpeg
// Por ejemplo: http://172.19.32.23:8080/video.mjpeg
```

Si necesitas cambiar manualmente la URL, puedes hacerlo en `src/components/CameraMenu.js`.

## Mensajes WebSocket

La aplicación envía y recibe mensajes JSON a través de WebSocket:

### Mensajes Enviados
```javascript
// Movimiento
{ action: 'walk', vx: 0.5, vy: 0.2, wz: 0 }
{ action: 'move', joint: 'HeadYaw', value: 0.3 }

// Postura
{ action: 'posture', value: 'Stand' }

// Voz
{ action: 'say', text: 'Hola mundo' }

// LEDs
{ action: 'led', group: 'ChestLeds', r: 1, g: 0, b: 0 }

// Idioma
{ action: 'language', value: 'Spanish' }
```

### Mensajes Recibidos
```javascript
// Estadísticas (ejemplo)
{
  type: 'stats',
  data: {
    ip: '192.168.1.100',
    battery: 85,
    joints: [
      { name: 'HeadYaw', position: 0.1, temperature: 35.2 }
    ]
  }
}
```

## Migración desde Vanilla JS

Esta versión React mantiene 100% de compatibilidad con el protocolo WebSocket original. Los principales cambios incluyen:

1. **Estructura Modular**: Código dividido en componentes reutilizables
2. **Estado Reactivo**: Uso de useState en lugar de variables globales
3. **Event Handlers**: Usando useCallback para optimización
4. **Lifecycle Management**: useEffect para manejo de conexiones y efectos
5. **Hooks Personalizados**: Lógica compleja extraída a hooks reutilizables

## Desarrollo

Para continuar desarrollando:

1. Clona el repositorio
2. Ejecuta `npm install`
3. Ejecuta `npm start`
4. La aplicación se abrirá en tu navegador

## Compatibilidad

- ✅ Navegadores modernos (Chrome, Firefox, Safari, Edge)
- ✅ Dispositivos móviles (iOS, Android)
- ✅ Tablets
- ✅ Escritorio

---

*Desarrollado con React 18 y Hooks modernos*
