import React from 'react';
import { FaHeart } from 'react-icons/fa';
import PropTypes from 'prop-types';
import './ControlButtons.css';


const ControlButtons = ({ onStand, onSit, onAutonomous, autonomousEnabled }) => {
  return (
    <section className="center">
      <button 
        className={`small-btn autonomous-btn ${autonomousEnabled ? 'active' : ''}`}
        onClick={onAutonomous}
      >
        <FaHeart size={14} />
        <span style={{ marginLeft: '0.5rem' }}>
          {autonomousEnabled ? 'ON' : 'OFF'}
        </span>
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
