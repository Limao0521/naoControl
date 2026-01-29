import React from 'react';
import { FaMicrophone, FaCamera, FaLightbulb, FaGlobe } from 'react-icons/fa';
import './ExtrasNav.css';

const ExtrasNav = ({ onMenuOpen }) => {
  const extraButtons = [
    { id: 'voice', icon: FaMicrophone, label: 'Voz' },
    { id: 'camera', icon: FaCamera, label: 'Cámara' },
    { id: 'leds', icon: FaLightbulb, label: 'LEDs' },
    { id: 'lang', icon: FaGlobe, label: 'Idioma' }
  ];

  return (
    <nav className="extras-nav">
      {extraButtons.map(button => {
        const IconComponent = button.icon;
        return (
          <button
            key={button.id}
            className="extra-btn"
            onClick={() => onMenuOpen(button.id)}
            title={button.label}
          >
            <IconComponent size={24} color="#FFFFFF" />
          </button>
        );
      })}
    </nav>
  );
};

export default ExtrasNav;
