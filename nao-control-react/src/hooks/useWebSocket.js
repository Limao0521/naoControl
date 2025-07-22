import { useState, useEffect, useRef, useCallback } from 'react';

const useWebSocket = (port = 6671) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    const host = window.location.hostname;
    const url = `ws://${host}:${port}`;
    
    console.log("[WS] Intentando conexión a", url);
    
    wsRef.current = new WebSocket(url);

    wsRef.current.onopen = () => {
      console.log("[WS] Conectado a", url);
      setIsConnected(true);
    };

    wsRef.current.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        console.log("[WS] Msg recibido:", msg);
        setLastMessage(msg);
      } catch (e) {
        console.warn("[WS] JSON inválido:", evt.data);
      }
    };

    wsRef.current.onerror = (err) => {
      console.error("[WS] Error:", err);
    };

    wsRef.current.onclose = () => {
      console.warn("[WS] Desconectado. Reintentando en 3 s…");
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    };
  }, [port]);

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
  }, []);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    connect,
    disconnect
  };
};

export default useWebSocket;
