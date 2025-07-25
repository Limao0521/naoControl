import React, { useState } from 'react';
import PropTypes from 'prop-types';
import './LanguageMenu.css';

const SettingsMenu = ({ isOpen, onClose, onLanguageChange, onVolumeChange, isEmbedded = false }) => {
  const [selectedLanguage, setSelectedLanguage] = useState('English');
  const [volume, setVolume] = useState(50);

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

  const handleVolumeChange = (newVolume) => {
    setVolume(newVolume);
    onVolumeChange(newVolume);
  };

  if (!isOpen) return null;

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  return (
    <div className={containerClass}>
      <header>
        <h3>⚙️ Settings</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>
      
      <div className="settings-controls">
        {/* Idioma TTS */}
        <div className="setting-group">
          <h4>🗣️ Idioma TTS</h4>
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

        {/* Control de Volumen */}
        <div className="setting-group">
          <h4>🔊 Volumen</h4>
          
          <div className="volume-input-group">
            <label htmlFor="volume-number">Volumen:</label>
            <div className="volume-manual-input">
              <input 
                type="number" 
                id="volume-number"
                min="0" 
                max="100" 
                value={volume}
                onChange={(e) => {
                  const newVolume = Math.min(100, Math.max(0, parseInt(e.target.value) || 0));
                  handleVolumeChange(newVolume);
                }}
                className="volume-input"
              />
              <span className="volume-unit">%</span>
            </div>
          </div>
          
          <input 
            type="range" 
            id="volume-slider"
            min="0" 
            max="100" 
            value={volume}
            onChange={(e) => handleVolumeChange(parseInt(e.target.value))}
            className="volume-slider"
          />
          
          <div className="volume-buttons">
            <button 
              className="volume-btn" 
              onClick={() => handleVolumeChange(0)}
              title="Silencio"
            >
              🔇
            </button>
            <button 
              className="volume-btn" 
              onClick={() => handleVolumeChange(50)}
              title="Volumen medio"
            >
              🔉
            </button>
            <button 
              className="volume-btn" 
              onClick={() => handleVolumeChange(100)}
              title="Volumen máximo"
            >
              🔊
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

SettingsMenu.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onLanguageChange: PropTypes.func.isRequired,
  onVolumeChange: PropTypes.func.isRequired,
  isEmbedded: PropTypes.bool,
};

export default SettingsMenu;
