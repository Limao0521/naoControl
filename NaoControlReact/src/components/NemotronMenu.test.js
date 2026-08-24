import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import NemotronMenu from './NemotronMenu';
import { nemotronApi } from '../services/nemotronApi';


jest.mock('../services/nemotronApi', () => ({
  nemotronApi: { status: jest.fn() },
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
