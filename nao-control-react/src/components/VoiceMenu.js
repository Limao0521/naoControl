import React, { useState } from 'react';
import './VoiceMenu.css';

const VoiceMenu = ({ isOpen, onClose, onSendVoice, isEmbedded = false }) => {
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

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  return (
    <div className={containerClass}>
      <header>
        <h3>Voz</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
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
