# Secure NAO Network Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full network status, scan, connect, disconnect, and profile-removal controls to the existing web UI without exposing Wi-Fi credentials on the unauthenticated NAO WebSocket.

**Architecture:** A React panel calls an `aiohttp` broker bound to the PC loopback interface. The broker validates requests and invokes a fixed Python 2 helper on the NAO over SSH; the helper uses `ALConnectionManager` and requires a continuous three-second rear-head tactile hold before every mutation.

**Tech Stack:** React 19, Jest/Testing Library, Python 3.11+, `aiohttp`, OpenSSH, Python 2.7, `qi`, NAOqi 2.8 `ALConnectionManager` and `ALMemory`.

**Spec:** `docs/superpowers/specs/2026-08-23-nao-network-management-design.md`

## Global Constraints

- The broker binds only to `127.0.0.1`.
- Wi-Fi credentials never use the unauthenticated WebSocket on port 6671.
- Connect, disconnect, and forget require a continuous three-second `RearTactilTouched` hold.
- Passwords are never logged, returned, persisted by the browser, or included in test fixtures resembling real credentials.
- Robot-side code remains Python 2.7 compatible.
- SSH arguments and remote command are fixed; untrusted values travel only in bounded JSON on standard input.
- The supported operation allowlist is exactly `status`, `scan`, `profiles`, `connect`, `disconnect`, and `forget`.
- Existing web-control, deployment, and Nemotron behavior must remain compatible.

---

### Task 1: Shared PC request validation and redaction

**Files:**
- Create: `pc_gateway/src/nao_gateway/network_models.py`
- Test: `pc_gateway/tests/test_network_models.py`

**Interfaces:**
- Produces: `parse_network_request(payload: Mapping[str, object]) -> NetworkRequest`
- Produces: `redact_sensitive(value: object) -> object`
- Produces: immutable `NetworkRequest(operation, service_id, ssid, passphrase)`

- [ ] **Step 1: Write failing tests for the operation allowlist and redaction**

```python
def test_parse_rejects_unknown_operation():
    with pytest.raises(NetworkRequestError, match="Unsupported network operation"):
        parse_network_request({"operation": "shell", "command": "id"})


def test_redaction_removes_nested_secret_values():
    payload = {"ssid": "Lab", "passphrase": "example-only", "nested": {"password": "example-only"}}
    assert redact_sensitive(payload) == {
        "ssid": "Lab", "passphrase": "[REDACTED]", "nested": {"password": "[REDACTED]"}
    }
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest pc_gateway/tests/test_network_models.py -q`

Expected: collection fails because `nao_gateway.network_models` does not exist.

- [ ] **Step 3: Implement the immutable request model, length checks, operation-specific required fields, and recursive redaction**

```python
ALLOWED_OPERATIONS = frozenset({"status", "scan", "profiles", "connect", "disconnect", "forget"})
SENSITIVE_KEYS = frozenset({"passphrase", "password", "secret", "psk"})


@dataclass(frozen=True)
class NetworkRequest:
    operation: str
    service_id: str = ""
    ssid: str = ""
    passphrase: str = ""
```

Validation must reject non-dictionaries, unknown keys, values containing NUL, service IDs longer than 512 characters, SSIDs longer than 32 characters, and passphrases outside 8–63 characters when present. `connect` requires `service_id`; `disconnect` and `forget` require only `service_id`.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest pc_gateway/tests/test_network_models.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add pc_gateway/src/nao_gateway/network_models.py pc_gateway/tests/test_network_models.py
git commit -m "feat: validate and redact network requests"
```

### Task 2: Python 2 NAO network helper and physical confirmation

**Files:**
- Create: `nao/scripts/runtime/network_admin.py`
- Create: `nao/scripts/runtime/intelligence/tests/test_network_admin.py`
- Modify: `tests/test_python2_compatibility_runner.py`

**Interfaces:**
- Consumes: one JSON object of at most 8192 bytes from standard input.
- Produces: one redacted JSON result with `status`, `operation`, `data`, and optional `reason`.
- Produces: `RearTactileGate.wait_for_hold(timeout_seconds) -> bool`
- Produces: `ConnectionManagerAdapter.execute(request) -> dict`

- [ ] **Step 1: Write failing tests for continuous rear-sensor hold**

```python
def test_releasing_rear_sensor_resets_hold_timer():
    readings = iter([1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0])
    clock = FakeClock(step=1.0)
    gate = RearTactileGate(lambda: next(readings), clock.time, clock.sleep, hold_seconds=3.0)
    assert gate.wait_for_hold(timeout_seconds=10.0) is True
    assert clock.time() >= 6.0
