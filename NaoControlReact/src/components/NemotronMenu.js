import React, { useEffect, useState } from 'react';

import { nemotronApi } from '../services/nemotronApi';
import './NemotronMenu.css';


const PHASE_LABELS = {
  idle: 'En espera',
  listening: 'Escuchando',
  processing: 'Procesando audio e imagen',
  responding: 'Preparando respuesta',
  ready: 'Listo',
  error: 'Error',
};

const ACTION_LABELS = {
  pending: 'Pendiente',
  accepted: 'Aceptada',
  completed: 'Completada',
  rejected: 'Rechazada',
  failed: 'Fallida',
  unknown: 'Desconocida',
};


const NemotronMenu = () => {
  const [state, setState] = useState({
    phase: 'idle', transcript: '', response: '', actions: [],
  });
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    let active = true;
    let requestPending = false;
    const refresh = async () => {
      if (requestPending) return;
      requestPending = true;
      try {
        const next = await nemotronApi.status();
        if (active) {
          setState(next);
          setConnected(true);
        }
      } catch (_error) {
        if (active) setConnected(false);
      } finally {
        requestPending = false;
      }
    };
    refresh();
    const interval = setInterval(refresh, 1000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <section className="nemotron-menu">
      <h3>Nemotron</h3>
      <div className={`nemotron-phase phase-${state.phase}`} role="status">
        <span className="nemotron-indicator" aria-hidden="true" />
        <strong>{connected ? PHASE_LABELS[state.phase] : 'Sin conexión'}</strong>
      </div>

      <article className="nemotron-card">
        <h4>Escuché</h4>
        <p>{state.transcript || (
          state.phase === 'listening'
            ? 'La transcripción aparecerá al soltar el bumper.'
            : 'Todavía no hay una transcripción.'
        )}</p>
      </article>

      <article className="nemotron-card">
        <h4>Respondí</h4>
        <p>{state.response || 'Todavía no hay una respuesta.'}</p>
      </article>

      <article className="nemotron-card">
        <h4>Acciones</h4>
        {state.actions.length ? (
          <ul className="nemotron-actions">
            {state.actions.map((action, index) => (
              <li key={`${action.name}-${index}`}>
                <strong>{action.name}</strong>
                <span>{ACTION_LABELS[action.status]}</span>
                {action.reason && <small>{action.reason}</small>}
              </li>
            ))}
          </ul>
        ) : <p>No se solicitaron acciones físicas.</p>}
      </article>
    </section>
  );
};


export default NemotronMenu;
