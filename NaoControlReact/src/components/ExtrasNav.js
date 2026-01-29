import React from 'react';
import './ExtrasNav.css';

const ExtrasNav = ({ onMenuOpen }) => {
  const extraButtons = [
    { id: 'voice', icon: '🎤', label: 'Voz' },
    { id: 'camera', icon: '📷', label: 'Cámara' },
    { id: 'leds', icon: '💡', label: 'LEDs' },
    { id: 'lang', icon: '🌐', label: 'Idioma' }
  ];

  return (
    <nav className="extras-nav">
      {extraButtons.map(button => (
        <button
          key={button.id}
          className="extra-btn"
          onClick={() => onMenuOpen(button.id)}
          title={button.label}
        >
          {button.icon}
        </button>
      ))}
    </nav>
  );
};

export default ExtrasNav;