```

- [ ] **Step 2: Run the test and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest nao/scripts/runtime/intelligence/tests/test_network_admin.py -q`

Expected: import fails because `network_admin.py` does not exist.

- [ ] **Step 3: Implement request parsing, redaction, and `RearTactileGate` without importing `qi` at module import time**

The gate must poll `ALMemory.getData("RearTactilTouched")`, start timing on a value of at least `0.5`, reset immediately on release, and return `False` when the overall confirmation deadline expires.

- [ ] **Step 4: Add failing adapter tests using a complete fake `ALConnectionManager`**

```python
def test_disconnect_requires_confirmation_before_state_change():
    manager = FakeConnectionManager()
    service = NetworkAdminService(ConnectionManagerAdapter(manager), RejectingGate())
    result = service.execute({"operation": "disconnect", "service_id": "wifi_lab"})
    assert result["status"] == "confirmation_timeout"
    assert manager.calls == []
```

- [ ] **Step 5: Implement the allowlisted `ALConnectionManager` adapter**

Read-only methods use `state()`, `interfaces()`, `scan()`, `services()`, and `provisionedServices()`. Mutations use `connect(service_id)`, `disconnect(service_id)`, and `forget(service_id)`. A protected network connection subscribes to `NetworkServiceInputRequired` before calling `connect`; its callback submits `[["ServiceId", service_id], ["Passphrase", passphrase]]` through `setServiceInput` only when passphrase input is requested.

Normalized service data may contain only `ServiceId`, `Name`, `Type`, `State`, `Security`, `Strength`, `Favorite`, `AutoConnect`, and non-secret IP fields.

- [ ] **Step 6: Add and pass tests for malformed JSON, oversized input, status/scan/profile normalization, every mutation, confirmation timeout, and redaction**

Run: `.\.venv\Scripts\python.exe -m pytest nao/scripts/runtime/intelligence/tests/test_network_admin.py -q`

Expected: all helper tests pass.

- [ ] **Step 7: Prove Python 2 syntax compatibility**

Run: `.\.venv\Scripts\python.exe nao/scripts/test_python2_compatibility.py`

Expected: `RESULTADOS: 3/3` and exit code 0. Add `network_admin.py` to the compatibility runner's explicit runtime file set if it is not discovered automatically.

- [ ] **Step 8: Commit**

```powershell
git add nao/scripts/runtime/network_admin.py nao/scripts/runtime/intelligence/tests/test_network_admin.py tests/test_python2_compatibility_runner.py
git commit -m "feat: add confirmed NAO network helper"
```

### Task 3: Loopback broker and fixed SSH transport

**Files:**
- Create: `pc_gateway/src/nao_gateway/network_broker.py`
- Create: `pc_gateway/tests/test_network_broker.py`
- Modify: `pc_gateway/pyproject.toml`

**Interfaces:**
- Consumes: `NetworkRequest` from Task 1.
- Produces: `SshNetworkTransport.execute(request: NetworkRequest) -> dict`.
- Produces: `create_network_app(transport, allowed_origins) -> aiohttp.web.Application`.
- HTTP contract: `GET /health`, `GET /network/status`, `POST /network/query`, and `POST /network/operation`.

- [ ] **Step 1: Add `aiohttp>=3.10,<4` and write a failing loopback API test**

```python
async def test_unapproved_origin_is_rejected(aiohttp_client):
    app = create_network_app(FakeTransport(), {"http://169.254.1.2:3000"})
    client = await aiohttp_client(app)
    response = await client.get("/network/status", headers={"Origin": "https://attacker.example"})
    assert response.status == 403
```

