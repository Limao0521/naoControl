import React from 'react';
import './ModePanel.css';

const ModePanel = ({ currentMode, onModeChange }) => {
  const modes = [
    { id: 'walk', label: 'Caminata' },
    { id: 'larm', label: 'Brazo Izq.' },
    { id: 'rarm', label: 'Brazo Der.' },
    { id: 'head', label: 'Cabeza' }
  ];

  return (
    <section className="mode-panel">
      {modes.map(mode => (
        <button
          key={mode.id}
          className={`mode-btn ${currentMode === mode.id ? 'active' : ''}`}
          onClick={() => onModeChange(mode.id)}
        >
          {mode.label}
        </button>
      ))}
    </section>
  );
};

export default ModePanel;
