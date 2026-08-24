import { createNetworkApi } from './networkApi';

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
  malformedMessage() { this.onmessage?.({ data: '{not-json' }); }
  remoteClose() { this.onclose?.(); }
  send(message) { this.sent.push(message); }
  close() { this.closed = true; }
}

const createApi = (overrides = {}) => createNetworkApi({
  WebSocketImpl: FakeWebSocket,
  locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
  idFactory: () => 'req-1',
  timeoutMs: 1000,
  ...overrides,
});

beforeEach(() => { FakeWebSocket.instances = []; });
afterEach(() => { jest.useRealTimers(); });

test('sends one correlated status request to the NAO control websocket', async () => {
  const pending = createApi().status();
  const socket = FakeWebSocket.instances[0];

  expect(socket.url).toBe('ws://169.254.197.40:6671');
  expect(socket.sent).toEqual([]);
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{
    action: 'networkAdmin', request_id: 'req-1', operation: 'status',
  }]);
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'completed', operation: 'status', data: { state: 'ready' },
  } });

  await expect(pending).resolves.toEqual({
    request_id: 'req-1', status: 'completed', operation: 'status', data: { state: 'ready' },
  });
  expect(socket.closed).toBe(true);
});

test('ignores server info and responses for a different request', async () => {
  const pending = createApi().scan();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.message({ server_info: { version: '2.0.0' } });
  socket.message({ networkAdmin: {
    request_id: 'another-request', status: 'completed', operation: 'scan', data: {},
  } });
  expect(socket.closed).toBe(false);
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'completed', operation: 'scan', data: { services: [] },
  } });
  await expect(pending).resolves.toMatchObject({ operation: 'scan' });
});

test('sends connect credentials only in the single outbound request', async () => {
  const pending = createApi().mutate({
    operation: 'connect', service_id: 'wifi_lab', ssid: 'Laboratorio', passphrase: 'example-only',
  });
  const socket = FakeWebSocket.instances[0];
  socket.open();
  expect(socket.sent.map(JSON.parse)).toEqual([{
    action: 'networkAdmin', request_id: 'req-1', operation: 'connect',
    service_id: 'wifi_lab', ssid: 'Laboratorio', passphrase: 'example-only',
  }]);
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'confirmation_timeout', operation: 'connect', data: {},
  } });
  const result = await pending;
  expect(JSON.stringify(result)).not.toContain('example-only');
});

test('keeps routing metadata authoritative when mutation payload contains collisions', async () => {
  const pending = createApi().mutate({
    action: 'shell', request_id: 'attacker-id', operation: 'disconnect', service_id: 'wifi_lab',
  });
  const socket = FakeWebSocket.instances[0];
  socket.open();

  expect(JSON.parse(socket.sent[0])).toMatchObject({
    action: 'networkAdmin', request_id: 'req-1', operation: 'disconnect',
  });
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'completed', operation: 'disconnect', data: {},
  } });
  await pending;
});

test('reports an indeterminate result when a mutation loses transport after send', async () => {
  const pending = createApi().mutate({ operation: 'disconnect', service_id: 'wifi_lab' });
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.remoteClose();
  await expect(pending).resolves.toEqual({
    request_id: 'req-1', status: 'transport_lost', operation: 'disconnect',
    data: {}, reason: 'connection_lost',
  });
});

test('rejects malformed server data with a generic error', async () => {
  const pending = createApi().profiles();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.malformedMessage();
  await expect(pending).rejects.toThrow('No fue posible contactar el gestor de red.');
});

test('rejects a read request closed before its result', async () => {
  const pending = createApi().status();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.remoteClose();
  await expect(pending).rejects.toThrow('No fue posible contactar el gestor de red.');
});

test('times out and closes a request without reflecting remote content', async () => {
  jest.useFakeTimers();
  const pending = createApi({ timeoutMs: 25 }).status();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  jest.advanceTimersByTime(25);
  await expect(pending).rejects.toThrow('No fue posible contactar el gestor de red.');
  expect(socket.closed).toBe(true);
});

test('rejects an unsafe generated request identifier before opening a socket', async () => {
  const api = createApi({ idFactory: () => 'invalid request id' });
  await expect(api.status()).rejects.toThrow('No fue posible contactar el gestor de red.');
  expect(FakeWebSocket.instances).toHaveLength(0);
});

test('uses wss when the control page is served over https', async () => {
  const pending = createApi({
    locationObject: { protocol: 'https:', hostname: 'nao.local' },
  }).status();
  const socket = FakeWebSocket.instances[0];
  expect(socket.url).toBe('wss://nao.local:6671');
  socket.open();
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'completed', operation: 'status', data: {},
  } });
  await pending;
});

test('reads and saves the PC gateway target through allowlisted operations', async () => {
  const api = createApi();
  const read = api.gatewayTarget();
  let socket = FakeWebSocket.instances[0];
  socket.open();
  expect(JSON.parse(socket.sent[0])).toMatchObject({ operation: 'gateway_target' });
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'completed', operation: 'gateway_target',
    data: { pc_ip: '192.168.10.25' },
  } });
  await expect(read).resolves.toMatchObject({ data: { pc_ip: '192.168.10.25' } });

  const save = api.saveGatewayTarget('192.168.10.30');
  socket = FakeWebSocket.instances[1];
  socket.open();
  expect(JSON.parse(socket.sent[0])).toMatchObject({
    operation: 'set_gateway_target', pc_ip: '192.168.10.30',
  });
  socket.message({ networkAdmin: {
    request_id: 'req-1', status: 'completed', operation: 'set_gateway_target',
    data: { pc_ip: '192.168.10.30' },
  } });
  await save;
});
