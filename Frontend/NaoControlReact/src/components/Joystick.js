import React from 'react';
import PropTypes from 'prop-types';
import useJoystick from '../hooks/useJoystick';
import './Joystick.css';

const Joystick = ({ onMove, mode, onTurnLeft, onTurnRight }) => {
  const {
    baseRef,
    knobRef,
    handleMouseDown,
    handleTouchStart
  } = useJoystick(onMove, mode);

  const handleTurnLeft = () => {
    if (onTurnLeft) {
      onTurnLeft();
    }
  };

  const handleTurnRight = () => {
    if (onTurnRight) {
      onTurnRight();
    }
  };

  return (
    <div className="joy-wrapper">
      {/* Botón de rotación izquierda */}
      <button 
        className="turn-btn turn-left"
        onClick={handleTurnLeft}
        title="Rotar Izquierda"
      >
        ←
      </button>

      <div 
        className="joy-base"
        ref={baseRef}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
      >
        <div className="joy-knob" ref={knobRef}></div>
      </div>

      {/* Botón de rotación derecha */}
      <button 
        className="turn-btn turn-right"
        onClick={handleTurnRight}
        title="Rotar Derecha"
      >
        →
      </button>
    </div>
  );
};

Joystick.propTypes = {
  onMove: PropTypes.func.isRequired,
  mode: PropTypes.string.isRequired,
  onTurnLeft: PropTypes.func,
  onTurnRight: PropTypes.func
};

export default Joystick;
