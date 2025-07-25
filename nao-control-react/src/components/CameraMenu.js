import React, { useState, useEffect } from 'react';
import './CameraMenu.css';

const CameraMenu = ({ isOpen, onClose, cameraUrl, isEmbedded = false }) => {
  const [currentCameraUrl, setCurrentCameraUrl] = useState('');
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    if (cameraUrl) {
      setCurrentCameraUrl(cameraUrl);
    } else {
      // Detectar la IP actual y construir la URL de la cámara
      const currentHost = window.location.hostname;
      const autoDetectedUrl = `http://${currentHost}:8080/video.mjpeg`;
      setCurrentCameraUrl(autoDetectedUrl);
    }
    setImageError(false);
  }, [cameraUrl]);

  const handleImageError = () => {
    setImageError(true);
  };

  if (!isOpen) return null;

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  return (
    <div className={containerClass}>
      <header>
        <h3>Cámara</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>
      
      {!imageError ? (
        <img 
          className="camera-feed" 
          src={currentCameraUrl} 
          alt="Video MJPEG"
          onError={handleImageError}
        />
      ) : (
        <div className="camera-error">
          <p>❌ No se puede conectar a la cámara</p>
          <p>Verifique que el robot esté encendido y conectado</p>
          <button 
            className="retry-btn" 
            onClick={() => setImageError(false)}
          >
            🔄 Reintentar
          </button>
        </div>
      )}
    </div>
  );
};

export default CameraMenu;
