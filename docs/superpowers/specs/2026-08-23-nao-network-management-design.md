# NAO Web Network Management Design

**Date:** 2026-08-23
**Status:** Approved
**Branch:** `feature/nemotron-multimodal-agent`

## Objective

Add complete network management to the NAO web control while protecting Wi-Fi credentials and preventing an unauthenticated browser session from changing robot connectivity without a physical operator present.

## Scope

The web control will provide:

- Current connection, interface, address, route, and signal status.
- Wireless network scanning.
- Saved network profile listing.
- Connecting to and saving a wireless network.
- Disconnecting an active profile.
- Removing a saved profile.

Read-only operations do not require physical confirmation. Every mutating operation requires the rear head tactile sensor to remain pressed for three seconds before it is executed.

## Architecture

The existing NAO web page exposes a Network panel, but administrative requests are handled by a PC-side network broker. The browser communicates only with the broker through loopback. The broker sends operations to a robot-side network helper over an encrypted SSH transport.

```text
NAO web Network panel
        |
        | loopback-only administrative API
        v
PC network broker
        |
        | SSH encrypted transport
        v
NAO network helper
        |
        +-- rear tactile confirmation gate
        +-- NAOqi connection-manager adapter
        +-- durable operation result log
```

The existing unauthenticated WebSocket on port 6671 remains responsible for ordinary robot controls. It must not carry new-network passwords or unrestricted network-management commands.

## Security boundaries

- The broker listens only on `127.0.0.1` and validates browser origins.
- Mutating requests require a short-lived operation identifier and physical confirmation.
- Wi-Fi credentials are accepted only for a connect operation and are never written to application logs, command events, or UI history.
- Robot-side operations use typed arguments and an explicit operation allowlist. Arbitrary shell input is forbidden.
- Active-profile disconnect and removal require an additional UI warning when no alternate connection is detected.
- The physical confirmation expires if it is not completed within the configured time window.
- Read-only status data may be reported through the normal UI but must not include stored credentials.

## Interaction flow

### Read-only operation

1. The browser asks the loopback broker for status, scan results, or profiles.
2. The broker invokes the robot helper over SSH.
3. The helper queries the connection-manager adapter and returns normalized JSON.
4. The panel displays the result.

### Mutating operation

1. The browser sends a typed connect, disconnect, or forget request to the broker.
2. The broker opens an SSH session and creates a pending robot operation.
3. The NAO announces the request and indicates the pending state using LEDs.
4. The operator presses the rear head tactile sensor continuously for three seconds.
5. The helper revalidates the request and executes it through the connection-manager adapter.
6. The helper persists a redacted result before returning it.
7. The broker reports success, rejection, timeout, or reconnection instructions to the UI.

## Connection changes and recovery

A successful network change may terminate the browser, SSH, camera, and Nemotron connections. Therefore the helper records the result locally before applying the final transition. When possible, the NAO announces the new address. The broker attempts reconnection without treating an expected transport loss as an operation failure.

Ethernet remains the preferred recovery path during development. The UI warns before an operation can remove the only known management path.

## Component responsibilities

### Web panel

- Render status, scan results, and saved profiles.
- Collect a password using a password input that is cleared after submission.
- Display explicit warnings and pending physical-confirmation state.
- Never store credentials in browser persistence.

### PC broker

- Bind to loopback only.
- Validate schema, origin, operation type, timeouts, and response size.
- Invoke a fixed robot helper command over SSH without shell interpolation.
- Redact sensitive fields from diagnostics.

### NAO helper

- Normalize the legacy NAOqi connection API behind a testable adapter.
- Subscribe to the rear tactile sensor and enforce a continuous three-second hold.
- Allow only status, scan, profiles, connect, disconnect, and forget operations.
- Persist redacted outcomes and provide deterministic exit statuses.

## Error handling

Expected outcomes are represented explicitly: `completed`, `rejected`, `confirmation_timeout`, `transport_lost_after_apply`, `unsupported`, and `failed`. Invalid requests fail closed. A tactile release before three seconds resets the confirmation timer.

## Testing strategy

- Unit tests for request validation, credential redaction, operation allowlisting, origin checks, and confirmation timing.
- Adapter tests with a fake connection manager for every operation and failure outcome.
- React tests for status rendering, password clearing, warnings, and pending confirmation.
- Integration tests with a fake SSH transport and simulated connection loss.
- Hardware validation over Ethernet before allowing Wi-Fi-only transitions.

## Acceptance criteria

- All six supported network operations are accessible from the web panel.
- No credential appears in application logs, WebSocket events, durable results, or committed fixtures.
- Mutating operations cannot execute without a continuous three-second rear-sensor hold.
- Releasing the sensor early or allowing the request to expire leaves network state unchanged.
- Expected connection loss is distinguishable from an unconfirmed or failed operation.
- Existing web-control and Nemotron tests remain green.
