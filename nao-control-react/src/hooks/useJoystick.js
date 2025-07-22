import { useState, useRef, useCallback, useEffect } from 'react';

const useJoystick = (onMove, mode = 'walk') => {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isActive, setIsActive] = useState(false);
  const baseRef = useRef(null);
  const knobRef = useRef(null);
  const touchIdRef = useRef(null);
  
  const dimensionsRef = useRef({ R: 0, Rk: 0, LIM: 0 });

  const recalculateDimensions = useCallback(() => {
    if (baseRef.current && knobRef.current) {
      const R = baseRef.current.clientWidth / 2;
      const Rk = knobRef.current.clientWidth / 2;
      const LIM = R - Rk;
      dimensionsRef.current = { R, Rk, LIM };
    }
  }, []);

  const setKnobPosition = useCallback((dx, dy) => {
    if (knobRef.current) {
      knobRef.current.style.transform = `translate(-50%, -50%) translate(${dx}px, ${dy}px)`;
    }
  }, []);

  const centerKnob = useCallback(() => {
    if (knobRef.current) {
      knobRef.current.style.transition = 'transform .1s';
      setKnobPosition(0, 0);
      setTimeout(() => {
        if (knobRef.current) {
          knobRef.current.style.transition = '';
        }
      }, 120);
    }
  }, [setKnobPosition]);

  const handleMove = useCallback((clientX, clientY) => {
    if (!isActive || !baseRef.current) return;

    const rect = baseRef.current.getBoundingClientRect();
    const { R, LIM } = dimensionsRef.current;
    
    let dx = clientX - rect.left - R;
    let dy = clientY - rect.top - R;
    
    const distance = Math.hypot(dx, dy);
    const factor = distance > LIM ? LIM / distance : 1;
    
    dx *= factor;
    dy *= factor;
    
    setKnobPosition(dx, dy);
    
    const nx = dx / LIM;
    const ny = -dy / LIM;
    
    const vx = Math.abs(nx) > 0.05 ? nx : 0;
    const vy = Math.abs(ny) > 0.05 ? ny : 0;
    
    setPosition({ x: vx, y: vy });
    
    if (onMove) {
      onMove({ x: vx, y: vy, mode });
    }
  }, [isActive, onMove, mode, setKnobPosition]);

  const startMove = useCallback((clientX, clientY, touchId = null) => {
    setIsActive(true);
    touchIdRef.current = touchId;
    recalculateDimensions();
    handleMove(clientX, clientY);
  }, [handleMove, recalculateDimensions]);

  const stopMove = useCallback(() => {
    setIsActive(false);
    touchIdRef.current = null;
    centerKnob();
    setPosition({ x: 0, y: 0 });
    
    if (onMove) {
      onMove({ x: 0, y: 0, mode, isStop: true });
    }
  }, [centerKnob, onMove, mode]);

  // Mouse events
  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    startMove(e.clientX, e.clientY);
  }, [startMove]);

  const handleMouseMove = useCallback((e) => {
    if (isActive) {
      handleMove(e.clientX, e.clientY);
    }
  }, [isActive, handleMove]);

  const handleMouseUp = useCallback(() => {
    if (isActive) {
      stopMove();
    }
  }, [isActive, stopMove]);

  // Touch events
  const handleTouchStart = useCallback((e) => {
    e.preventDefault();
    if (e.touches.length > 0) {
      const touch = e.touches[0];
      startMove(touch.clientX, touch.clientY, touch.identifier);
    }
  }, [startMove]);

  const handleTouchMove = useCallback((e) => {
    if (!isActive) return;
    
    for (let i = 0; i < e.touches.length; i++) {
      const touch = e.touches[i];
      if (touch.identifier === touchIdRef.current) {
        handleMove(touch.clientX, touch.clientY);
        break;
      }
    }
  }, [isActive, handleMove]);

  const handleTouchEnd = useCallback(() => {
    if (isActive) {
      stopMove();
    }
  }, [isActive, stopMove]);

  useEffect(() => {
    const handleWindowMouseMove = (e) => handleMouseMove(e);
    const handleWindowMouseUp = () => handleMouseUp();
    const handleWindowTouchMove = (e) => handleTouchMove(e);
    const handleWindowTouchEnd = () => handleTouchEnd();

    window.addEventListener('mousemove', handleWindowMouseMove);
    window.addEventListener('mouseup', handleWindowMouseUp);
    window.addEventListener('touchmove', handleWindowTouchMove, { passive: false });
    window.addEventListener('touchend', handleWindowTouchEnd);

    return () => {
      window.removeEventListener('mousemove', handleWindowMouseMove);
      window.removeEventListener('mouseup', handleWindowMouseUp);
      window.removeEventListener('touchmove', handleWindowTouchMove);
      window.removeEventListener('touchend', handleWindowTouchEnd);
    };
  }, [handleMouseMove, handleMouseUp, handleTouchMove, handleTouchEnd]);

  useEffect(() => {
    recalculateDimensions();
    const handleResize = () => recalculateDimensions();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [recalculateDimensions]);

  return {
    baseRef,
    knobRef,
    position,
    isActive,
    handleMouseDown,
    handleTouchStart
  };
};

export default useJoystick;
