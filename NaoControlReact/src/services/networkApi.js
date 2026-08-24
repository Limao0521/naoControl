const DEFAULT_BASE_URL = 'http://127.0.0.1:6675';
const REQUEST_TIMEOUT_MS = 50000;


export const createNetworkApi = (baseUrl = DEFAULT_BASE_URL) => {
  const request = async (path, options = {}) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        cache: 'no-store',
        credentials: 'omit',
        ...options,
        signal: controller.signal,
        headers: {
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
          ...(options.headers || {}),
        },
      });
      if (!response.ok) {
        throw new Error('broker request failed');
      }
      const payload = await response.json();
      if (!payload || typeof payload !== 'object' || !payload.status) {
        throw new Error('invalid broker response');
      }
      return payload;
    } catch (_error) {
      throw new Error('No fue posible contactar el gestor de red.');
    } finally {
      clearTimeout(timeout);
    }
  };

  const query = (operation) => request('/network/query', {
    method: 'POST',
    body: JSON.stringify({ operation }),
  });

  return {
    status: () => request('/network/status'),
    scan: () => query('scan'),
    profiles: () => query('profiles'),
    mutate: (payload) => request('/network/operation', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  };
};


export const networkApi = createNetworkApi();
