import React, { useState, useEffect, useCallback } from 'react';
import useWebSocket from '../hooks/useWebSocket';
import ModePanel from './ModePanel';
import ControlButtons from './ControlButtons';
import Joystick from './Joystick';
import SidePanel from './SidePanel';
import './NaoController.css';

const NaoController = () => {
  const [currentMode, setCurrentMode] = useState('walk');
  const [activeMenu, setActiveMenu] = useState(null);
  const [robotStats, setRobotStats] = useState({
    ip: '',
    battery: 0,
    joints: []
  });

  const { sendMessage, lastMessage } = useWebSocket(6671);

  // Manejar mensajes entrantes
  useEffect(() => {
    if (lastMessage) {
      // Aquí puedes procesar los mensajes recibidos del robot
      if (lastMessage.type === 'stats') {
        setRobotStats(lastMessage.data);
      }
    }
  }, [lastMessage]);

  // Manejar cambio de modo
  const handleModeChange = useCallback((mode) => {
    setCurrentMode(mode);
    console.log('[MODE] Cambiado a', mode);
  }, []);

  // Manejar movimientos del joystick
  const handleJoystickMove = useCallback(({ x, y, mode, isStop }) => {
    if (!sendMessage) return;

    const vx = x;
    const vy = y;

    if (isStop && mode === 'walk') {
      // Para walk, enviar comando de parada
      sendMessage({ action: 'walk', vx: 0, vy: 0, wz: 0 });
      console.log('[JOY] walk STOP');
      return;
    }

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

  // Enfocar en el body para teclado (opcional)
  useEffect(() => {
    document.body.focus();
  }, []);

  return (
    <div className="nao-controller">
      {/* Side Panel */}
      <SidePanel
        activeMenu={activeMenu}
        onMenuSelect={handleMenuSelect}
        onSendVoice={handleSendVoice}
        onSetLed={handleSetLed}
        onLedOff={handleLedOff}
        stats={robotStats}
        onLanguageChange={handleLanguageChange}
      />

      {/* Main Content */}
      <div className="main-content">
        <main className="nes-pad">
          <ModePanel 
            currentMode={currentMode} 
            onModeChange={handleModeChange} 
          />
          
          <ControlButtons 
            onStand={handleStand} 
            onSit={handleSit} 
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
