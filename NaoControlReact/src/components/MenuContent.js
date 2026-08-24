import React from 'react';
import VoiceMenu from './VoiceMenu';
import CameraMenu from './CameraMenu';
import LedsMenu from './LedsMenu';
import SettingsMenu from './LanguageMenu';
import UIMenu from './UIMenu';
import EmotesMenu from './EmotesMenu';
import NetworkMenu from './NetworkMenu';
import './MenuContent.css';

const MenuContent = ({ 
  activeMenu, 
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
  if (!activeMenu) return null;

  const renderMenuContent = () => {
    switch (activeMenu) {
      case 'voice':
        return (
          <VoiceMenu 
            isOpen={true}
            onClose={() => {}} // No necesitamos cerrar desde aquí
            onSendVoice={onSendVoice}
            sendMessage={sendMessage}
            lastMessage={lastMessage}
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
      case 'ui':
        return (
          <UIMenu 
            onUIChange={onUIChange}
            currentUI={currentUI}
          />
        );
      case 'emotes':
        return (
          <EmotesMenu 
            isOpen={true}
            onClose={() => {}}
            onEmote={onEmote}
            isEmbedded={true}
          />
        );
      case 'network':
        return <NetworkMenu />;
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
