import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import NemotronMenu from './NemotronMenu';
import { nemotronApi } from '../services/nemotronApi';


jest.mock('../services/nemotronApi', () => ({
  nemotronApi: {
    status: jest.fn(), providerStatus: jest.fn(), setProvider: jest.fn(),
    setLanguage: jest.fn(), setGemmaEndpoint: jest.fn(),
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
    error: '', language: 'es', updated_at_ms: 1234,
    gemma_base_url: '',
  });
  nemotronApi.setProvider.mockResolvedValue({
    selected: 'gemma_local', active: 'nemotron', healthy: true,
    error: '', language: 'es', updated_at_ms: 1235,
    gemma_base_url: 'http://192.168.23.1:8080/v1',
  });
  nemotronApi.setLanguage.mockResolvedValue({
    selected: 'gemma_local', active: 'nemotron', healthy: true,
    error: '', language: 'en', updated_at_ms: 1236,
    gemma_base_url: 'http://192.168.23.1:8080/v1',
  });
  nemotronApi.setGemmaEndpoint.mockResolvedValue({
    selected: 'nemotron', active: 'nemotron', healthy: true,
    error: '', language: 'es', gemma_base_url: 'http://192.168.23.1:8080/v1',
    updated_at_ms: 1235,
  });
});


test('shows what Nemotron heard, answered, and physically executed', async () => {
  render(<NemotronMenu />);

  expect(await screen.findByText('Quiero que te levantes.')).toBeInTheDocument();
  expect(screen.getByText('Me levantaré ahora mismo.')).toBeInTheDocument();
  expect(screen.getByText('set_posture')).toBeInTheDocument();
  expect(screen.getByText('Completada')).toBeInTheDocument();
  expect(screen.getByText(/cliente cloud dentro del NAO \(sin PC\)/i)).toBeInTheDocument();
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


test('configures Gemma LAN endpoint from the intelligent control panel without exposing its key', async () => {
  render(<NemotronMenu />);

  const selector = await screen.findByLabelText('Proveedor de inteligencia');
  expect(screen.getByRole('option', { name: 'Gemma LAN autenticado' })).toBeInTheDocument();
  fireEvent.change(selector, { target: { value: 'gemma_local' } });
  const endpoint = screen.getByLabelText('Endpoint de Gemma LAN');
  fireEvent.change(endpoint, { target: { value: 'http://192.168.23.1:8080/v1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar configuración' }));

  await waitFor(() => {
    expect(nemotronApi.setGemmaEndpoint).toHaveBeenCalledWith('http://192.168.23.1:8080/v1');
    expect(nemotronApi.setProvider).toHaveBeenCalledWith('gemma_local');
  });
  expect(screen.getByText('Cambio solicitado. Se aplicará antes del siguiente turno.')).toBeInTheDocument();
  expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
});


test('selects English for model responses and NAO speech from the intelligent panel', async () => {
  render(<NemotronMenu />);

  const selector = await screen.findByLabelText('Idioma de respuesta');
  fireEvent.change(selector, { target: { value: 'en' } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar configuración' }));

  await waitFor(() => {
    expect(nemotronApi.setLanguage).toHaveBeenCalledWith('en');
  });
  expect(screen.getByText(/idioma y voz del robot/i)).toBeInTheDocument();
});


test('shows provider activation error while preserving visible active provider', async () => {
  nemotronApi.providerStatus.mockResolvedValue({
    selected: 'gemma_local', active: 'nemotron', healthy: true,
    error: 'Gemma local no responde', language: 'es', updated_at_ms: 1236,
    gemma_base_url: 'http://192.168.23.1:8080/v1',
  });

  render(<NemotronMenu />);

  expect(await screen.findByText('Activo: Nemotron NVIDIA')).toBeInTheDocument();
  expect(screen.getByText('Gemma local no responde')).toBeInTheDocument();
});
