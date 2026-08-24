# Integrated NAO Network Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all NAO network-management operations available through the existing control WebSocket whenever NAO Control starts, with no PC broker, SSH setup, or Nemotron dependency.

**Architecture:** Add one typed `networkAdmin` command to the robot-side command factory and inject the existing `NetworkAdminService` during control-server initialization. Rewrite the React network client to exchange correlated request/response frames with `ws://<NAO_IP>:6671`, then remove the obsolete PC broker and configuration.

**Tech Stack:** Python 2.7-compatible robot runtime, NAOqi 2.8 `qi` and `ALConnectionManager`, SimpleWebSocketServer, React 19, Jest, pytest, PowerShell deployment tooling.

**Spec:** `docs/superpowers/specs/2026-08-24-nao-integrated-network-management-design.md`

## Global Constraints

- Keep every deployed Python module compatible with Python 2.7 syntax.
- Keep `status`, `scan`, `profiles`, `connect`, `disconnect`, and `forget` as the complete operation allowlist.
- Require a continuous three-second `RearTactilTouched` hold for every mutating operation.
- Never log, persist, or return passphrases, passwords, PSKs, or secrets.
- A failed network-service initialization must not prevent normal control-server startup.
- Do not introduce a new port, daemon, cloud dependency, SSH key, or PC startup command.
- Do not push; create local commits after each independently testable task.

---

### Task 1: Robot-side WebSocket command and safe logging

**Files:**
- Create: `nao/scripts/runtime/control_server/commands/network_commands.py`
- Create: `nao/scripts/runtime/control_server/message_security.py`
- Create: `nao/scripts/runtime/intelligence/tests/test_network_control_command.py`
- Modify: `nao/scripts/runtime/control_server/command_factory.py`
- Modify: `nao/scripts/runtime/control_server/server.py`

**Interfaces:**
- Consumes: `build_robot_service(session, audit_log=None) -> NetworkAdminService` and `NetworkAdminService.execute(request: dict) -> dict`.
- Produces: `NetworkAdminCommand(nao_facade, logger, network_service)` and `safe_message_summary(message: dict) -> str`.
- Request: `{action, request_id, operation, service_id?, ssid?, passphrase?}`.
- Response: `{"networkAdmin": {request_id, status, operation, data, reason?}}`.

- [ ] **Step 1: Write failing command tests**

Create real command tests with recording service, socket, and logger fakes. Cover successful forwarding, request-ID correlation, unknown outer fields, unavailable service, stable exception handling, and absence of `example-only` from responses and logs.

```python
message = {"action": "networkAdmin", "request_id": "req-1",
           "operation": "connect", "service_id": "wifi_lab",
           "passphrase": "example-only"}
assert command.execute(message, socket) is True
payload = json.loads(socket.messages[-1])["networkAdmin"]
assert payload["request_id"] == "req-1"
assert "example-only" not in json.dumps(payload)
```

- [ ] **Step 2: Write failing logging tests**

Assert `safe_message_summary()` returns only `action`, `operation`, and a validated 1-64 character `[A-Za-z0-9._-]` request ID. Assert arbitrary keys and passphrases never appear.

- [ ] **Step 3: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest nao\scripts\runtime\intelligence\tests\test_network_control_command.py -q
```

Expected: collection fails because the two production modules do not exist.

- [ ] **Step 4: Implement the command and sanitizer**

Copy only `operation`, `service_id`, `ssid`, and `passphrase` into the service request. Reject invalid request IDs and outer fields. Catch `NetworkAdminError` as `invalid_request` and other exceptions as `operation_failed` without exception text. Send one stable envelope and never echo the passphrase.

- [ ] **Step 5: Inject one service instance**

Extend `CommandFactory.__init__(..., network_service=None)`, register `networkAdmin`, and pass the service only to `NetworkAdminCommand`. In `ModularControlServer`, create a local `qi.Session`, connect to `tcp://127.0.0.1:9559`, call `build_robot_service`, and retain both session and service. If initialization fails, continue with `None`. Replace raw inbound logging with `safe_message_summary(message)` after JSON parsing.

