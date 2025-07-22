import React from 'react';
import './ControlButtons.css';

const ControlButtons = ({ onStand, onSit }) => {
  return (
    <section className="center">
      <button className="small-btn" onClick={onStand}>
        STAND
      </button>
      <button className="small-btn" onClick={onSit}>
        SIT
      </button>
    </section>
  );
};

export default ControlButtons;
