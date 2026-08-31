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


test('reads selected and active intelligent provider from the control socket', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
    timeoutMs: 1000,
  });

  const pending = api.providerStatus();
  const socket = FakeWebSocket.instances[0];
  socket.open();

  expect(socket.sent.map(JSON.parse)).toEqual([
    { action: 'intelligenceProviderStatus' },
  ]);
  socket.message({ intelligenceProviderStatus: {
    success: true, selected: 'gemma_local', active: 'nemotron',
    healthy: true, error: '', language: 'es', selection_version: 2,
    gemma_base_url: 'http://192.168.23.1:8080/v1', updated_at_ms: 1234,
  } });

  await expect(pending).resolves.toEqual({
    selected: 'gemma_local', active: 'nemotron', healthy: true,
    error: '', language: 'es', gemma_base_url: 'http://192.168.23.1:8080/v1', updated_at_ms: 1234,
  });
});


test('saves only an allowlisted provider identifier', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
    timeoutMs: 1000,
  });

  const pending = api.setProvider('gemma_local');
  const socket = FakeWebSocket.instances[0];
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{
    action: 'setIntelligenceProvider', provider: 'gemma_local',
  }]);
  socket.message({ setIntelligenceProvider: {
    success: true, selected: 'gemma_local', active: 'nemotron',
    healthy: true, error: '', language: 'es', selection_version: 2,
    gemma_base_url: 'http://192.168.23.1:8080/v1', updated_at_ms: 1234,
  } });

  await expect(pending).resolves.toMatchObject({ selected: 'gemma_local' });
  await expect(api.setProvider('http://attacker.test')).rejects.toThrow(
    'Proveedor inteligente no disponible.'
  );
  expect(FakeWebSocket.instances).toHaveLength(1);
});


test('saves only Spanish or English as intelligent response language', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
    timeoutMs: 1000,
  });

  const pending = api.setLanguage('en');
  const socket = FakeWebSocket.instances[0];
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{
    action: 'setIntelligenceLanguage', language: 'en',
  }]);
  socket.message({ setIntelligenceLanguage: {
    success: true, selected: 'gemma_local', active: 'nemotron',
    healthy: true, error: '', language: 'en',
    gemma_base_url: 'http://192.168.23.1:8080/v1', updated_at_ms: 1234,
  } });

  await expect(pending).resolves.toMatchObject({ language: 'en' });
  await expect(api.setLanguage('French')).rejects.toThrow(
    'Proveedor inteligente no disponible.'
  );
});


test('sends only a private Gemma host IP and keeps the endpoint syntax fixed', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '192.168.23.66' },
    timeoutMs: 1000,
  });

  const pending = api.setGemmaEndpoint('192.168.23.1');
  const socket = FakeWebSocket.instances[0];
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{
    action: 'setGemmaEndpoint', gemma_ip: '192.168.23.1',
  }]);
  socket.message({ setGemmaEndpoint: {
    success: true, selected: 'nemotron', active: '', healthy: false,
    error: '', language: 'es', gemma_base_url: 'http://192.168.23.1:8080/v1',
    updated_at_ms: 1234,
  } });

  await expect(pending).resolves.toMatchObject({
    gemma_base_url: 'http://192.168.23.1:8080/v1',
  });
  await expect(api.setGemmaEndpoint('8.8.8.8')).rejects.toThrow(
    'Proveedor inteligente no disponible.'
  );
});


test('saves provider, language, and optional Gemma IP in one request', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '192.168.23.66' },
    timeoutMs: 1000,
  });
  const pending = api.configure('gemma_local', 'en', '192.168.23.1');
  const socket = FakeWebSocket.instances[0];
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{
    action: 'configureIntelligence', provider: 'gemma_local',
    language: 'en', gemma_ip: '192.168.23.1',
  }]);
  socket.message({ configureIntelligence: {
    success: true, selected: 'gemma_local', active: '', healthy: false,
    error: '', language: 'en', gemma_base_url: 'http://192.168.23.1:8080/v1',
    updated_at_ms: 1234,
  } });

  await expect(pending).resolves.toMatchObject({
    selected: 'gemma_local', language: 'en',
  });
});


test('surfaces an old robot backend instead of hiding the provider rejection', async () => {
  const api = createNemotronApi({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: 'http:', hostname: '192.168.23.66' },
    timeoutMs: 1000,
  });

  const pending = api.setGemmaEndpoint('192.168.23.1');
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.message({ setGemmaEndpoint: {
    success: false, error: 'invalid_request',
  } });

  await expect(pending).rejects.toThrow(
    'El NAO ejecuta una versión anterior; reinicia los servicios.'
  );
});
