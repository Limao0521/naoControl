import React from 'react';
import './EmotesMenu.css';

const EmotesMenu = ({ isOpen, onClose, onEmote, isEmbedded = false }) => {
  if (!isOpen) return null;

  const emoteActions = [
    { action: 'saxophone', label: 'Saxophone' },
    { action: 'taichichua', label: 'Tai Chi' },
    { action: 'gangnamstyle', label: 'Gangnam Style' },
    { action: 'elephant', label: 'Elephant' },
    { action: 'disco', label: 'Disco' },
    { action: 'macarena', label: 'Macarena' }
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
