import React from 'react';
import PropTypes from 'prop-types';
import './ControlButtons.css';


const ControlButtons = ({ onStand, onSit, onAutonomous, autonomousEnabled }) => {
  return (
    <section className="center">
      <button 
        className={`small-btn autonomous-btn ${autonomousEnabled ? 'active' : ''}`}
        onClick={onAutonomous}
      >
        {autonomousEnabled ? '💗 ON' : '💗 OFF'}
      </button>
      <button className="small-btn" onClick={onStand}>
        STAND
      </button>
      <button className="small-btn" onClick={onSit}>
        SIT
      </button>
    </section>
  );
};


ControlButtons.propTypes = {
  onStand: PropTypes.func.isRequired,
  onSit: PropTypes.func.isRequired,
  onAutonomous: PropTypes.func.isRequired,
  autonomousEnabled: PropTypes.bool.isRequired,
};

export default ControlButtons;
