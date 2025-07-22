import React, { useState } from 'react';
import './LanguageMenu.css';

const LanguageMenu = ({ isOpen, onClose, onLanguageChange }) => {
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

  return (
    <div className="menu active">
      <header>
        <h3>Idioma TTS</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
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
