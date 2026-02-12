import React from 'react';
import { FaMicrophone, FaCamera, FaLightbulb, FaTheaterMasks, FaGamepad, FaCog } from 'react-icons/fa';
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
  currentUI,
  sendMessage,
  lastMessage
}) => {
  const menuItems = [
    { id: 'voice', icon: FaMicrophone, label: 'Voz' },
    { id: 'camera', icon: FaCamera, label: 'Cámara' },
    { id: 'leds', icon: FaLightbulb, label: 'LEDs' },
    { id: 'emotes', icon: FaTheaterMasks, label: 'Emotes' },
    { id: 'ui', icon: FaGamepad, label: 'UI Mode' },
    { id: 'lang', icon: FaCog, label: 'Settings' }
  ];

  return (
    <div className="side-panel">
      <div className="side-panel-nav">
        {menuItems.map(item => {
          const IconComponent = item.icon;
          return (
            <button
              key={item.id}
              className={`side-nav-btn ${activeMenu === item.id ? 'active' : ''}`}
              onClick={() => onMenuSelect(item.id === activeMenu ? null : item.id)}
              title={item.label}
            >
              <IconComponent size={24} color="#FFFFFF" />
            </button>
          );
        })}
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
            sendMessage={sendMessage}
            lastMessage={lastMessage}
          />
        )}
      </div>
    </div>
  );
};

export default SidePanel;
