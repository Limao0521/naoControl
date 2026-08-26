import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import NemotronMenu from './NemotronMenu';
import { nemotronApi } from '../services/nemotronApi';


jest.mock('../services/nemotronApi', () => ({
  nemotronApi: {
    status: jest.fn(), providerStatus: jest.fn(), setProvider: jest.fn(),
  },
}));


beforeEach(() => {
  jest.clearAllMocks();
  nemotronApi.status.mockResolvedValue({
    success: true, interaction_id: 'turn-1', phase: 'ready',
    transcript: 'Quiero que te levantes.',
    response: 'Me levantaré ahora mismo.',
    actions: [{ name: 'set_posture', status: 'completed', reason: null }],
    updated_at_ms: 1234,
  });
  nemotronApi.providerStatus.mockResolvedValue({
    selected: 'nemotron', active: 'nemotron', healthy: true,
    error: '', updated_at_ms: 1234,
  });
  nemotronApi.setProvider.mockResolvedValue({
    selected: 'gemma_local', active: 'nemotron', healthy: true,
    error: '', updated_at_ms: 1235,
  });
});


test('shows what Nemotron heard, answered, and physically executed', async () => {
  render(<NemotronMenu />);

  expect(await screen.findByText('Quiero que te levantes.')).toBeInTheDocument();
  expect(screen.getByText('Me levantaré ahora mismo.')).toBeInTheDocument();
  expect(screen.getByText('set_posture')).toBeInTheDocument();
  expect(screen.getByText('Completada')).toBeInTheDocument();
});


test('shows listening state before a batch transcription exists', async () => {
  nemotronApi.status.mockResolvedValue({
    success: true, interaction_id: 'turn-2', phase: 'listening',
    transcript: '', response: '', actions: [], updated_at_ms: 1235,
  });

  render(<NemotronMenu />);

  expect(await screen.findByText('Escuchando')).toBeInTheDocument();
  expect(screen.getByText('La transcripción aparecerá al soltar el bumper.')).toBeInTheDocument();
});


test('selects Gemma local from the intelligent control panel without exposing endpoint or key', async () => {
  render(<NemotronMenu />);

  const selector = await screen.findByLabelText('Proveedor de inteligencia');
  fireEvent.change(selector, { target: { value: 'gemma_local' } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar proveedor' }));

  await waitFor(() => {
    expect(nemotronApi.setProvider).toHaveBeenCalledWith('gemma_local');
  });
  expect(screen.getByText('Cambio solicitado. Se aplicará antes del siguiente turno.')).toBeInTheDocument();
  expect(screen.queryByLabelText(/url/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
});


test('shows provider activation error while preserving visible active provider', async () => {
  nemotronApi.providerStatus.mockResolvedValue({
    selected: 'gemma_local', active: 'nemotron', healthy: true,
    error: 'Gemma local no responde', updated_at_ms: 1236,
  });

  render(<NemotronMenu />);

  expect(await screen.findByText('Activo: Nemotron NVIDIA')).toBeInTheDocument();
  expect(screen.getByText('Gemma local no responde')).toBeInTheDocument();
});
