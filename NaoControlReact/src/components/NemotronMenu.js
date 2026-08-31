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
  gemma_local: 'Gemma LAN autenticado',
};

const gemmaIpFromEndpoint = (endpoint) => {
  try { return new URL(endpoint).hostname; }
  catch (_error) { return ''; }
};


const NemotronMenu = () => {
  const [state, setState] = useState({
    phase: 'idle', transcript: '', response: '', actions: [],
  });
  const [connected, setConnected] = useState(true);
  const [provider, setProvider] = useState({
    selected: 'nemotron', active: '', healthy: false, error: '', language: 'es',
    gemma_base_url: '',
    updated_at_ms: 0,
  });
  const [providerChoice, setProviderChoice] = useState('nemotron');
  const [providerBusy, setProviderBusy] = useState(false);
  const [providerMessage, setProviderMessage] = useState('');
  const [languageChoice, setLanguageChoice] = useState('es');
  const [gemmaIp, setGemmaIp] = useState('');

  useEffect(() => {
    let active = true;
    let requestPending = false;
    const refresh = async () => {
      if (requestPending) return;
      requestPending = true;
      try {
        const [turnResult, providerResult] = await Promise.allSettled([
          nemotronApi.status(), nemotronApi.providerStatus(),
        ]);
        if (active) {
          if (turnResult.status === 'fulfilled') setState(turnResult.value);
          if (providerResult.status === 'fulfilled') {
            const nextProvider = providerResult.value;
            setProvider(nextProvider);
            setProviderChoice(nextProvider.selected);
            setLanguageChoice(nextProvider.language);
            setGemmaIp(gemmaIpFromEndpoint(nextProvider.gemma_base_url));
          }
          setConnected(providerResult.status === 'fulfilled');
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

  const saveConfiguration = async (event) => {
    event.preventDefault();
    setProviderBusy(true);
    setProviderMessage('');
    try {
      const next = await nemotronApi.configure(
        providerChoice, languageChoice,
        providerChoice === 'gemma_local' ? gemmaIp : '',
      );
      setProvider(next);
      setProviderMessage('Cambio solicitado. Se aplicará antes del siguiente turno.');
    } catch (error) {
      setProviderMessage(error?.message || 'No fue posible cambiar el proveedor.');
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

      <form className="nemotron-card provider-card" onSubmit={saveConfiguration}>
        <h4>Proveedor e idioma</h4>
        <label htmlFor="intelligence-provider">Proveedor de inteligencia</label>
        <select
          id="intelligence-provider"
          value={providerChoice}
          onChange={(event) => {
            setProviderChoice(event.target.value);
          }}
          disabled={providerBusy}
        >
          <option value="nemotron">Nemotron NVIDIA</option>
          <option value="gemma_local">Gemma LAN autenticado</option>
        </select>
        {providerChoice === 'gemma_local' && (
          <>
            <label htmlFor="gemma-server-ip">IP del PC con Gemma</label>
            <input
              id="gemma-server-ip"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              placeholder="192.168.23.1"
              value={gemmaIp}
              onChange={(event) => {
                setGemmaIp(event.target.value);
              }}
              pattern="(?:[0-9]{1,3}\.){3}[0-9]{1,3}"
              maxLength={15}
              disabled={providerBusy}
              required
            />
            <p>
              Se usará http://{gemmaIp || 'IP'}:8080/v1. La clave permanece en el PC gateway.
            </p>
          </>
        )}
        <label htmlFor="intelligence-language">Idioma de respuesta</label>
        <select
          id="intelligence-language"
          value={languageChoice}
          onChange={(event) => {
            setLanguageChoice(event.target.value);
          }}
          disabled={providerBusy}
        >
          <option value="es">Español</option>
          <option value="en">English</option>
        </select>
        <p>Controla el idioma y voz del robot para las respuestas inteligentes.</p>
        <p>Seleccionado: {PROVIDER_LABELS[provider.selected]}</p>
        <p>
          Ejecución: {providerChoice === 'nemotron'
            ? 'cliente cloud dentro del NAO (sin PC)'
            : 'gateway en el PC que aloja o alcanza Gemma'}
        </p>
        <p>Activo: {provider.active ? PROVIDER_LABELS[provider.active] : 'ninguno'}</p>
        <p className={provider.healthy ? 'provider-ok' : 'provider-offline'}>
          {provider.healthy ? 'Proveedor disponible' : 'Proveedor no disponible'}
        </p>
        {provider.error && <p className="provider-error">{provider.error}</p>}
        <button type="submit" disabled={providerBusy || !connected}>
          {providerBusy ? 'Guardando…' : 'Guardar configuración'}
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
        {state.response_latency_ms > 0 && (
          <p><strong>Tiempo hasta iniciar la voz:</strong> {(state.response_latency_ms / 1000).toFixed(2)} s</p>
        )}
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
