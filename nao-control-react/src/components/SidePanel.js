import React from 'react';
import MenuContent from './MenuContent';
import './SidePanel.css';

const SidePanel = ({ 
  activeMenu, 
  onMenuSelect, 
  onSendVoice, 
  onSetLed, 
  onLedOff, 
  stats, 
  onLanguageChange 
}) => {
  const menuItems = [
    { id: 'voice', icon: '🎤', label: 'Voz' },
    { id: 'camera', icon: '📷', label: 'Cámara' },
    { id: 'leds', icon: '💡', label: 'LEDs' },
    { id: 'stats', icon: '📊', label: 'Estadísticas' },
    { id: 'lang', icon: '🌐', label: 'Idioma' }
  ];

  return (
    <div className="side-panel">
      <div className="side-panel-nav">
        {menuItems.map(item => (
          <button
            key={item.id}
            className={`side-nav-btn ${activeMenu === item.id ? 'active' : ''}`}
            onClick={() => onMenuSelect(item.id === activeMenu ? null : item.id)}
            title={item.label}
          >
            {item.icon}
          </button>
        ))}
      </div>
      
      <div className="side-panel-content">
        {activeMenu && (
          <MenuContent
            activeMenu={activeMenu}
            onSendVoice={onSendVoice}
            onSetLed={onSetLed}
            onLedOff={onLedOff}
            stats={stats}
            onLanguageChange={onLanguageChange}
          />
        )}
      </div>
    </div>
  );
};

export default SidePanel;