- [ ] **Step 6: Verify GREEN and regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest nao\scripts\runtime\intelligence\tests\test_network_control_command.py nao\scripts\runtime\intelligence\tests\test_network_admin.py nao\scripts\runtime\intelligence\tests\test_nao_facade_runtime.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add nao/scripts/runtime/control_server nao/scripts/runtime/intelligence/tests/test_network_control_command.py
git commit -m "feat: integrate network management into NAO control"
```

---

### Task 2: React WebSocket network client

**Files:**
- Modify: `NaoControlReact/src/services/networkApi.js`
- Modify: `NaoControlReact/src/services/networkApi.test.js`
- Modify only if required for stable result mapping: `NaoControlReact/src/components/NetworkMenu.js`
- Test: `NaoControlReact/src/components/NetworkMenu.test.js`

**Interfaces:**
- Consumes: Task 1 `networkAdmin` protocol.
- Produces: `createNetworkApi({ WebSocketImpl, locationObject, idFactory, timeoutMs })` with existing `status()`, `scan()`, `profiles()`, and `mutate(payload)` methods.

- [ ] **Step 1: Write failing WebSocket behavior tests**

Use a behavioral fake WebSocket. Verify robot-host URL derivation, send-after-open, ignoring `server_info` and mismatched IDs, resolving only the matched response, closing on completion, and generic errors for timeout, early close, malformed JSON, and failed responses.

```javascript
const api = createNetworkApi({
  WebSocketImpl: FakeWebSocket,
  locationObject: { protocol: 'http:', hostname: '169.254.197.40' },
  idFactory: () => 'req-1', timeoutMs: 100,
});
const pending = api.status();
socket.open();
expect(JSON.parse(socket.sent[0])).toEqual({
  action: 'networkAdmin', request_id: 'req-1', operation: 'status',
});
```

- [ ] **Step 2: Verify RED**

```powershell
cd NaoControlReact
$env:CI='true'
npm test -- --watchAll=false src/services/networkApi.test.js
cd ..
```

Expected: FAIL because the implementation still uses `fetch()` and port `6675`.

- [ ] **Step 3: Implement the bounded one-request client**

Derive `ws:`/`wss:` from the page protocol, use `locationObject.hostname` and fixed port `6671`, validate the generated ID, register callbacks, send once after open, filter frames, clear the timer on every terminal path, and close exactly once. Do not persist the passphrase or reflect received content in errors.

- [ ] **Step 4: Verify GREEN and menu behavior**

```powershell
cd NaoControlReact
$env:CI='true'
npm test -- --watchAll=false src/services/networkApi.test.js src/components/NetworkMenu.test.js
cd ..
```

Expected: all selected tests pass and password clearing remains green.

- [ ] **Step 5: Commit**

```powershell
git add NaoControlReact/src/services/networkApi.js NaoControlReact/src/services/networkApi.test.js NaoControlReact/src/components/NetworkMenu.js NaoControlReact/src/components/NetworkMenu.test.js
git commit -m "feat: route network control through NAO websocket"
```

---

### Task 3: Remove the obsolete PC broker and SSH setup

**Files:**
- Delete: `pc_gateway/src/nao_gateway/network_main.py`
- Delete: `pc_gateway/src/nao_gateway/network_broker.py`
- Delete: `pc_gateway/src/nao_gateway/network_models.py`
- Delete: `pc_gateway/tests/test_network_main.py`
- Delete: `pc_gateway/tests/test_network_broker.py`
- Delete: `pc_gateway/tests/test_network_models.py`
- Delete: `tools/setup-nao-network-admin.ps1`
- Delete: `tests/test_network_admin_setup_script.py`
- Modify: `pc_gateway/src/nao_gateway/config.py`
- Modify: `pc_gateway/tests/test_config.py`
- Modify: `pc_gateway/pyproject.toml`
- Modify: `.env.example`

**Interfaces:**
- Removes: `NetworkBrokerSettings`, `nao-network-admin`, `NAO_NETWORK_*`, port `6675`, and SSH transport.
- Preserves: `GatewaySettings`, Nemotron entry points, and the robot-local `network_admin.py` service.

- [ ] **Step 1: Add the reduced-surface configuration regression**

Keep all `GatewaySettings` tests. Add a test proving legacy `NAO_NETWORK_*` keys do not affect `GatewaySettings`; remove imports and assertions whose only subject is the deleted broker.

- [ ] **Step 2: Establish and verify the removal boundary**

```powershell
.\.venv\Scripts\python.exe -m pytest pc_gateway\tests -q
```

Expected before deletion: current suite passes. After test edits but before production removal: imports fail, proving the obsolete surface still exists in test expectations.

- [ ] **Step 3: Delete broker code and configuration**

Delete the listed files. Remove broker helpers and `NetworkBrokerSettings` only; do not change `GatewaySettings`. Remove the console entry point and obsolete environment variables. Remove `aiohttp` only if `rg -n "aiohttp" pc_gateway` proves no remaining production use.

- [ ] **Step 4: Verify the PC gateway**

```powershell
.\.venv\Scripts\python.exe -m pytest pc_gateway\tests -q
.\.venv\Scripts\python.exe -m compileall -q pc_gateway\src
```

Expected: all PC gateway tests pass and compilation exits zero.

- [ ] **Step 5: Commit**

```powershell
git add -A -- pc_gateway tools/setup-nao-network-admin.ps1 tests/test_network_admin_setup_script.py .env.example
git commit -m "refactor: remove PC network broker"
```

---

### Task 4: Documentation, build, and final verification

**Files:**
- Modify: `README.md`
- Modify: `docs/network-management.md`
- Modify only if validation coverage is missing: `tools/deploy-nao.ps1`
- Modify only with deploy behavior: `tests/test_deploy_script.py`
- Regenerate: `NaoControlReact/build/`

**Interfaces:**
- Operator command: `powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\deploy-nao.ps1" -NaoIp <NAO_IP> -StartServices`.
- UI: `http://<NAO_IP>:3000`; control and network WebSocket: `ws://<NAO_IP>:6671`.

