import React from 'react';
import './StatsMenu.css';

const StatsMenu = ({ isOpen, onClose, stats }) => {
  if (!isOpen) return null;

  return (
    <div className="menu active">
      <header>
        <h3>Estadísticas</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </header>
      
      <div className="stats-info">
        <p>IP: <span className="stat-value">{stats?.ip || 'N/A'}</span></p>
        <p>Batería: <span className="stat-value">{stats?.battery || 'N/A'}%</span></p>
        
        {stats?.joints && stats.joints.length > 0 && (
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
                <tr key={index}>
                  <td>{joint.name}</td>
                  <td>{joint.position?.toFixed(2) || 'N/A'}</td>
                  <td>{joint.temperature?.toFixed(1) || 'N/A'}°C</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {(!stats?.joints || stats.joints.length === 0) && (
          <p className="no-data">No hay datos de articulaciones disponibles</p>
        )}
      </div>
    </div>
  );
};

export default StatsMenu;
