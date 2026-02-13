import React, { useState, useEffect } from 'react';
import './VoiceMenu.css';

const VoiceMenu = ({ isOpen, onClose, onSendVoice, sendMessage, lastMessage, isEmbedded = false }) => {
  const [voiceText, setVoiceText] = useState('');
  const [conversationStatus, setConversationStatus] = useState({
    running: false,
    elapsed_time: 0,
    provider: '',
    errors: []
  });

  // Procesar mensajes entrantes del servidor
  useEffect(() => {
    if (lastMessage && lastMessage.conversationStatus) {
      setConversationStatus({
        running: lastMessage.conversationStatus.running || false,
        elapsed_time: lastMessage.conversationStatus.elapsed_time || 0,
        provider: lastMessage.conversationStatus.provider || '',
        errors: lastMessage.conversationStatus.errors || []
      });
    }
  }, [lastMessage]);

  // Solicitar estado de la conversación cada 2 segundos
  useEffect(() => {
    if (!isOpen) return;

    const getStatus = () => {
      if (sendMessage) {
        sendMessage({ action: "getConversationStatus" });
      }
    };

    // Primera consulta
    getStatus();

    // Consultas periódicas
    const interval = setInterval(getStatus, 2000);

    return () => clearInterval(interval);
  }, [isOpen, sendMessage]);

  const handleStartConversation = () => {
    if (sendMessage) {
      sendMessage({ 
        action: "startConversation", 
        provider: "groq" 
      });
    }
  };

  const handleStopConversation = () => {
    if (sendMessage) {
      sendMessage({ action: "stopConversation" });
    }
  };

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

  // Formatear tiempo de conversación
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={containerClass}>
      <header>
        <h3>Voz</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>

      {/* Estado de conversación */}
      <div className="conversation-status">
        <div className={`status-indicator ${conversationStatus.running ? 'active' : 'inactive'}`}>
          <span className="status-dot"></span>
          <span className="status-text">
            {conversationStatus.running 
              ? `Conversación activa (${formatTime(conversationStatus.elapsed_time)})` 
              : 'Conversación detenida'}
          </span>
        </div>
        {conversationStatus.provider && (
          <span className="provider-info">Proveedor: {conversationStatus.provider}</span>
        )}
        {conversationStatus.errors.length > 0 && (
          <div className="conversation-errors">
            {conversationStatus.errors.map((error, idx) => (
              <div key={idx} className="error-msg">{error}</div>
            ))}
          </div>
        )}
      </div>

      {/* Botones de control de conversación */}
      <div className="conversation-controls">
        <button 
          className="menu-btn start-btn" 
          onClick={handleStartConversation}
          disabled={conversationStatus.running}
        >
          Start
        </button>
        <button 
          className="menu-btn stop-btn" 
          onClick={handleStopConversation}
          disabled={!conversationStatus.running}
        >
          Stop
        </button>
      </div>

      {/* Entrada de texto para hablar */}
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
