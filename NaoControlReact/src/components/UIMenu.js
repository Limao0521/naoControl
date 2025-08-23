import React from 'react';
import './UIMenu.css';

const UIMenu = ({ onUIChange, currentUI }) => {
  const uiModes = [
    { id: 'normal', name: 'NORMAL', icon: '🎮', description: 'Control completo con selectores' },
    { id: 'futbol', name: 'FÚTBOL', icon: '⚽', description: 'Modo fútbol con joystick y kick' }
  ];

  return (
    <div className="ui-menu">
      <h3>🎮 Modo de Interfaz</h3>
      <div className="ui-modes">
        {uiModes.map(mode => (
          <button
            key={mode.id}
            className={`ui-mode-btn ${currentUI === mode.id ? 'active' : ''}`}
            onClick={() => onUIChange(mode.id)}
          >
            <div className="ui-mode-icon">{mode.icon}</div>
            <div className="ui-mode-name">{mode.name}</div>
            <div className="ui-mode-desc">{mode.description}</div>
          </button>
        ))}
      </div>
      
      <div className="ui-info">
        <p><strong>Modo Actual:</strong> {uiModes.find(m => m.id === currentUI)?.name || 'NORMAL'}</p>
        <div className="ui-details">
          {currentUI === 'normal' ? (
            <ul>
              <li>• Selectores de modo (Caminar, Cabeza, etc.)</li>
              <li>• Panel de control completo</li>
              <li>• Joystick multimodo</li>
            </ul>
          ) : (
            <ul>
              <li>• Joystick para caminar</li>
              <li>• Botones básicos (Stand, Sit, Autonomous)</li>
              <li>• Botón de KICK con cooldown</li>
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default UIMenu;
