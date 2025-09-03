import React, { useRef, useCallback } from 'react';
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

  const turnLeftIntervalRef = useRef(null);
  const turnRightIntervalRef = useRef(null);

  // Funciones para iniciar el envío continuo de comandos de rotación
  const startTurnLeft = useCallback(() => {
    if (onTurnLeft && !turnLeftIntervalRef.current) {
      // Enviar inmediatamente
      onTurnLeft();
      // Configurar envío continuo cada 500ms (2 veces por segundo)
      turnLeftIntervalRef.current = setInterval(() => {
        onTurnLeft();
      }, 500);
    }
  }, [onTurnLeft]);

  const stopTurnLeft = useCallback(() => {
    if (turnLeftIntervalRef.current) {
      clearInterval(turnLeftIntervalRef.current);
      turnLeftIntervalRef.current = null;
    }
  }, []);

  const startTurnRight = useCallback(() => {
    if (onTurnRight && !turnRightIntervalRef.current) {
      // Enviar inmediatamente
      onTurnRight();
      // Configurar envío continuo cada 500ms (2 veces por segundo)
      turnRightIntervalRef.current = setInterval(() => {
        onTurnRight();
      }, 500);
    }
  }, [onTurnRight]);

  const stopTurnRight = useCallback(() => {
    if (turnRightIntervalRef.current) {
      clearInterval(turnRightIntervalRef.current);
      turnRightIntervalRef.current = null;
    }
  }, []);

  // Cleanup al desmontar el componente
  React.useEffect(() => {
    return () => {
      if (turnLeftIntervalRef.current) {
        clearInterval(turnLeftIntervalRef.current);
      }
      if (turnRightIntervalRef.current) {
        clearInterval(turnRightIntervalRef.current);
      }
    };
  }, []);

  return (
    <div className="joy-wrapper">
      {/* Botón de rotación izquierda */}
      <button 
        className="turn-btn turn-left"
        onMouseDown={startTurnLeft}
        onMouseUp={stopTurnLeft}
        onMouseLeave={stopTurnLeft}
        onTouchStart={startTurnLeft}
        onTouchEnd={stopTurnLeft}
        onTouchCancel={stopTurnLeft}
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
        onMouseDown={startTurnRight}
        onMouseUp={stopTurnRight}
        onMouseLeave={stopTurnRight}
        onTouchStart={startTurnRight}
        onTouchEnd={stopTurnRight}
        onTouchCancel={stopTurnRight}
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
