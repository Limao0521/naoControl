import React, { useState } from 'react';
import './VoiceMenu.css';

const VoiceMenu = ({ isOpen, onClose, onSendVoice }) => {
  const [voiceText, setVoiceText] = useState('');

  const handleSend = () => {
    if (voiceText.trim()) {
      onSendVoice(voiceText);
      setVoiceText('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="menu active">
      <header>
        <h3>Voz</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </header>
      <textarea
        className="voice-text"
        placeholder="Texto a hablar"
        value={voiceText}
        onChange={(e) => setVoiceText(e.target.value)}
        onKeyPress={handleKeyPress}
      />
      <button className="menu-btn" onClick={handleSend}>
        Hablar
      </button>
    </div>
  );
};

export default VoiceMenu;
