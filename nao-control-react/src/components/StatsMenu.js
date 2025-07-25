import React from 'react';
import PropTypes from 'prop-types';
import './StatsMenu.css';

const StatsMenu = ({ isOpen, onClose, stats, isEmbedded = false }) => {
  if (!isOpen) return null;

  const containerClass = isEmbedded ? 'menu embedded' : 'menu active';

  // Función para obtener el estado de la batería
  const getBatteryStatus = () => {
    if (stats?.batteryFull) return ' (Llena)';
    if (stats?.batteryLow) return ' (Baja)';
    return ' (Normal)';
  };

  return (
    <div className={containerClass}>
      <header>
        <h3>Stats</h3>
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
        {stats?.joints && stats.joints.length > 0 && (
          <div className="joints-stats">
            <h4>Articulaciones</h4>
            <table className="stat-joints">
              <thead>
                <tr>
                  <th>Joint</th>
                  <th>Pos</th>
                  <th>Temp</th>
                </tr>
              </thead>
              <tbody>
                {stats.joints.map((joint, index) => (
                  <tr key={joint.name || index}>
                    <td>{joint.name}</td>
                    <td>{joint.position?.toFixed(2) || 'N/A'}</td>
                    <td>{joint.temperature?.toFixed(1) || 'N/A'}°C</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        
        {(!stats?.joints || stats.joints.length === 0) && (
          <p className="no-data">No hay datos de articulaciones disponibles</p>
        )}
      </div>
    </div>
  );
};

StatsMenu.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  isEmbedded: PropTypes.bool,
  stats: PropTypes.shape({
    battery: PropTypes.number,
    batteryIcon: PropTypes.string,
    batteryColor: PropTypes.string,
    batteryLow: PropTypes.bool,
    batteryFull: PropTypes.bool,
    joints: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string,
      position: PropTypes.number,
      temperature: PropTypes.number
    }))
  })
};

export default StatsMenu;
