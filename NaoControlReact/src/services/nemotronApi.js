const DEFAULT_TIMEOUT_MS = 3000;
const PHASES = new Set(['idle', 'listening', 'processing', 'responding', 'ready', 'error']);
const ACTION_STATUSES = new Set([
  'pending', 'accepted', 'completed', 'rejected', 'failed', 'unknown',
]);
const ERROR_MESSAGE = 'Estado Nemotron no disponible.';
const PROVIDER_ERROR_MESSAGE = 'Proveedor inteligente no disponible.';
const PROVIDERS = new Set(['nemotron', 'gemma_local']);
const LANGUAGES = new Set(['es', 'en']);


const invalid = () => new Error(ERROR_MESSAGE);
const invalidProvider = () => new Error(PROVIDER_ERROR_MESSAGE);

const validPrivateIpv4 = (value) => {
  try {
    const octets = value.split('.').map(Number);
    if (octets.length !== 4
      || octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)) return false;
    return octets[0] === 10
      || (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31)
      || (octets[0] === 192 && octets[1] === 168)
      || (octets[0] === 169 && octets[1] === 254);
  } catch (_error) {
    return false;
  }
};


const normalize = (raw) => {
  if (!raw || raw.success !== true || !PHASES.has(raw.phase)) throw invalid();
  if (typeof raw.interaction_id !== 'string' || raw.interaction_id.length > 64) throw invalid();
  if (typeof raw.transcript !== 'string' || raw.transcript.length > 2000) throw invalid();
  if (typeof raw.response !== 'string' || raw.response.length > 2000) throw invalid();
  if (!Array.isArray(raw.actions) || raw.actions.length > 16) throw invalid();
  const actions = raw.actions.map((action) => {
    if (!action || typeof action.name !== 'string' || action.name.length > 64) throw invalid();
    if (!ACTION_STATUSES.has(action.status)) throw invalid();
    if (action.reason !== null && typeof action.reason !== 'string') throw invalid();
    return { name: action.name, status: action.status, reason: action.reason };
  });
  return {
    success: true,
    interaction_id: raw.interaction_id,
    phase: raw.phase,
    transcript: raw.transcript,
    response: raw.response,
    actions,
    updated_at_ms: Number.isFinite(raw.updated_at_ms) ? raw.updated_at_ms : 0,
  };
};


const normalizeProvider = (raw) => {
  if (!raw || raw.success !== true) throw invalidProvider();
  if (!PROVIDERS.has(raw.selected)) throw invalidProvider();
  if (raw.active !== '' && !PROVIDERS.has(raw.active)) throw invalidProvider();
  if (typeof raw.healthy !== 'boolean') throw invalidProvider();
  if (typeof raw.error !== 'string' || raw.error.length > 200) throw invalidProvider();
  if (!LANGUAGES.has(raw.language)) throw invalidProvider();
  if (typeof raw.gemma_base_url !== 'string' || raw.gemma_base_url.length > 120) {
    throw invalidProvider();
  }
  return {
    selected: raw.selected,
    active: raw.active,
    healthy: raw.healthy,
    error: raw.error,
    language: raw.language,
    gemma_base_url: raw.gemma_base_url,
    updated_at_ms: Number.isFinite(raw.updated_at_ms) ? raw.updated_at_ms : 0,
  };
};


export const createNemotronApi = (options = {}) => {
  const browserWindow = typeof window === 'undefined' ? {} : window;
  const WebSocketImpl = options.WebSocketImpl || browserWindow.WebSocket;
  const locationObject = options.locationObject || browserWindow.location || {};
  const timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;

  const request = (payload, responseKey, normalizer, errorFactory) => (
    new Promise((resolve, reject) => {
      if (!WebSocketImpl || !locationObject.hostname) {
        reject(errorFactory());
        return;
      }
      const scheme = locationObject.protocol === 'https:' ? 'wss:' : 'ws:';
      let settled = false;
      let socket;
      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        try { socket?.close(); } catch (_error) { /* best effort */ }
        callback(value);
      };
      const fail = () => finish(reject, errorFactory());
      let timer;
      try {
        socket = new WebSocketImpl(`${scheme}//${locationObject.hostname}:6671`);
      } catch (_error) {
        fail();
        return;
      }
      timer = setTimeout(fail, timeoutMs);
      socket.onopen = () => {
        try { socket.send(JSON.stringify(payload)); }
        catch (_error) { fail(); }
      };
      socket.onmessage = (event) => {
        if (settled) return;
        let message;
        try { message = JSON.parse(event.data); }
        catch (_error) { fail(); return; }
        if (!message?.[responseKey]) return;
        try { finish(resolve, normalizer(message[responseKey])); }
        catch (_error) { fail(); }
      };
      socket.onerror = fail;
      socket.onclose = fail;
    })
  );

  return {
    status: () => request(
      { action: 'nemotronStatus' }, 'nemotronStatus', normalize, invalid,
    ),
    providerStatus: () => request(
      { action: 'intelligenceProviderStatus' },
      'intelligenceProviderStatus', normalizeProvider, invalidProvider,
    ),
    setProvider: (provider) => {
      if (!PROVIDERS.has(provider)) return Promise.reject(invalidProvider());
      return request(
        { action: 'setIntelligenceProvider', provider },
        'setIntelligenceProvider', normalizeProvider, invalidProvider,
      );
    },
    setLanguage: (language) => {
      if (!LANGUAGES.has(language)) return Promise.reject(invalidProvider());
      return request(
        { action: 'setIntelligenceLanguage', language },
        'setIntelligenceLanguage', normalizeProvider, invalidProvider,
      );
    },
    setGemmaEndpoint: (gemmaIp) => {
      if (!validPrivateIpv4(gemmaIp)) return Promise.reject(invalidProvider());
      return request(
        { action: 'setGemmaEndpoint', gemma_ip: gemmaIp },
        'setGemmaEndpoint', normalizeProvider, invalidProvider,
      );
    },
  };
};


export const nemotronApi = createNemotronApi();
