import { createNetworkApi } from './networkApi';


const okJson = (payload) => ({
  ok: true,
  status: 200,
  json: async () => payload,
});


afterEach(() => {
  jest.restoreAllMocks();
});


test('sends connect credentials only to the loopback broker', async () => {
  global.fetch = jest.fn().mockResolvedValue(
    okJson({ status: 'confirmation_timeout', operation: 'connect', data: {} })
  );
  const api = createNetworkApi();

  await api.mutate({
    operation: 'connect',
    service_id: 'wifi_lab',
    passphrase: 'example-only',
  });

  expect(fetch.mock.calls[0][0]).toBe(
    'http://127.0.0.1:6675/network/operation'
  );
  expect(fetch.mock.calls[0][1].cache).toBe('no-store');
  expect(JSON.parse(fetch.mock.calls[0][1].body).passphrase).toBe('example-only');
});


test('uses read-only routes for status scan and profiles', async () => {
  global.fetch = jest.fn().mockResolvedValue(
    okJson({ status: 'completed', operation: 'status', data: {} })
  );
  const api = createNetworkApi();

  await api.status();
  await api.scan();
  await api.profiles();

  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    'http://127.0.0.1:6675/network/status',
    'http://127.0.0.1:6675/network/query',
    'http://127.0.0.1:6675/network/query',
  ]);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ operation: 'scan' });
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ operation: 'profiles' });
});


test('returns a generic error without reflecting response content', async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 500,
    json: async () => ({ detail: 'example-only' }),
  });
  const api = createNetworkApi();

  await expect(api.status()).rejects.toThrow('No fue posible contactar el gestor de red.');
});

