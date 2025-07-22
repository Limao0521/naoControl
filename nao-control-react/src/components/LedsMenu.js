import React, { useState } from 'react';
import './LedsMenu.css';

const LedsMenu = ({ isOpen, onClose, onSetLed, onLedOff }) => {
  const [selectedGroup, setSelectedGroup] = useState('ChestLeds');
  const [selectedColor, setSelectedColor] = useState('#ff0000');

  const ledGroups = [
    { value: 'ChestLeds', label: 'Pecho' },
    { value: 'FaceLeds', label: 'Cara' },
    { value: 'EarLeds', label: 'Orejas' },
    { value: 'EyeLeds', label: 'Ojos' }
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

  return (
    <div className="menu active">
      <header>
        <h3>LEDs</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </header>
      
      <div className="led-controls">
        <label htmlFor="led-group">Grupo:</label>
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
        
        <label htmlFor="led-color">Color:</label>
        <input 
          type="color" 
          id="led-color"
          value={selectedColor}
          onChange={(e) => setSelectedColor(e.target.value)}
        />
        
        <div className="led-buttons">
          <button className="menu-btn" onClick={handleSetLed}>
            Encender
          </button>
          <button className="menu-btn" onClick={handleLedOff}>
            Apagar
          </button>
        </div>
      </div>
    </div>
  );
};

export default LedsMenu;
