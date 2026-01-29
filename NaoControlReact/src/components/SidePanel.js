import React from 'react';
import MenuContent from './MenuContent';
import './SidePanel.css';

const SidePanel = ({ 
  activeMenu, 
  onMenuSelect, 
  onSendVoice, 
  onSetLed, 
  onLedOff, 
  onLanguageChange,
  onVolumeChange,
  onUIChange,
  onEmote,
  currentUI 
}) => {
  const menuItems = [
    { id: 'voice', icon: '🎤', label: 'Voz' },
    { id: 'camera', icon: '📷', label: 'Cámara' },
    { id: 'leds', icon: '💡', label: 'LEDs' },
    { id: 'emotes', icon: '💃', label: 'Emotes' },
    { id: 'ui', icon: '🎮', label: 'UI Mode' },
    { id: 'lang', icon: '⚙️', label: 'Settings' }
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
            onLanguageChange={onLanguageChange}
            onVolumeChange={onVolumeChange}
            onUIChange={onUIChange}
            onEmote={onEmote}
            currentUI={currentUI}
          />
        )}
      </div>
    </div>
  );
};

export default SidePanel;