- [ ] **Step 1: Update operator documentation**

Remove all setup-script, `network_main`, SSH-key, PC-broker, and port-6675 instructions. Document the single deploy command, automatic startup, rear-sensor confirmation, Ethernet-first testing, redacted robot log, and plaintext WebSocket limitation.

- [ ] **Step 2: Run Python and deployment verification**

```powershell
.\.venv\Scripts\python.exe -m pytest pc_gateway\tests nao\scripts\runtime\intelligence\tests tests\test_deploy_script.py -q
.\.venv\Scripts\python.exe -m compileall -q pc_gateway\src nao\scripts\runtime
```

- [ ] **Step 3: Run frontend verification and build**

```powershell
cd NaoControlReact
$env:CI='true'
npm test -- --watchAll=false
npm run build
cd ..
```

- [ ] **Step 4: Review security-sensitive diff and stale references**

```powershell
git diff --check
rg -n "127\.0\.0\.1:6675|network_main|setup-nao-network-admin|NAO_NETWORK_|NAO_SSH_KEY" README.md docs .env.example NaoControlReact pc_gateway tools tests
rg -n "passphrase|password|psk|secret" nao/scripts/runtime/control_server nao/scripts/runtime/network_admin.py
```

Expected: no operational stale references; remaining sensitive-field occurrences are bounded validation/redaction or safe fixtures. Review the diff for raw-message logging, shell execution, secret persistence, unrestricted operations, and unsafe error reflection.

- [ ] **Step 5: Commit documentation and build**

```powershell
git add README.md docs/network-management.md NaoControlReact/build tools/deploy-nao.ps1 tests/test_deploy_script.py
git commit -m "docs: simplify integrated NAO network deployment"
```

- [ ] **Step 6: Confirm local completion without push**

```powershell
git status --short
git log --oneline -8
```

Expected: clean worktree, local commits present, and no push performed. Physical deployment remains explicit against the current NAO IP.