- [ ] **Step 2: Run the broker tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest pc_gateway/tests/test_network_broker.py -q`

Expected: import fails because `network_broker` does not exist.

- [ ] **Step 3: Implement strict CORS/origin handling and bounded JSON endpoints**

Only `GET`, `POST`, and preflight `OPTIONS` are accepted. The response includes `Access-Control-Allow-Origin` only after an exact allowed-origin match and `Vary: Origin`. Request bodies are limited to 8192 bytes. Cache headers are `no-store`.

- [ ] **Step 4: Write failing transport tests proving values are sent on stdin, not command arguments**

```python
async def test_ssh_transport_keeps_ssid_and_passphrase_out_of_argv():
    runner = RecordingProcessRunner({"status": "completed", "operation": "connect", "data": {}})
    transport = SshNetworkTransport("nao", "169.254.1.2", "C:/keys/nao", runner=runner)
    await transport.execute(NetworkRequest("connect", "wifi_lab", "Lab", "example-only"))
    assert "Lab" not in " ".join(runner.argv)
    assert "example-only" not in " ".join(runner.argv)
    assert json.loads(runner.stdin)["service_id"] == "wifi_lab"
```

- [ ] **Step 5: Implement `asyncio.create_subprocess_exec` transport**

The fixed command arguments are:

```python
[
    "ssh", "-i", key_path,
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=yes",
    "-o", "ConnectTimeout=8",
    f"{user}@{host}",
    "python2 /home/nao/naoControl/nao/scripts/runtime/network_admin.py --stdin",
]
```

The request JSON is written only to stdin. Apply a 45-second timeout, cap stdout/stderr at 64 KiB, parse exactly one JSON result, redact exceptions, and classify an SSH disconnect after a mutation as `transport_lost_after_apply` rather than unconditional success.

- [ ] **Step 6: Run broker tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest pc_gateway/tests/test_network_broker.py -q`

Expected: all broker tests pass.

- [ ] **Step 7: Commit**

```powershell
git add pc_gateway/pyproject.toml pc_gateway/src/nao_gateway/network_broker.py pc_gateway/tests/test_network_broker.py
git commit -m "feat: add secure PC network broker"
```

### Task 4: Gateway lifecycle and configuration

**Files:**
- Modify: `pc_gateway/src/nao_gateway/config.py`
- Modify: `pc_gateway/src/nao_gateway/main.py`
- Modify: `pc_gateway/tests/test_config.py`
- Modify: `pc_gateway/tests/test_main.py`
- Create: `.env.example`

**Interfaces:**
- Produces settings `network_broker_enabled`, `network_broker_port`, `nao_ssh_user`, `nao_ssh_key`, and `network_allowed_origins`.
- Produces `run_network_broker(settings) -> None` as a sibling async service to the reconnecting Nemotron gateway.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_network_broker_defaults_to_loopback_port_and_robot_web_origin(base_env):
    settings = GatewaySettings.from_env(base_env | {"NAO_GATEWAY_URL": "ws://169.254.1.2:6674"})
    assert settings.network_broker_host == "127.0.0.1"
    assert settings.network_broker_port == 6675
    assert settings.network_allowed_origins == ("http://169.254.1.2:3000",)
```

- [ ] **Step 2: Verify RED, then implement strict environment parsing**

Run: `.\.venv\Scripts\python.exe -m pytest pc_gateway/tests/test_config.py -q`

Reject non-loopback broker hosts, ports outside 1024–65535, missing SSH key paths when the broker is enabled, and origins that are not explicit `http://` or `https://` origins without paths.

- [ ] **Step 3: Write failing lifecycle tests and start broker beside the gateway**

Use `asyncio.gather(maintain_robot_connection(...), run_network_broker(...))`; cancellation of either service must close the `aiohttp` runner and Nemotron client.

- [ ] **Step 4: Document only names and safe example values in `.env.example`**

