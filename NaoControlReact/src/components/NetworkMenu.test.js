import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import NetworkMenu from './NetworkMenu';
import { networkApi } from '../services/networkApi';


jest.mock('../services/networkApi', () => ({
  networkApi: {
    status: jest.fn(),
    scan: jest.fn(),
    profiles: jest.fn(),
    mutate: jest.fn(),
    gatewayTarget: jest.fn(),
    saveGatewayTarget: jest.fn(),
  },
}));


const completed = (operation, data) => ({ status: 'completed', operation, data });


beforeEach(() => {
  jest.clearAllMocks();
  networkApi.status.mockResolvedValue(
    completed('status', {
      state: 'ready',
      interfaces: [{ Name: 'eth0', Address: '169.254.1.2' }],
      services: [],
    })
  );
  networkApi.profiles.mockResolvedValue(completed('profiles', { profiles: [] }));
  networkApi.gatewayTarget.mockResolvedValue(completed('gateway_target', {}));
});


test('shows a clear broker unavailable state', async () => {
  networkApi.status.mockRejectedValue(new Error('offline'));

  render(<NetworkMenu />);

  expect(await screen.findByText('Gestor de red no disponible')).toBeInTheDocument();
});


test('scans networks and clears the password after a connect attempt', async () => {
  networkApi.scan.mockResolvedValue(
    completed('scan', {
      services: [
        {
          ServiceId: 'wifi_lab',
          Name: 'Laboratorio',
          State: 'idle',
          Strength: 72,
          Security: ['psk'],
        },
      ],
    })
  );
  networkApi.mutate.mockResolvedValue({
    status: 'confirmation_timeout',
    operation: 'connect',
    data: {},
  });
  render(<NetworkMenu />);
  await screen.findByText('Estado: ready');

  fireEvent.click(screen.getByRole('button', { name: 'Escanear redes' }));
  expect(await screen.findByText('Laboratorio')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Conectar a Laboratorio' }));
  const password = screen.getByLabelText('Contraseña Wi-Fi');
  fireEvent.change(password, { target: { value: 'example-only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Solicitar conexión' }));

  await waitFor(() => expect(networkApi.mutate).toHaveBeenCalledTimes(1));
  expect(networkApi.mutate).toHaveBeenCalledWith({
    operation: 'connect',
    service_id: 'wifi_lab',
    ssid: 'Laboratorio',
    passphrase: 'example-only',
  });
  expect(password).toHaveValue('');
  expect(
    await screen.findByText('Confirmación física no recibida; no se cambió la red.')
  ).toBeInTheDocument();
});


test('requires explicit warning acknowledgement before disconnecting last path', async () => {
  networkApi.status.mockResolvedValue(
    completed('status', {
      state: 'ready',
      interfaces: [{ Name: 'wlan0', Address: '192.168.1.20' }],
      services: [
        { ServiceId: 'wifi_lab', Name: 'Laboratorio', State: 'ready', Type: 'wifi' },
      ],
    })
  );
  networkApi.profiles.mockResolvedValue(
    completed('profiles', {
      profiles: [
        { ServiceId: 'wifi_lab', Name: 'Laboratorio', State: 'ready', Favorite: true },
      ],
    })
  );
  networkApi.mutate.mockResolvedValue(completed('disconnect', {}));
  render(<NetworkMenu />);
  await screen.findByText('Laboratorio');

  fireEvent.click(screen.getByRole('button', { name: 'Desconectar Laboratorio' }));

  expect(
    screen.getByText('Esta puede ser la única conexión disponible del NAO.')
  ).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Confirmar desconexión' })).toBeDisabled();
  fireEvent.click(screen.getByLabelText('Entiendo que puedo perder la conexión'));
  expect(screen.getByRole('button', { name: 'Confirmar desconexión' })).toBeEnabled();
});


test('explains that the gateway PC is inferred from the control browser', async () => {
  render(<NetworkMenu />);

  expect(await screen.findByText('PC gateway automático')).toBeInTheDocument();
  expect(screen.getByText(/IP del PC que abrió este control/i)).toBeInTheDocument();
  expect(networkApi.gatewayTarget).not.toHaveBeenCalled();
});
