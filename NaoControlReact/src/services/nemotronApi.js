const DEFAULT_TIMEOUT_MS = 3000;
const PHASES = new Set(['idle', 'listening', 'processing', 'responding', 'ready', 'error']);
const ACTION_STATUSES = new Set([
  'pending', 'accepted', 'completed', 'rejected', 'failed', 'unknown',
]);
const ERROR_MESSAGE = 'Estado Nemotron no disponible.';


const invalid = () => new Error(ERROR_MESSAGE);


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


export const createNemotronApi = (options = {}) => {
  const browserWindow = typeof window === 'undefined' ? {} : window;
  const WebSocketImpl = options.WebSocketImpl || browserWindow.WebSocket;
  const locationObject = options.locationObject || browserWindow.location || {};
  const timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;

  return {
    status: () => new Promise((resolve, reject) => {
      if (!WebSocketImpl || !locationObject.hostname) {
        reject(invalid());
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
      const fail = () => finish(reject, invalid());
      let timer;
      try {
        socket = new WebSocketImpl(`${scheme}//${locationObject.hostname}:6671`);
      } catch (_error) {
        fail();
        return;
      }
      timer = setTimeout(fail, timeoutMs);
      socket.onopen = () => {
        try { socket.send(JSON.stringify({ action: 'nemotronStatus' })); }
        catch (_error) { fail(); }
      };
      socket.onmessage = (event) => {
        if (settled) return;
        let message;
        try { message = JSON.parse(event.data); }
        catch (_error) { fail(); return; }
        if (!message?.nemotronStatus) return;
        try { finish(resolve, normalize(message.nemotronStatus)); }
        catch (_error) { fail(); }
      };
      socket.onerror = fail;
      socket.onclose = fail;
    }),
  };
};


export const nemotronApi = createNemotronApi();