```dotenv
NAO_NETWORK_BROKER_ENABLED=true
NAO_NETWORK_BROKER_PORT=6675
NAO_SSH_USER=nao
NAO_SSH_KEY=C:\\Users\\you\\.ssh\\nao_control_ed25519
NAO_NETWORK_ALLOWED_ORIGINS=http://169.254.1.2:3000
```

- [ ] **Step 5: Run focused and full gateway tests**

Run: `.\.venv\Scripts\python.exe -m pytest pc_gateway/tests -q`

Expected: all PC gateway tests pass.

- [ ] **Step 6: Commit**

```powershell
git add .env.example pc_gateway/src/nao_gateway/config.py pc_gateway/src/nao_gateway/main.py pc_gateway/tests/test_config.py pc_gateway/tests/test_main.py
git commit -m "feat: run network broker with Nemotron gateway"
```

### Task 5: React network client and management panel

**Files:**
- Create: `NaoControlReact/src/services/networkApi.js`
- Create: `NaoControlReact/src/services/networkApi.test.js`
- Create: `NaoControlReact/src/components/NetworkMenu.js`
- Create: `NaoControlReact/src/components/NetworkMenu.css`
- Create: `NaoControlReact/src/components/NetworkMenu.test.js`
- Modify: `NaoControlReact/src/components/SidePanel.js`
- Modify: `NaoControlReact/src/components/MenuContent.js`

**Interfaces:**
- Produces: `networkApi.status()`, `scan()`, `profiles()`, and `mutate(payload)`.
- Produces: `NetworkMenu` with status, available networks, saved profiles, password entry, warning confirmation, and physical-confirmation progress.

- [ ] **Step 1: Write failing API tests for loopback-only URL and password handling**

```javascript
test('sends a connect credential only to the loopback broker', async () => {
  global.fetch = jest.fn().mockResolvedValue(okJson({ status: 'pending_confirmation' }));
  await networkApi.mutate({ operation: 'connect', service_id: 'wifi_lab', passphrase: 'example-only' });
  expect(fetch.mock.calls[0][0]).toBe('http://127.0.0.1:6675/network/operation');
  expect(fetch.mock.calls[0][1].cache).toBe('no-store');
});
```

- [ ] **Step 2: Verify RED and implement `networkApi`**

Run: `npm test -- --watchAll=false src/services/networkApi.test.js`

Provide a 50-second `AbortController` timeout, JSON-only responses, generic error messages, and no console logging of request bodies.

- [ ] **Step 3: Write failing component tests**

Tests must prove that the panel renders broker-unavailable state, refreshes status, shows scanned networks, requires explicit UI acknowledgement before last-path disconnect/removal, labels the rear-sensor three-second confirmation, disables duplicate submissions, and clears the password input immediately after submission settles.

- [ ] **Step 4: Implement the panel and navigation entry**

Add `{ id: 'network', icon: FaWifi, label: 'Red' }` to `SidePanel`. Add the `network` case to `MenuContent`. Keep all network state inside `NetworkMenu`; do not pass credentials through `NaoController` or ordinary `sendMessage`.

- [ ] **Step 5: Run tests and production build**

Run: `npm test -- --watchAll=false`

Run: `npm run build`

Expected: tests pass and `NaoControlReact/build/index.html` is produced without ESLint errors.

- [ ] **Step 6: Commit**

```powershell
git add NaoControlReact/src/services NaoControlReact/src/components/NetworkMenu.* NaoControlReact/src/components/SidePanel.js NaoControlReact/src/components/MenuContent.js NaoControlReact/build
git commit -m "feat: manage NAO networks from web control"
```

### Task 6: SSH-key setup, deployment, and operator documentation

**Files:**
- Create: `tools/setup-nao-network-admin.ps1`
- Create: `tests/test_network_admin_setup_script.py`
- Modify: `tools/deploy-nao.ps1`
- Modify: `tests/test_deploy_script.py`
- Create: `docs/network-management.md`
- Modify: `README.md`

