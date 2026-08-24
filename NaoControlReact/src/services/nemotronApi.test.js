import { createNemotronApi } from './nemotronApi';


class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.sent = [];
    this.closed = false;
    FakeWebSocket.instances.push(this);
  }

  open() { this.onopen?.(); }
  message(payload) { this.onmessage?.({ data: JSON.stringify(payload) }); }
  send(message) { this.sent.push(message); }
  close() { this.closed = true; }
}


beforeEach(() => { FakeWebSocket.instances = []; });


test('reads the bounded latest Nemotron turn from the NAO control socket', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
    timeoutMs: 1000,
  });
  const pending = api.status();
  const socket = FakeWebSocket.instances[0];

  expect(socket.url).toBe('ws://169.254.197.40:6671');
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{ action: 'nemotronStatus' }]);
  socket.message({ nemotronStatus: {
    success: true, interaction_id: 'turn-1', phase: 'ready',
    transcript: 'Hola NAO', response: 'Hola, ¿cómo estás?',
    actions: [{ name: 'set_posture', status: 'completed', reason: null }],
    updated_at_ms: 1234,
  } });

  await expect(pending).resolves.toMatchObject({
    phase: 'ready', transcript: 'Hola NAO', response: 'Hola, ¿cómo estás?',
  });
  expect(socket.closed).toBe(true);
});


test('rejects malformed interaction state instead of rendering it', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
    timeoutMs: 1000,
  });
  const pending = api.status();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.message({ nemotronStatus: {
    success: true, interaction_id: 'turn-1', phase: 'forged',
    transcript: 'x', response: 'y', actions: [], updated_at_ms: 1234,
  } });

  await expect(pending).rejects.toThrow('Estado Nemotron no disponible.');
});
