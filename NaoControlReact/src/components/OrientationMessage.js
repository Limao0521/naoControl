import React from 'react';
import { FaMobileAlt, FaSync } from 'react-icons/fa';
import './OrientationMessage.css';

const OrientationMessage = () => {
  return (
    <div className="orientation-overlay">
      <div className="orientation-message">
        <div className="phone-icon"><FaMobileAlt size={64} color="#FFFFFF" /></div>
        <h2>Gira tu dispositivo</h2>
        <p>Esta aplicación solo funciona en modo horizontal</p>
        <div className="rotate-icon"><FaSync size={48} color="#FFFFFF" /></div>
      </div>
    </div>
  );
};

export default OrientationMessage;
