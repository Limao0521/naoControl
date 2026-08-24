import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { networkApi } from '../services/networkApi';
import './NetworkMenu.css';


const resultMessage = (result) => {
  switch (result?.status) {
    case 'completed':
      return 'Operación de red completada.';
    case 'confirmation_timeout':
      return 'Confirmación física no recibida; no se cambió la red.';
    case 'transport_lost_after_apply':
      return 'La conexión cambió y se perdió el enlace. Revisa la nueva IP del NAO.';
    case 'rejected':
      return 'El NAO rechazó la operación.';
    default:
      return 'La operación de red falló.';
  }
};


const displayName = (service) => service.Name || service.ServiceId || 'Red sin nombre';


const NetworkMenu = () => {
  const [brokerState, setBrokerState] = useState('loading');
  const [networkState, setNetworkState] = useState(null);
  const [services, setServices] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [selectedService, setSelectedService] = useState(null);
  const [passphrase, setPassphrase] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [pendingAction, setPendingAction] = useState(null);
  const [warningAccepted, setWarningAccepted] = useState(false);

  const refresh = useCallback(async () => {
    setBrokerState('loading');
    try {
      const [statusResult, profileResult] = await Promise.all([
        networkApi.status(),
        networkApi.profiles(),
      ]);
      setNetworkState(statusResult.data || {});
      setProfiles(profileResult.data?.profiles || []);
      setBrokerState('ready');
    } catch (_error) {
      setBrokerState('error');
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onlyManagementPath = useMemo(() => {
    const interfaces = networkState?.interfaces || [];
    const hasEthernet = interfaces.some((item) =>
      String(item.Name || '').toLowerCase().startsWith('eth')
    );
    const connected = (networkState?.services || []).filter((item) =>
      ['ready', 'online'].includes(String(item.State || '').toLowerCase())
    );
    return !hasEthernet && connected.length <= 1;
  }, [networkState]);

  const scan = async () => {
    setBusy(true);
    setMessage('');
    try {
      const result = await networkApi.scan();
      setServices(result.data?.services || []);
    } catch (_error) {
      setMessage('No fue posible escanear redes.');
    } finally {
      setBusy(false);
    }
  };

  const connect = async (event) => {
    event.preventDefault();
    if (!selectedService || busy) return;
    const payload = {
      operation: 'connect',
      service_id: selectedService.ServiceId,
      ssid: selectedService.Name || '',
      passphrase,
    };
    setPassphrase('');
    setBusy(true);
    setMessage('Espera la indicación del NAO y mantén el sensor trasero por 3 segundos.');
    try {
      const result = await networkApi.mutate(payload);
      setMessage(resultMessage(result));
      if (result.status === 'completed') await refresh();
    } catch (_error) {
      setMessage('No fue posible contactar el gestor de red.');
    } finally {
      setBusy(false);
    }
  };

  const requestProfileAction = (operation, profile) => {
    setWarningAccepted(false);
    setPendingAction({ operation, profile });
  };

  const confirmProfileAction = async () => {
    if (!pendingAction || !warningAccepted || busy) return;
    const { operation, profile } = pendingAction;
    setBusy(true);
    setMessage('Espera la indicación del NAO y mantén el sensor trasero por 3 segundos.');
    try {
      const result = await networkApi.mutate({
        operation,
        service_id: profile.ServiceId,
      });
      setMessage(resultMessage(result));
      setPendingAction(null);
      if (result.status === 'completed') await refresh();
    } catch (_error) {
      setMessage('No fue posible contactar el gestor de red.');
    } finally {
      setBusy(false);
    }
  };

  if (brokerState === 'error') {
    return (
      <section className="network-menu">
        <h3>Red</h3>
        <p className="network-error">Gestor de red no disponible</p>
        <p>Inicia el gateway del PC con el broker habilitado.</p>
        <button type="button" onClick={refresh}>Reintentar</button>
      </section>
    );
  }

  return (
    <section className="network-menu">
      <h3>Gestión de red</h3>
      {brokerState === 'loading' ? (
        <p>Consultando el NAO…</p>
      ) : (
        <>
          <div className="network-summary">
            <strong>Estado: {networkState?.state || 'desconocido'}</strong>
            {(networkState?.interfaces || []).map((item) => (
              <span key={`${item.Name}-${item.Address}`}>
                {item.Name}: {item.Address || item.IPv4?.Address || 'sin IP'}
              </span>
            ))}
          </div>

          <button type="button" onClick={scan} disabled={busy}>
            Escanear redes
          </button>

          <div className="network-list" aria-label="Redes disponibles">
            {services.map((service) => (
              <div className="network-card" key={service.ServiceId}>
                <div>
                  <strong>{displayName(service)}</strong>
                  <span>Señal: {service.Strength ?? 'N/A'}%</span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedService(service)}
                  disabled={busy}
                  aria-label={`Conectar a ${displayName(service)}`}
                >
                  Conectar
                </button>
              </div>
            ))}
          </div>

          {selectedService && (
            <form className="network-connect-form" onSubmit={connect}>
              <strong>Conectar a {displayName(selectedService)}</strong>
              <label htmlFor="network-passphrase">Contraseña Wi-Fi</label>
              <input
                id="network-passphrase"
                type="password"
                autoComplete="new-password"
                value={passphrase}
                onChange={(event) => setPassphrase(event.target.value)}
                minLength={passphrase ? 8 : undefined}
                maxLength={63}
              />
              <button type="submit" disabled={busy}>Solicitar conexión</button>
            </form>
          )}

          <h4>Perfiles guardados</h4>
          <div className="network-list">
            {profiles.map((profile) => (
              <div className="network-card" key={profile.ServiceId}>
                <strong>{displayName(profile)}</strong>
                <div className="network-actions">
                  <button
                    type="button"
                    onClick={() => requestProfileAction('disconnect', profile)}
                    aria-label={`Desconectar ${displayName(profile)}`}
                  >
                    Desconectar
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => requestProfileAction('forget', profile)}
                    aria-label={`Eliminar ${displayName(profile)}`}
                  >
                    Eliminar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {pendingAction && (
        <div className="network-warning" role="alert">
          <strong>
            {onlyManagementPath
              ? 'Esta puede ser la única conexión disponible del NAO.'
              : 'Esta operación cambiará la conectividad del NAO.'}
          </strong>
          <label>
            <input
              type="checkbox"
              checked={warningAccepted}
              onChange={(event) => setWarningAccepted(event.target.checked)}
            />
            Entiendo que puedo perder la conexión
          </label>
          <div className="network-actions">
            <button type="button" onClick={() => setPendingAction(null)}>Cancelar</button>
            <button
              type="button"
              className="danger"
              disabled={!warningAccepted || busy}
              onClick={confirmProfileAction}
            >
              {pendingAction.operation === 'forget'
                ? 'Confirmar eliminación'
                : 'Confirmar desconexión'}
            </button>
          </div>
        </div>
      )}

      {message && <p className="network-message" role="status">{message}</p>}
    </section>
  );
};


export default NetworkMenu;
