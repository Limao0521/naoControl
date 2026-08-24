# Integrated NAO Network Management Design

**Date:** 2026-08-24
**Status:** Approved in chat; pending document review
**Branch:** `feature/nemotron-multimodal-agent`
**Supersedes:** `2026-08-23-nao-network-management-design.md`

## Objective

Make network management an intrinsic feature of the NAO web control. It must
be available whenever the control WebSocket is running, without a PC-side
broker, a dedicated SSH key, an NVIDIA/Nemotron process, or any manual process
outside the normal NAO Control startup.

## Resulting architecture

```text
Browser Network panel
        |
        | existing ws://<NAO_IP>:6671 control channel
        v
NAO modular control server
        |
        | typed, allowlisted request
        v
NetworkAdminService
        |
        +-- rear-head tactile confirmation for mutations
        +-- ALConnectionManager adapter
        +-- redacted robot-local audit log
```

`NetworkAdminService` is constructed when the modular control server starts.
It is therefore available with the web control even when Nemotron and the PC
gateway are stopped. No additional daemon or port is introduced.

## Supported protocol

The WebSocket accepts one new action:

```json
{
  "action": "networkAdmin",
  "request_id": "browser-generated-id",
  "operation": "status|scan|profiles|connect|disconnect|forget",
  "service_id": "optional-service-id",
  "ssid": "optional-ssid",
  "passphrase": "optional-password"
}
```

Only `action`, `request_id`, `operation`, `service_id`, `ssid`, and
`passphrase` are accepted. The existing `NetworkAdminService` continues to
validate operation-specific fields and string sizes. The control server replies
with:

```json
{
  "networkAdmin": {
    "request_id": "browser-generated-id",
    "status": "completed|rejected|confirmation_timeout|failed",
    "operation": "status",
    "data": {},
    "reason": "optional-stable-reason"
  }
}
```

The response repeats only the bounded `request_id`; it never repeats the
passphrase. The browser ignores the initial `server_info` frame and any response
whose action or request identifier does not match its pending request.

## Control-server integration

A `NetworkAdminCommand` adapts the existing command pattern to
`NetworkAdminService`. The service is created once during control-server
initialization and injected into the command factory; it is not reconstructed
for every browser request.

Initialization failure does not prevent ordinary robot control from starting.
Instead, `networkAdmin` returns `unavailable` and the failure is recorded
without credentials. This isolates a missing or unsupported
`ALConnectionManager` from movement, speech, camera, and Nemotron behavior.

Read-only operations execute synchronously. Mutating operations may wait up to
the existing physical-confirmation timeout, so the browser uses a bounded
request timeout longer than that gate. While a mutation is pending, the normal
movement watchdog remains active.

## Physical confirmation and robot safety

`connect`, `disconnect`, and `forget` retain the existing continuous
three-second hold on `RearTactilTouched`. Releasing the sensor resets the hold.
If confirmation expires, network state remains unchanged.

Before execution, the NAO announces the confirmation request in Spanish and
uses the chest LED to show pending, completed, or rejected state. The UI keeps
its current warnings when Ethernet is unavailable or the selected profile is
active.

## Credential and logging rules

- The browser password field is cleared immediately after submission.
- The WebSocket server no longer logs raw inbound JSON. It logs only the action,
  bounded request identifier, and operation name.
- The network service never writes passphrases, passwords, PSKs, or secrets to
  its audit log or response.
- Exceptions returned to the browser use stable reasons and never include raw
  exception strings.
- The passphrase remains in memory only for the duration of the request and the
  `ALConnectionManager` input callback.

The current page uses HTTP and an unencrypted WebSocket. Consequently, this
design protects credentials from application logs and persistence but not from
packet capture by an attacker on the same network. Initial validation must use
a direct Ethernet or otherwise trusted laboratory network. TLS is a separate
future hardening item and is not silently claimed by this migration.

## Frontend behavior

The React network client derives the robot host from `window.location.hostname`
and communicates with `ws://<host>:6671`. It opens a bounded request connection,
sends one `networkAdmin` request after the socket opens, waits for the matching
response, then closes the socket. This keeps the network menu independent from
the controller component's long-lived command socket while reusing the same
robot service and port.

Connection loss after an approved mutation is reported as an indeterminate
transport result. The UI instructs the operator to verify the new address over
Ethernet instead of claiming success or automatically retrying the mutation.

## Removed components and configuration

The implementation removes the operational dependency on:

- `nao_gateway.network_main` and its console entry point.
- The PC-side `network_broker` and SSH transport.
- `NetworkBrokerSettings` and `NAO_NETWORK_*` environment variables.
- `tools/setup-nao-network-admin.ps1` and the dedicated SSH key.
- Port `6675` and the manual PC startup command.

The robot-side `network_admin.py` remains because it contains the validated
NAOqi adapter, tactile gate, notifier, redaction, and audit logic. Its existing
stdin entry point remains available only as a robot-local diagnostic interface;
the runtime and operator documentation do not invoke or depend on it.

## Startup and deployment

No lifecycle script starts a separate network process. Starting the existing
control service on port `6671` activates network management automatically.
Starting Nemotron remains optional and unrelated.

The complete operator workflow becomes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\deploy-nao.ps1" -NaoIp <NAO_IP> -StartServices
```

After deployment, the Network panel is available at
`http://<NAO_IP>:3000`; there is no setup command and no PC network-manager
terminal.

## Testing strategy

- Python unit tests for command injection, request/response correlation,
  unavailable-service behavior, redaction, validation, and tactile confirmation.
- Control-server tests proving raw network credentials are never logged.
- React tests for robot-host URL derivation, server-info filtering, request ID
  matching, timeouts, password clearing, and connection-loss messaging.
- Regression tests proving the normal command factory and Nemotron gateway do
  not initialize or depend on the removed PC broker.
- Python 2 compilation checks for every deployed robot-side module.
- Frontend test and production build before deployment.
- Hardware validation over Ethernet: status, scan, rejected early release,
  confirmed connection, and recovery after an address change.

## Acceptance criteria

- Deploying and starting NAO Control is sufficient to expose the Network panel.
- Nemotron, NVIDIA credentials, the PC gateway, SSH setup, and port `6675` are
  unnecessary for all six network operations.
- Read-only operations work without tactile confirmation.
- Mutations cannot execute without a continuous three-second rear-head hold.
- No password appears in console logs, robot audit logs, WebSocket responses,
  test fixtures, Git history introduced by this change, or browser persistence.
- Existing movement, speech, web control, camera, and Nemotron behavior remains
  available if network-service initialization fails.
- The deploy script remains the only operator command required after a fresh
  checkout with dependencies already installed.
