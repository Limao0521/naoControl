import React, { useState } from 'react';
import './LanguageMenu.css';

const LanguageMenu = ({ isOpen, onClose, onLanguageChange, isEmbedded = false }) => {
  const [selectedLanguage, setSelectedLanguage] = useState('English');

  const languages = [
    { value: 'English', label: 'English' },
    { value: 'French', label: 'French' },
    { value: 'German', label: 'German' },
    { value: 'Spanish', label: 'Spanish' },
    { value: 'Italian', label: 'Italian' }
  ];

  const handleLanguageChange = () => {
    onLanguageChange(selectedLanguage);
  };

  if (!isOpen) return null;

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  return (
    <div className={containerClass}>
      <header>
        <h3>Idioma TTS</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>
      
      <div className="language-controls">
        <label htmlFor="tts-lang">Idioma:</label>
        <select 
          id="tts-lang"
          value={selectedLanguage}
          onChange={(e) => setSelectedLanguage(e.target.value)}
        >
          {languages.map(lang => (
            <option key={lang.value} value={lang.value}>
              {lang.label}
            </option>
          ))}
        </select>
        
        <button className="menu-btn" onClick={handleLanguageChange}>
          Cambiar idioma
        </button>
      </div>
    </div>
  );
};

export default LanguageMenu;
