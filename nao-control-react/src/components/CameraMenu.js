import React from 'react';
import './CameraMenu.css';

const CameraMenu = ({ isOpen, onClose, cameraUrl }) => {
  if (!isOpen) return null;

  const defaultCameraUrl = cameraUrl || "http://<IP_NAO>:8080/video.mjpeg";

  return (
    <div className="menu active">
      <header>
        <h3>Cámara</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </header>
      <img 
        className="camera-feed" 
        src={defaultCameraUrl} 
        alt="Video MJPEG"
        onError={(e) => {
          e.target.style.display = 'none';
          // Mostrar mensaje de error si no se puede cargar la imagen
        }}
      />
      <p className="camera-info">
        URL: {defaultCameraUrl}
      </p>
    </div>
  );
};

export default CameraMenu;
