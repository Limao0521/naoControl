import React from 'react';
import './OrientationMessage.css';

const OrientationMessage = () => {
  return (
    <div className="orientation-overlay">
      <div className="orientation-message">
        <div className="phone-icon">📱</div>
        <h2>Gira tu dispositivo</h2>
        <p>Esta aplicación solo funciona en modo horizontal</p>
        <div className="rotate-icon">🔄</div>
      </div>
    </div>
  );
};

export default OrientationMessage;
