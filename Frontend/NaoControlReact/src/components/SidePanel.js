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
  onLanguageChange,
  onVolumeChange,
  onRequestStats,
  onUIChange,
  currentUI 
}) => {
  const menuItems = [
    { id: 'voice', icon: '🎤', label: 'Voz' },
    { id: 'camera', icon: '📷', label: 'Cámara' },
    { id: 'leds', icon: '💡', label: 'LEDs' },
    { id: 'stats', icon: '📊', label: 'Stats' },
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
            stats={stats}
            onLanguageChange={onLanguageChange}
            onVolumeChange={onVolumeChange}
            onRequestStats={onRequestStats}
            onUIChange={onUIChange}
            currentUI={currentUI}
          />
        )}
      </div>
    </div>
  );
};

export default SidePanel;
