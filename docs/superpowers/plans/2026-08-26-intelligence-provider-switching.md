# Intelligent Provider Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent web-controlled Nemotron/Gemma selection and make model-requested eye colors visibly coexist with intelligent-mode indicators.

**Architecture:** The NAO stores only the provider identifier and publishes it through the authenticated gateway. A PC-side router owns lazy provider clients and switches only after validating availability. A robot-local LED controller serializes temporary model colors and mode colors.

**Tech Stack:** Python 2.7/NAOqi, Python 3.11/httpx/pydantic, signed WebSocket protocol, React 19/Jest.

**Spec:** `docs/superpowers/specs/2026-08-26-intelligence-provider-switching.md`

## Global Constraints

- Never store NVIDIA credentials or the Gemma endpoint in the browser or NAO configuration.
- Keep all physical actions behind the existing registry, policy engine, and NAO-local executor.
- Gemma defaults to PC loopback `http://127.0.0.1:8080/v1` and does not accept a robot-selected URL.
- Provider changes become active before the next interaction, never halfway through a turn.
- Face LED overrides last three seconds and cannot overwrite a newer mode transition.

---

### Task 1: Deterministic intelligent LED ownership

**Files:**
- Create: `nao/scripts/runtime/intelligence/led_controller.py`
- Modify: `nao/scripts/runtime/intelligence/gateway_server.py`
- Modify: `nao/scripts/runtime/intelligence/action_executor.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_led_controller.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_gateway_server.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_action_executor.py`

**Interfaces:**
- Produces: `IntelligenceLedController.set_mode(mode)` and `show_action(group, rgb)`.
- Consumes: `NAOFacade.set_led_rgb(group, r, g, b, duration)`.

- [ ] **Step 1: Write failing tests** proving a face action survives turn completion, restores after three seconds, and a newer mode transition invalidates the old restoration.
- [ ] **Step 2: Run** `python -m pytest nao/scripts/runtime/intelligence/tests/test_led_controller.py nao/scripts/runtime/intelligence/tests/test_gateway_server.py nao/scripts/runtime/intelligence/tests/test_action_executor.py -q` and confirm failures are caused by the missing controller behavior.
- [ ] **Step 3: Implement** the controller with injected timers, route mode writes through it, and route model LED actions through `show_action`.
- [ ] **Step 4: Re-run** the focused test command and require zero failures.
- [ ] **Step 5: Commit** with `fix: preserve requested intelligent led colors`.

### Task 2: PC provider adapters and safe router

**Files:**
- Create: `pc_gateway/src/nao_gateway/providers.py`
- Modify: `pc_gateway/src/nao_gateway/nemotron.py`
- Modify: `pc_gateway/src/nao_gateway/config.py`
- Modify: `pc_gateway/src/nao_gateway/agent_host.py`
- Test: `pc_gateway/tests/test_providers.py`
- Test: `pc_gateway/tests/test_config.py`

**Interfaces:**
- Produces: `ProviderRouter.activate(name)`, `ProviderRouter.perceive(...)`, `ProviderRouter.decide(...)`, and `ProviderRouter.status()`.
- Produces: `GemmaLocalClient` using PC-only `GEMMA_BASE_URL` and `GEMMA_MODEL` settings.
- Consumes: the existing `Perception`, `AgentDecision`, and tool schemas.

- [ ] **Step 1: Write failing tests** for lazy Nemotron creation, Gemma health/model discovery, Gemma WAV/image payloads, rejected unknown providers, and preserving the previous provider after failed activation.
- [ ] **Step 2: Run** `python -m pytest pc_gateway/tests/test_providers.py pc_gateway/tests/test_config.py -q` and confirm feature-missing failures.
- [ ] **Step 3: Implement** conditional settings, the local Gemma adapter, and the router without allowing remotely supplied endpoints.
- [ ] **Step 4: Re-run** the focused tests and require zero failures.
- [ ] **Step 5: Commit** with `feat: add safe Nemotron and Gemma provider router`.

### Task 3: Persist and synchronize provider selection

**Files:**
- Create: `nao/scripts/runtime/intelligence/provider_config.py`
- Modify: `nao/scripts/runtime/intelligence/gateway_server.py`
- Modify: `nao/scripts/runtime/control_server/commands/nemotron_commands.py`
- Modify: `nao/scripts/runtime/control_server/command_factory.py`
- Modify: `pc_gateway/src/nao_gateway/main.py`
- Modify: `pc_gateway/src/nao_gateway/robot_client.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_provider_config.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_nemotron_control_command.py`
- Test: `pc_gateway/tests/test_main.py`
- Test: `pc_gateway/tests/test_robot_client.py`

**Interfaces:**
- Produces: atomic `ProviderConfigStore.load/save`, web actions `intelligenceProviderStatus` and `setIntelligenceProvider`, and signed `provider_config` gateway events.
- Consumes: `ProviderRouter.activate(name)`; only `nemotron` and `gemma_local` are accepted.

- [ ] **Step 1: Write failing tests** for allowlisted persistence, malformed-file fallback, authorized web mutation, signed synchronization, and deferred PC activation through the session queue.
- [ ] **Step 2: Run** the four focused test files and confirm expected feature-missing failures.
- [ ] **Step 3: Implement** atomic robot storage and synchronization without transmitting keys or URLs.
- [ ] **Step 4: Re-run** focused tests and require zero failures.
- [ ] **Step 5: Commit** with `feat: synchronize intelligent provider selection`.

### Task 4: Web provider control and observability

**Files:**
- Modify: `NaoControlReact/src/services/nemotronApi.js`
- Modify: `NaoControlReact/src/services/nemotronApi.test.js`
- Modify: `NaoControlReact/src/components/NemotronMenu.js`
- Modify: `NaoControlReact/src/components/NemotronMenu.css`
- Modify: `NaoControlReact/src/components/NemotronMenu.test.js`

**Interfaces:**
- Consumes: `nemotronApi.providerStatus()` and `nemotronApi.setProvider(name)`.
- Produces: accessible provider selector, save action, active/selected state, health, and bounded error text.

- [ ] **Step 1: Write failing Jest tests** for loading status, saving Gemma, rejected saves, and no endpoint/key fields in the rendered panel.
- [ ] **Step 2: Run** `npm test -- --watchAll=false --runTestsByPath src/services/nemotronApi.test.js src/components/NemotronMenu.test.js` from `NaoControlReact` and confirm feature-missing failures.
- [ ] **Step 3: Implement** the API calls and accessible UI while keeping the existing transcript, response, and action cards.
- [ ] **Step 4: Re-run** focused Jest tests and require zero failures.
- [ ] **Step 5: Commit** with `feat: select intelligent provider from web control`.

### Task 5: Documentation, compatibility, and security verification

**Files:**
- Modify: `docs/nemotron/operation.md`
- Modify: `docs/nemotron/installation.md`
- Modify: `.env.example`
- Modify: deployment bundle inputs if required by existing packaging tests.

**Interfaces:**
- Documents: local Gemma prerequisite, selector behavior, LED ownership, logs, rollback, and PC-only configuration.

- [ ] **Step 1: Update documentation and example variables** without including real credentials.
- [ ] **Step 2: Run** all Python 2-compatible robot tests, all PC gateway tests, React tests, and React production build.
- [ ] **Step 3: Run** a scoped security diff review covering every changed file and remediate confirmed findings.
- [ ] **Step 4: Re-run** all verification after any remediation.
- [ ] **Step 5: Commit** with `docs: document provider switching and led behavior` and leave the branch unpushed until physical NAO validation.
