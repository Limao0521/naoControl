import React from 'react';
import useJoystick from '../hooks/useJoystick';
import './Joystick.css';

const Joystick = ({ onMove, mode }) => {
  const {
    baseRef,
    knobRef,
    handleMouseDown,
    handleTouchStart
  } = useJoystick(onMove, mode);

  return (
    <div className="joy-wrapper">
      <div 
        className="joy-base"
        ref={baseRef}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
      >
        <div className="joy-knob" ref={knobRef}></div>
      </div>
    </div>
  );
};

export default Joystick;
