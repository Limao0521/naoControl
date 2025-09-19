import React from 'react';
import PropTypes from 'prop-types';
import './StatsMenu.css';

const StatsMenu = ({ isOpen, onClose, stats, onRequestStats, isEmbedded = false }) => {
  if (!isOpen) return null;

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  // Función para obtener el estado de la batería
  const getBatteryStatus = () => {
    if (stats?.batteryFull) return ' (Llena)';
    if (stats?.batteryLow) return ' (Baja)';
    return ' (Normal)';
  };

  // Procesar datos de temperaturas y ángulos para crear lista de articulaciones
  const processJointData = () => {
    if (!stats?.temperatures || !stats?.angles) return [];
    
    const jointData = [];
    
    // Combinar datos de temperaturas y ángulos
    const tempNames = Object.keys(stats.temperatures);
    const angleNames = Object.keys(stats.angles);
    
    // Usar los nombres de las articulaciones (que generalmente coinciden)
    const allJointNames = [...new Set([...tempNames, ...angleNames])];
    
    allJointNames.forEach(jointName => {
      jointData.push({
        name: jointName,
        temperature: stats.temperatures[jointName] || null,
        angle: stats.angles[jointName] || null
      });
    });
    
    return jointData.sort((a, b) => a.name.localeCompare(b.name));
  };

  const jointData = processJointData();

  return (
    <div className={containerClass}>
      <header>
        <h3>Telemetria</h3>
        {!isEmbedded && <button className="close-btn" onClick={onClose}>✕</button>}
      </header>
      
      <div className="stats-info">
        {/* Información de batería */}
        <div className="battery-stats">
          <h4>Batería</h4>
          <div className="battery-info" style={{ color: stats?.batteryColor || '#FFC107' }}>
            <span className="battery-icon">{stats?.batteryIcon || '🔋'}</span>
            <span className="battery-level">{stats?.battery || 'N/A'}%</span>
            <span className="battery-status">
              {getBatteryStatus()}
            </span>
          </div>
        </div>

        {/* Información de articulaciones */}        
        {jointData && jointData.length > 0 && (
          <div className="joints-stats">
            <h4>🤖 Articulaciones ({jointData.length})</h4>
            <div className="joints-container">
              <table className="stat-joints">
                <thead>
                  <tr>
                    <th>Articulación</th>
                    <th>Ángulo (rad)</th>
                    <th>Temp (°C)</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {jointData.map((joint, index) => {
                    const temp = joint.temperature;
                    
                    // Determinar estado de temperatura
                    let tempStatus = '✅';
                    let tempColor = '#4caf50';
                    
                    if (temp > 70) {
                      tempStatus = '🔥';
                      tempColor = '#ff5722';
                    } else if (temp > 50) {
                      tempStatus = '⚠️';
                      tempColor = '#ff9800';
                    }
                    
                    return (
                      <tr key={joint.name || index}>
                        <td className="joint-name">{joint.name}</td>
                        <td className="joint-angle">
                          {joint.angle !== null ? joint.angle.toFixed(3) : 'N/A'}
                        </td>
                        <td className="joint-temp" style={{ color: tempColor }}>
                          {joint.temperature !== null ? joint.temperature.toFixed(1) : 'N/A'}
                        </td>
                        <td className="joint-status">{tempStatus}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
        
        {/* Resumen de temperaturas */}
        {stats?.temperatures && (
          <div className="temperature-summary">
            <h4>🌡️ Resumen Térmico</h4>
            <div className="temp-stats">
              {(() => {
                const temps = Object.values(stats.temperatures).filter(t => t !== null);
                if (temps.length === 0) return <p>No hay datos de temperatura</p>;
                
                const avgTemp = temps.reduce((a, b) => a + b, 0) / temps.length;
                const maxTemp = Math.max(...temps);
                const minTemp = Math.min(...temps);
                const hotJoints = temps.filter(t => t > 70).length;
                
                return (
                  <div className="temp-overview">
                    <div className="temp-stat">
                      <span className="label">Promedio:</span>
                      <span className="value">{avgTemp.toFixed(1)}°C</span>
                    </div>
                    <div className="temp-stat">
                      <span className="label">Máxima:</span>
                      <span className="value" style={{ color: maxTemp > 70 ? '#ff5722' : '#4caf50' }}>
                        {maxTemp.toFixed(1)}°C
                      </span>
                    </div>
                    <div className="temp-stat">
                      <span className="label">Mínima:</span>
                      <span className="value">{minTemp.toFixed(1)}°C</span>
                    </div>
                    {hotJoints > 0 && (
                      <div className="temp-stat warning">
                        <span className="label">⚠️ Calientes:</span>
                        <span className="value">{hotJoints} articulaciones</span>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          </div>
        )}
        
        {(!jointData || jointData.length === 0) && (
          <div className="no-data">
            <p>No hay datos de articulaciones disponibles</p>
            <small>
              {onRequestStats ? (
                <button 
                  className="stats-request-btn" 
                  onClick={onRequestStats}
                >
                  Solicitar Stats
                </button>
              ) : (
                'Abre el menú "Stats" para solicitar información del robot'
              )}
            </small>
          </div>
        )}
      </div>
    </div>
  );
};

StatsMenu.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onRequestStats: PropTypes.func,
  isEmbedded: PropTypes.bool,
  stats: PropTypes.shape({
    battery: PropTypes.number,
    batteryIcon: PropTypes.string,
    batteryColor: PropTypes.string,
    batteryLow: PropTypes.bool,
    batteryFull: PropTypes.bool,
    // Nuevo formato de datos del backend
    temperatures: PropTypes.objectOf(PropTypes.number),
    angles: PropTypes.objectOf(PropTypes.number),
    // Formato legacy (mantener compatibilidad)
    joints: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      position: PropTypes.number,
      temperature: PropTypes.number
    }))
  })
};

export default StatsMenu;
