import React from 'react';
import './EmotesMenu.css';

const EmotesMenu = ({ isOpen, onClose, onEmote, isEmbedded = false }) => {
  if (!isOpen) return null;

  // Agrega o modifica acciones fácilmente aquí
  const emoteActions = [
    { action: 'dance_1', label: 'Baile 1' },
    { action: 'dance_2', label: 'Baile 2' },
    { action: 'dance_3', label: 'Baile 3' },
    { action: 'wave', label: 'Saludo' },
    { action: 'clap', label: 'Aplauso' }
  ];

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  return (
    <div className={containerClass}>
      <header>
        <h3>Emotes</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>

      <div className="emotes-grid">
        {emoteActions.map((item) => (
          <button
            key={item.action}
            className="menu-btn emote-btn"
            onClick={() => onEmote(item.action)}
            title={item.action}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default EmotesMenu;
