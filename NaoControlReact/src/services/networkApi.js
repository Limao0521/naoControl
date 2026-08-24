const DEFAULT_TIMEOUT_MS = 50000;
const REQUEST_ID_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
const RESULT_STATUSES = new Set([
  'completed', 'rejected', 'confirmation_timeout', 'failed',
]);
const MUTATING_OPERATIONS = new Set(['connect', 'disconnect', 'forget']);
const GENERIC_ERROR = 'No fue posible contactar el gestor de red.';


const defaultIdFactory = () => (
  `network-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
);


const genericError = () => new Error(GENERIC_ERROR);


export const createNetworkApi = (options = {}) => {
  const browserWindow = typeof window === 'undefined' ? {} : window;
  const WebSocketImpl = options.WebSocketImpl || browserWindow.WebSocket;
  const locationObject = options.locationObject || browserWindow.location || {};
  const idFactory = options.idFactory || defaultIdFactory;
  const timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;

  const request = (requestPayload) => {
    const requestId = String(idFactory());
    if (!REQUEST_ID_PATTERN.test(requestId) || !WebSocketImpl || !locationObject.hostname) {
      return Promise.reject(genericError());
    }

    const scheme = locationObject.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${scheme}//${locationObject.hostname}:6671`;

    return new Promise((resolve, reject) => {
      let socket;
      let settled = false;
      let sent = false;
      let timer;

      const closeSocket = () => {
        try { socket?.close(); } catch (_error) { /* best effort */ }
      };
      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        closeSocket();
        callback(value);
      };
      const fail = () => finish(reject, genericError());

      try {
        socket = new WebSocketImpl(url);
      } catch (_error) {
        fail();
        return;
      }

      timer = setTimeout(fail, timeoutMs);

      socket.onopen = () => {
        if (settled) return;
        try {
          socket.send(JSON.stringify({
            ...requestPayload,
            action: 'networkAdmin',
            request_id: requestId,
          }));
          sent = true;
        } catch (_error) {
          fail();
        }
      };

      socket.onmessage = (event) => {
        if (settled) return;
        let message;
        try {
          message = JSON.parse(event.data);
        } catch (_error) {
          fail();
          return;
        }
        const result = message?.networkAdmin;
        if (!result || result.request_id !== requestId) return;
        if (!RESULT_STATUSES.has(result.status) || typeof result.operation !== 'string') {
          fail();
          return;
        }
        const normalized = {
          request_id: requestId,
          status: result.status,
          operation: result.operation,
          data: result.data && typeof result.data === 'object' ? result.data : {},
        };
        if (typeof result.reason === 'string') normalized.reason = result.reason;
        finish(resolve, normalized);
      };

      socket.onerror = fail;
      socket.onclose = () => {
        if (settled) return;
        const operation = requestPayload.operation;
        if (sent && MUTATING_OPERATIONS.has(operation)) {
          finish(resolve, {
            request_id: requestId,
            status: 'transport_lost',
            operation,
            data: {},
            reason: 'connection_lost',
          });
        } else {
          fail();
        }
      };
    });
  };

  return {
    status: () => request({ operation: 'status' }),
    scan: () => request({ operation: 'scan' }),
    profiles: () => request({ operation: 'profiles' }),
    mutate: (payload) => request(payload),
  };
};


export const networkApi = createNetworkApi();