**Interfaces:**
- Produces: `tools/setup-nao-network-admin.ps1 -NaoIp <IP>` for one-time key setup.
- Preserves: `tools/deploy-nao.ps1 -NaoIp <IP> -StartServices` as the single deployment command.

- [ ] **Step 1: Write failing script behavior tests**

Run the PowerShell scripts with controlled fake `ssh`, `scp`, and `ssh-keygen` executables. Assert that the setup key is created outside the repository, the public key alone is appended to `~/.ssh/authorized_keys`, target IP validation rejects shell syntax, and deployment includes `network_admin.py` without copying `.env` or private keys.

- [ ] **Step 2: Verify RED and implement setup script**

The default key path is `%USERPROFILE%\.ssh\nao_control_ed25519`. Use `ssh-keygen -t ed25519` only when absent, require the operator's normal SSH password for the initial append, set remote `.ssh` permissions to 700 and `authorized_keys` to 600, and verify a subsequent `BatchMode=yes` connection.

- [ ] **Step 3: Update deployment validation**

After extraction, verify both:

```sh
test -f "$staged/nao/scripts/runtime/network_admin.py"
python -m py_compile "$staged/nao/scripts/runtime/network_admin.py"
```

- [ ] **Step 4: Document setup and recovery**

Document the exact sequence:

```powershell
.\tools\setup-nao-network-admin.ps1 -NaoIp <NAO_IP>
.\tools\deploy-nao.ps1 -NaoIp <NAO_IP> -StartServices
.\.venv\Scripts\python.exe -u -m nao_gateway.main --env-file .env --registry config\action_registry.json
```

Include broker port 6675, web port 3000, rear-sensor confirmation, Ethernet-first hardware testing, host-key replacement handling after a robot reset, expected connection loss, and the recovery SSH commands.

- [ ] **Step 5: Run deployment/setup tests and secret scan**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_network_admin_setup_script.py tests/test_deploy_script.py tests/test_no_tracked_secrets.py -q`

Expected: all tests pass and no credentials are tracked.

- [ ] **Step 6: Commit**

```powershell
git add tools/setup-nao-network-admin.ps1 tools/deploy-nao.ps1 tests/test_network_admin_setup_script.py tests/test_deploy_script.py docs/network-management.md README.md
git commit -m "docs: add secure network deployment workflow"
```

### Task 7: Full verification and security review

**Files:**
- Modify only files required by failures proven in this task.

**Interfaces:**
- Verifies the complete approved specification and repository security invariants.

- [ ] **Step 1: Run all Python tests**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run Python 2 compatibility checks**

Run: `.\.venv\Scripts\python.exe nao/scripts/test_python2_compatibility.py`

Expected: `RESULTADOS: 3/3`.

- [ ] **Step 3: Run frontend tests and build**

Run: `npm test -- --watchAll=false`

Run: `npm run build`

Expected: both commands succeed without warnings attributable to the change.

- [ ] **Step 4: Review the complete branch diff for credential exposure, origin bypass, shell interpolation, fail-open confirmation, and accidental WebSocket routing**

Inspect `git diff origin/feature/nemotron-multimodal-agent...HEAD` and confirm that passphrases occur only as transient typed values, all subprocess arguments are fixed, and every mutation calls the physical gate before the adapter.

- [ ] **Step 5: Perform Ethernet-connected hardware smoke test**

Verify status, scan, and profiles first. Then connect to a non-critical test Wi-Fi profile. Verify a short rear-sensor press rejects the operation, a continuous three-second press permits it, the password is absent from PC and NAO logs, and Ethernet still provides recovery. Test disconnect and forget only on the non-critical profile.

- [ ] **Step 6: Commit any test-proven integration corrections, then push**

```powershell
git status --short
git push origin feature/nemotron-multimodal-agent
```

Expected: clean working tree and remote branch updated.

## Primary references

- SoftBank Robotics, [`ALConnectionManager` API 2.8.7.4](http://doc.aldebaran.com/2-8/naoqi/connectionmanager/alconnectionmanager-api.html).
- Approved project design: `docs/superpowers/specs/2026-08-23-nao-network-management-design.md`.
