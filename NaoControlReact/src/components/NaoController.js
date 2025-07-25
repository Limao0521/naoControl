import React, { useState, useEffect, useCallback, useRef } from 'react';
import useWebSocket from '../hooks/useWebSocket';
import ModePanel from './ModePanel';
import ControlButtons from './ControlButtons';
import Joystick from './Joystick';
import SidePanel from './SidePanel';
import OrientationMessage from './OrientationMessage';
import './NaoController.css';

const NaoController = () => {
  const [currentMode, setCurrentMode] = useState('walk');
  const [activeMenu, setActiveMenu] = useState(null);
  const [robotStats, setRobotStats] = useState({
    ip: '',
    battery: 0,
    batteryLow: false,
    batteryFull: false,
    joints: []
  });
  const [hostIP, setHostIP] = useState('');
  const [autonomousEnabled, setAutonomousEnabled] = useState(false);
  const sendIntervalRef = useRef(null);
  const currentValuesRef = useRef({ x: 0, y: 0, mode: 'walk' });

  const { sendMessage, lastMessage, isConnected } = useWebSocket(6671);

  // Detectar IP del host
  useEffect(() => {
    const currentHost = window.location.hostname;
    setHostIP(currentHost);
  }, []);

  // Manejar mensajes entrantes
  useEffect(() => {
    if (lastMessage) {
      // Procesar mensajes de batería
      if (lastMessage.battery !== undefined) {
        setRobotStats(prev => ({
          ...prev,
          battery: lastMessage.battery,
          batteryLow: lastMessage.low || false,
          batteryFull: lastMessage.full || false
        }));
        console.log('[BATTERY] Actualizado:', lastMessage.battery + '%', 
                   'Low:', lastMessage.low, 'Full:', lastMessage.full);
      }
      
      // Otros mensajes del robot
      if (lastMessage.type === 'stats') {
        setRobotStats(prev => ({ ...prev, ...lastMessage.data }));
      }
    }
  }, [lastMessage]);

  // Manejar cambio de modo
  const handleModeChange = useCallback((mode) => {
    setCurrentMode(mode);
    console.log('[MODE] Cambiado a', mode);
  }, []);

  // Función para enviar comandos (como en el código original)
  const sendCmd = useCallback(() => {
    if (!sendMessage) return;

    const { x: vx, y: vy, mode } = currentValuesRef.current;

    switch (mode) {
      case 'walk':
        // Para walk: adelante = vy local; lateral = vx local
        sendMessage({ action: 'walk', vx: vy, vy: vx, wz: 0 });
        break;
      case 'larm':
        sendMessage({ action: 'move', joint: 'LShoulderPitch', value: vy });
        sendMessage({ action: 'move', joint: 'LShoulderRoll', value: vx });
        break;
      case 'rarm':
        sendMessage({ action: 'move', joint: 'RShoulderPitch', value: vy });
        sendMessage({ action: 'move', joint: 'RShoulderRoll', value: vx });
        break;
      case 'head':
        sendMessage({ action: 'move', joint: 'HeadPitch', value: vy });
        sendMessage({ action: 'move', joint: 'HeadYaw', value: vx });
        break;
      default:
        break;
    }

    console.log('[JOY]', mode, vx.toFixed(2), vy.toFixed(2));
  }, [sendMessage]);

  // Iniciar envío continuo (15 FPS como en el original)
  const startSend = useCallback(() => {
    if (!sendIntervalRef.current) {
      sendIntervalRef.current = setInterval(sendCmd, 1000 / 15); // 15 FPS
    }
  }, [sendCmd]);

  // Detener envío continuo
  const stopSend = useCallback(() => {
    if (sendIntervalRef.current) {
      clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }

    const { mode } = currentValuesRef.current;
    
    if (mode === 'walk') {
      // 1) Detener movimiento
      currentValuesRef.current = { x: 0, y: 0, mode };
      if (sendMessage) {
        sendMessage({ action: 'walk', vx: 0, vy: 0, wz: 0 });
        console.log('[JOY] walk STOP');
        
        // 2) Volver a Stand
        sendMessage({ action: 'posture', value: 'Stand' });
        console.log('[JOY] STAND enviado tras parada');
      }
    } else {
      console.log('[JOY] hold position (mode=' + mode + ')');
    }
  }, [sendMessage]);

  // Manejar movimientos del joystick (como en el original)
  const handleJoystickMove = useCallback(({ x, y, mode, isStop }) => {
    if (isStop) {
      stopSend();
      return;
    }

    // Actualizar valores actuales
    currentValuesRef.current = { x, y, mode };

    // Si no estaba enviando, iniciar envío continuo
    if (!sendIntervalRef.current) {
      startSend();
    }
  }, [startSend, stopSend]);

  // Comandos de postura
  const handleStand = useCallback(() => {
    if (sendMessage({ action: 'posture', value: 'Stand' })) {
      console.log('[UI] STAND enviado');
    }
  }, [sendMessage]);

  const handleSit = useCallback(() => {
    if (sendMessage({ action: 'posture', value: 'Sit' })) {
      console.log('[UI] SIT enviado');
    }
  }, [sendMessage]);

  // Comando Autonomous Life
  const handleAutonomous = useCallback(() => {
    const newState = !autonomousEnabled;
    setAutonomousEnabled(newState);
    
    if (sendMessage({ action: 'autonomous', enable: newState })) {
      console.log('[UI] Autonomous Life →', newState ? 'ON' : 'OFF');
    }
  }, [sendMessage, autonomousEnabled]);

  // Funciones de los menús
  const handleMenuSelect = useCallback((menuId) => {
    setActiveMenu(menuId);
    console.log('[UI] Seleccionar menú', menuId);
  }, []);

  const handleSendVoice = useCallback((text) => {
    if (sendMessage({ action: 'say', text })) {
      console.log('[UI] say →', text);
    }
  }, [sendMessage]);

  const handleSetLed = useCallback((group, { r, g, b }) => {
    if (sendMessage({ action: 'led', group, r, g, b })) {
      console.log('[UI] led-on', group, r.toFixed(2), g.toFixed(2), b.toFixed(2));
    }
  }, [sendMessage]);

  const handleLedOff = useCallback((group) => {
    if (sendMessage({ action: 'led', group, r: 0, g: 0, b: 0 })) {
      console.log('[UI] led-off', group);
    }
  }, [sendMessage]);

  const handleLanguageChange = useCallback((language) => {
    if (sendMessage({ action: 'language', value: language })) {
      console.log('[UI] setLanguage →', language);
    }
  }, [sendMessage]);

  // Comando de volumen
  const handleVolumeChange = useCallback((volume) => {
    if (sendMessage({ action: 'volume', value: volume })) {
      console.log('[UI] setVolume →', volume);
    }
  }, [sendMessage]);

  // Aplicar configuraciones guardadas cuando se conecte
  useEffect(() => {
    if (isConnected) {
      // Aplicar volumen guardado
      const savedVolume = localStorage.getItem('nao-volume');
      if (savedVolume) {
        const volume = parseInt(savedVolume);
        handleVolumeChange(volume);
        console.log('[SETTINGS] Volumen aplicado desde localStorage:', volume);
      }
      
      // Aplicar idioma guardado si es necesario
      const savedLanguage = localStorage.getItem('nao-tts-language');
      if (savedLanguage) {
        console.log('[SETTINGS] Idioma guardado:', savedLanguage);
      }
    }
  }, [isConnected, handleVolumeChange]);

  // Solicitar estado de batería
  const requestBatteryStatus = useCallback(() => {
    if (sendMessage({ action: 'getBattery' })) {
      console.log('[UI] getBattery solicitado');
    }
  }, [sendMessage]);

  // Enfocar en el body para teclado (opcional)
  useEffect(() => {
    document.body.focus();
  }, []);

  // Cleanup del intervalo al desmontar
  useEffect(() => {
    return () => {
      if (sendIntervalRef.current) {
        clearInterval(sendIntervalRef.current);
      }
    };
  }, []);

  // Solicitar estado de batería cada 10 segundos
  useEffect(() => {
    const batteryInterval = setInterval(() => {
      if (isConnected) {
        requestBatteryStatus();
      }
    }, 10000); // Cada 10 segundos

    // Solicitar inmediatamente al conectar
    if (isConnected) {
      requestBatteryStatus();
    }

    return () => clearInterval(batteryInterval);
  }, [isConnected, requestBatteryStatus]);

  // Función para obtener el icono de batería según el estado
  const getBatteryIcon = useCallback(() => {
    const { battery, batteryLow, batteryFull } = robotStats;
    
    if (batteryFull) {
      return '🔋'; // Batería llena (95%+)
    } else if (batteryLow) {
      return '🪫'; // Batería baja (<20%)
    } else if (battery >= 60) {
      return '🔋'; // Batería alta (60%+)
    } else if (battery >= 40) {
      return '🔋'; // Batería media (40-59%)
    } else if (battery >= 20) {
      return '🔋'; // Batería media-baja (20-39%)
    } else {
      return '🪫'; // Batería muy baja (<20%)
    }
  }, [robotStats]);

  // Función para obtener el color de la batería
  const getBatteryColor = useCallback(() => {
    const { batteryLow, batteryFull } = robotStats;
    
    if (batteryFull) {
      return '#4CAF50'; // Verde para llena
    } else if (batteryLow) {
      return '#FF5722'; // Rojo para baja
    } else {
      return '#FFC107'; // Amarillo para normal
    }
  }, [robotStats]);

  return (
    <div className="nao-controller">
      {/* Orientation Message */}
      <OrientationMessage />
      
      {/* Side Panel */}
      <SidePanel
        activeMenu={activeMenu}
        onMenuSelect={handleMenuSelect}
        onSendVoice={handleSendVoice}
        onSetLed={handleSetLed}
        onLedOff={handleLedOff}
        stats={{
          ...robotStats,
          batteryIcon: getBatteryIcon(),
          batteryColor: getBatteryColor()
        }}
        onLanguageChange={handleLanguageChange}
        onVolumeChange={handleVolumeChange}
      />

      {/* Main Content */}
      <div className="main-content">
        <main className="nes-pad">
          {/* Status Info */}
          <div className="control-status">
            <div className="status-ip">
              IP: {hostIP || 'N/A'}
            </div>
            <div className="status-connection">
              {isConnected ? '🟢 Conectado' : '🔴 Desconectado'}
            </div>
            <div className="status-battery" style={{ color: getBatteryColor() }}>
              {getBatteryIcon()} {robotStats.battery || 'N/A'}%
            </div>
          </div>

          <ModePanel 
            currentMode={currentMode} 
            onModeChange={handleModeChange} 
          />
          
          <ControlButtons 
            onStand={handleStand} 
            onSit={handleSit}
            onAutonomous={handleAutonomous}
            autonomousEnabled={autonomousEnabled}
          />
          
          <Joystick 
            onMove={handleJoystickMove} 
            mode={currentMode} 
          />
        </main>
      </div>
    </div>
  );
};

export default NaoController;
