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

const PROVIDER_LABELS = {
  nemotron: 'Nemotron NVIDIA',
  gemma_local: 'Gemma local',
};


const NemotronMenu = () => {
  const [state, setState] = useState({
    phase: 'idle', transcript: '', response: '', actions: [],
  });
  const [connected, setConnected] = useState(true);
  const [provider, setProvider] = useState({
    selected: 'nemotron', active: '', healthy: false, error: '', updated_at_ms: 0,
  });
  const [providerChoice, setProviderChoice] = useState('nemotron');
  const [providerTouched, setProviderTouched] = useState(false);
  const [providerBusy, setProviderBusy] = useState(false);
  const [providerMessage, setProviderMessage] = useState('');

  useEffect(() => {
    let active = true;
    let requestPending = false;
    const refresh = async () => {
      if (requestPending) return;
      requestPending = true;
      try {
        const [next, nextProvider] = await Promise.all([
          nemotronApi.status(), nemotronApi.providerStatus(),
        ]);
        if (active) {
          setState(next);
          setProvider(nextProvider);
          if (!providerTouched) setProviderChoice(nextProvider.selected);
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
  }, [providerTouched]);

  const saveProvider = async (event) => {
    event.preventDefault();
    setProviderBusy(true);
    setProviderMessage('');
    try {
      const next = await nemotronApi.setProvider(providerChoice);
      setProvider(next);
      setProviderTouched(false);
      setProviderMessage('Cambio solicitado. Se aplicará antes del siguiente turno.');
    } catch (_error) {
      setProviderMessage('No fue posible cambiar el proveedor.');
    } finally {
      setProviderBusy(false);
    }
  };

  return (
    <section className="nemotron-menu">
      <h3>Sistema inteligente</h3>
      <div className={`nemotron-phase phase-${state.phase}`} role="status">
        <span className="nemotron-indicator" aria-hidden="true" />
        <strong>{connected ? PHASE_LABELS[state.phase] : 'Sin conexión'}</strong>
      </div>

      <form className="nemotron-card provider-card" onSubmit={saveProvider}>
        <h4>Proveedor</h4>
        <label htmlFor="intelligence-provider">Proveedor de inteligencia</label>
        <select
          id="intelligence-provider"
          value={providerChoice}
          onChange={(event) => {
            setProviderChoice(event.target.value);
            setProviderTouched(true);
          }}
          disabled={providerBusy}
        >
          <option value="nemotron">Nemotron NVIDIA</option>
          <option value="gemma_local">Gemma local</option>
        </select>
        <p>Seleccionado: {PROVIDER_LABELS[provider.selected]}</p>
        <p>Activo: {provider.active ? PROVIDER_LABELS[provider.active] : 'ninguno'}</p>
        <p className={provider.healthy ? 'provider-ok' : 'provider-offline'}>
          {provider.healthy ? 'Proveedor disponible' : 'Proveedor no disponible'}
        </p>
        {provider.error && <p className="provider-error">{provider.error}</p>}
        <button type="submit" disabled={providerBusy || !connected}>
          {providerBusy ? 'Guardando…' : 'Guardar proveedor'}
        </button>
        {providerMessage && <p role="status">{providerMessage}</p>}
      </form>

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
