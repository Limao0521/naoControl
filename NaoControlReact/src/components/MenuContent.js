import React from 'react';
import VoiceMenu from './VoiceMenu';
import CameraMenu from './CameraMenu';
import LedsMenu from './LedsMenu';
import StatsMenu from './StatsMenu';
import SettingsMenu from './LanguageMenu';
import './MenuContent.css';

const MenuContent = ({ 
  activeMenu, 
  onSendVoice, 
  onSetLed, 
  onLedOff, 
  stats, 
  onLanguageChange,
  onVolumeChange,
  onRequestStats 
}) => {
  if (!activeMenu) return null;

  const renderMenuContent = () => {
    switch (activeMenu) {
      case 'voice':
        return (
          <VoiceMenu 
            isOpen={true}
            onClose={() => {}} // No necesitamos cerrar desde aquí
            onSendVoice={onSendVoice}
            isEmbedded={true}
          />
        );
      case 'camera':
        return (
          <CameraMenu 
            isOpen={true}
            onClose={() => {}}
            isEmbedded={true}
          />
        );
      case 'leds':
        return (
          <LedsMenu 
            isOpen={true}
            onClose={() => {}}
            onSetLed={onSetLed}
            onLedOff={onLedOff}
            isEmbedded={true}
          />
        );
      case 'stats':
        return (
          <StatsMenu 
            isOpen={true}
            onClose={() => {}}
            stats={stats}
            onRequestStats={onRequestStats}
            isEmbedded={true}
          />
        );
      case 'lang':
        return (
          <SettingsMenu 
            isOpen={true}
            onClose={() => {}}
            onLanguageChange={onLanguageChange}
            onVolumeChange={onVolumeChange}
            isEmbedded={true}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="menu-content">
      {renderMenuContent()}
    </div>
  );
};

export default MenuContent;
