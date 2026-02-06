import React, { useState } from 'react';
import './LedsMenu.css';

const LedsMenu = ({ isOpen, onClose, onSetLed, onLedOff, isEmbedded = false }) => {
  const [selectedGroup, setSelectedGroup] = useState('FaceLeds');
  const [selectedColor, setSelectedColor] = useState('#ff0000');

  // Colores predefinidos para acceso rápido
  const presetColors = [
    { color: '#ff0000', label: 'Rojo' },
    { color: '#00ff00', label: 'Verde' },
    { color: '#0000ff', label: 'Azul' },
    { color: '#ffff00', label: 'Amarillo' },
    { color: '#ff00ff', label: 'Magenta' },
    { color: '#00ffff', label: 'Cian' },
    { color: '#ffffff', label: 'Blanco' },
    { color: '#ffa500', label: 'Naranja' }
  ];

  const ledGroups = [
    // Todos los LEDs
    { value: 'AllLeds', label: 'Todos los LEDs' },
    
    // Orejas
    { value: 'EarLeds', label: 'Ambas Orejas' },
    { value: 'LeftEarLeds', label: 'Oreja Izq.' },
    { value: 'RightEarLeds', label: 'Oreja Der.' },

    // Ojos/Cara
    { value: 'FaceLeds', label: 'Ambos Ojos' },
    { value: 'LeftFaceLeds', label: 'Ojo Izq.' },
    { value: 'RightFaceLeds', label: 'Ojo Der.' },
    
    // Pies
    { value: 'FeetLeds', label: 'Ambos Pies' },
    { value: 'LeftFootLeds', label: 'Pie Izq.' },
    { value: 'RightFootLeds', label: 'Pie Der.' }
  ];

  const handleSetLed = () => {
    const hex = selectedColor;
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    
    onSetLed(selectedGroup, { r, g, b });
  };

  const handleLedOff = () => {
    onLedOff(selectedGroup);
  };

  if (!isOpen) return null;

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  return (
    <div className={containerClass}>
      <header>
        <h3>LEDs</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>
      
      <div className="led-controls">
        <div className="control-section">
          <label htmlFor="led-group">Grupo de LEDs:</label>
          <select 
            id="led-group"
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
          >
            {ledGroups.map(group => (
              <option key={group.value} value={group.value}>
                {group.label}
              </option>
            ))}
          </select>
        </div>
        
        <div className="control-section">
          <label htmlFor="led-color">Color personalizado:</label>
          <input 
            type="color" 
            id="led-color"
            value={selectedColor}
            onChange={(e) => setSelectedColor(e.target.value)}
          />
        </div>
        
        <div className="control-section">
          <label>Colores rápidos:</label>
          <div className="preset-colors">
            {presetColors.map((preset, index) => (
              <button
                key={index}
                className={`color-preset ${selectedColor === preset.color ? 'active' : ''}`}
                style={{ backgroundColor: preset.color }}
                onClick={() => setSelectedColor(preset.color)}
                title={preset.label}
              >
                {preset.color === selectedColor ? '✓' : ''}
              </button>
            ))}
          </div>
        </div>
        
        <div className="led-buttons">
          <button className="menu-btn led-on-btn" onClick={handleSetLed}>
            Encender
          </button>
          <button className="menu-btn led-off-btn" onClick={handleLedOff}>
            Apagar
          </button>
        </div>
      </div>
    </div>
  );
};

export default LedsMenu;
