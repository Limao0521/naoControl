import React from 'react';
import { FaGamepad, FaFootballBall } from 'react-icons/fa';
import './UIMenu.css';

const UIMenu = ({ onUIChange, currentUI }) => {
  const uiModes = [
    { id: 'normal', name: 'NORMAL', icon: FaGamepad, description: 'Control completo con selectores' },
    { id: 'futbol', name: 'FÚTBOL', icon: FaFootballBall, description: 'Modo fútbol con joystick y kick' }
  ];

  return (
    <div className="ui-menu">
      <h3>Modo de Interfaz</h3>
      <div className="ui-modes">
        {uiModes.map(mode => {
          const IconComponent = mode.icon;
          return (
            <button
              key={mode.id}
              className={`ui-mode-btn ${currentUI === mode.id ? 'active' : ''}`}
              onClick={() => onUIChange(mode.id)}
            >
              <div className="ui-mode-icon"><IconComponent size={48} color="#FFFFFF" /></div>
              <div className="ui-mode-name">{mode.name}</div>
              <div className="ui-mode-desc">{mode.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default UIMenu;
