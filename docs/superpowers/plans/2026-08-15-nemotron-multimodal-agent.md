# Nemotron Multimodal Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Groq conversation subsystem with a physically activated, multimodal Nemotron agent whose PC-hosted MCP tools safely control approved NAOqi capabilities.

**Architecture:** NAO keeps a Python 2.7 mode controller, sensor adapter, safety supervisor, and action executor. A Python 3 PC gateway synchronizes interaction media, calls NVIDIA ASR/vision/agent endpoints, hosts MCP, validates tool calls, and sends signed semantic commands to the existing NAO Control execution layer.

**Tech Stack:** Python 2.7 and NAOqi 2.8 on NAO; Python 3.11+, `pytest`, `pydantic`, `httpx`, official MCP Python SDK, OpenAI-compatible NVIDIA NIM APIs, React for the existing web client.

## Global Constraints

- Startup mode is `WEB_CONTROL`; Web Control produces zero NVIDIA API requests.
- Left bumper held for 1.5 seconds toggles Nemotron mode; right bumper is hold-to-talk; both bumpers request local emergency stop.
- Cloud credentials exist only on the PC and enter through environment variables.
- NVIDIA HTTPS certificate verification is always enabled.
- Model output never reaches NAOqi without schema, policy, and robot-side validation.
- First-release body tools are `look`, `set_posture`, `gesture`, and allowlisted `run_behavior`; unrestricted joints and locomotion are excluded.
- Native NAO TTS is the first-release speech output.
- Python 2 code must parse and run on NAO's Python 2.7 runtime.
- Every functional task follows red-green-refactor and ends in a focused commit without AI attribution.
- Do not push the branch until automated tests and supervised robot tests are complete.

---

## File map

### Robot runtime

- `nao/scripts/runtime/intelligence/protocol.py`: Python 2-compatible envelopes, canonical JSON, HMAC verification, expiry, and replay guard.
- `nao/scripts/runtime/intelligence/mode_manager.py`: operating-state machine and bumper timing.
- `nao/scripts/runtime/intelligence/audio_capture.py`: bounded `ALAudioRecorder` push-to-talk capture and chunked base64 transfer.
- `nao/scripts/runtime/intelligence/safety_supervisor.py`: entry checks, heartbeat fail-safe, and emergency stop.
- `nao/scripts/runtime/intelligence/action_executor.py`: semantic action allowlist and translation to `NAOFacade`.
- `nao/scripts/runtime/intelligence/gateway_server.py`: authenticated PC gateway channel, heartbeats, events, commands, and results.
- `nao/scripts/runtime/control_server/server.py`: share `NAOFacade` and mode ownership with the intelligent gateway; reject web actions while Nemotron owns the body.
- `nao/scripts/runtime/launcher.py`: start/stop the intelligent gateway and preserve the head-touch Choregraphe control.
- `nao/deploy/structure.json` and `nao/deploy/deploy.py`: deploy the new runtime reproducibly.

### PC gateway

- `pc_gateway/pyproject.toml`: package metadata, runtime dependencies, test configuration, and console entry point.
- `pc_gateway/src/nao_gateway/config.py`: validated environment configuration.
- `pc_gateway/src/nao_gateway/protocol.py`: signed robot-protocol client implementation.
- `pc_gateway/src/nao_gateway/robot_client.py`: connection, heartbeat, event stream, command acknowledgements, and cancellation.
- `pc_gateway/src/nao_gateway/sensor_hub.py`: camera ring buffer, audio assembly, and synchronized state.
- `pc_gateway/src/nao_gateway/interaction_manager.py`: immutable interaction lifecycle.
- `pc_gateway/src/nao_gateway/nemotron/clients.py`: ASR, vision, and agent HTTP clients.
- `pc_gateway/src/nao_gateway/nemotron/orchestrator.py`: ASR/vision/agent sequencing and degraded vision behavior.
- `pc_gateway/src/nao_gateway/action_registry.py`: typed registry loader.
- `pc_gateway/src/nao_gateway/policy_engine.py`: model tool validation and safety preconditions.
- `pc_gateway/src/nao_gateway/mcp_server/server.py`: MCP resources and tools.
- `pc_gateway/src/nao_gateway/agent_host.py`: event-driven turn loop and tool-result feedback.
- `pc_gateway/src/nao_gateway/main.py`: composition root and shutdown.

### Configuration and documentation

- `.env.example`: variable names only; no credential values.
- `config/action_registry.json`: approved semantic actions and constraints.
- `config/behavior_registry.json`: stable IDs, installed behavior names, provenance, posture, and timeout.
- `docs/nemotron/`: installation, NVIDIA credentials, operation, security, MCP reference, testing, and rollback.

---

### Task 1: Remove legacy cloud secrets and establish PC configuration

**Files:**
- Create: `.env.example`
- Create: `pc_gateway/pyproject.toml`
- Create: `pc_gateway/src/nao_gateway/__init__.py`
- Create: `pc_gateway/src/nao_gateway/config.py`
- Create: `pc_gateway/tests/test_config.py`
- Modify: `.gitignore`
- Modify: `nao/scripts/runtime/llm_conversation/config.py`
- Modify: `nao/scripts/runtime/nao_conversation.py`
- Modify: `nao/scripts/runtime/llm_conversation/providers/base_provider.py`
- Modify: `nao/scripts/runtime/llm_conversation/providers/whisper_stt.py`
- Modify: root Groq/Gemini diagnostic scripts containing committed keys

**Interfaces:**
- Produces: `GatewaySettings.from_env(environ: Mapping[str, str]) -> GatewaySettings`
- Produces fields: `nvidia_api_key`, `nvidia_base_url`, `agent_model`, `vision_model`, `asr_url`, `robot_url`, `robot_shared_secret`

- [ ] **Step 1: Write failing configuration and secret-scan tests**

```python
def test_settings_require_secrets(monkeypatch):
    from nao_gateway.config import GatewaySettings, ConfigurationError
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="NVIDIA_API_KEY"):
        GatewaySettings.from_env(os.environ)

def test_nvidia_base_url_must_be_https(monkeypatch):
    env = valid_environment(NVIDIA_BASE_URL="http://example.test/v1")
    with pytest.raises(ConfigurationError, match="HTTPS"):
        GatewaySettings.from_env(env)
```

Add a repository test that scans tracked text files for known key prefixes and `CERT_NONE`, excluding a fixture containing only redacted examples.

- [ ] **Step 2: Run tests and confirm the configuration module and scan fail**

Run: `python -m pip install -e "pc_gateway[test]"`

Run: `python -m pytest pc_gateway/tests/test_config.py tests/test_no_tracked_secrets.py -v`

Expected: import failure for `nao_gateway.config` and failures listing tracked secret/TLS-bypass locations without printing complete credentials.

- [ ] **Step 3: Implement strict settings and remove every tracked credential/TLS bypass**

```python
@dataclass(frozen=True)
class GatewaySettings:
    nvidia_api_key: str
    nvidia_base_url: str
    agent_model: str
    vision_model: str
    asr_url: str
    robot_url: str
    robot_shared_secret: str

    @classmethod
    def from_env(cls, environ):
        required = ("NVIDIA_API_KEY", "NVIDIA_ASR_URL", "NAO_GATEWAY_SECRET")
        missing = [name for name in required if not environ.get(name)]
        if missing:
            raise ConfigurationError("Missing environment variables: " + ", ".join(missing))
        base_url = environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        if not base_url.startswith("https://"):
            raise ConfigurationError("NVIDIA_BASE_URL must use HTTPS")
        return cls(
            nvidia_api_key=environ["NVIDIA_API_KEY"],
            nvidia_base_url=base_url.rstrip("/"),
            agent_model=environ.get("NVIDIA_AGENT_MODEL", "nvidia/nemotron-3-nano-30b-a3b"),
            vision_model=environ.get("NVIDIA_VISION_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
            asr_url=environ["NVIDIA_ASR_URL"],
            robot_url=environ.get("NAO_GATEWAY_URL", "ws://nao.local:6674"),
            robot_shared_secret=environ["NAO_GATEWAY_SECRET"],
        )
```

Make legacy robot conversation modules refuse to start without environment-provided keys during the transition. Do not preserve fallback secrets. Keep SSL verification at its library default.

Declare these PC dependency ranges in `pyproject.toml`: `pydantic>=2.8,<3`, `httpx>=0.27,<1`, `websockets>=13,<16`, `mcp>=1.12,<2`; the `test` extra contains `pytest>=8,<9`, `pytest-asyncio>=0.24,<1`, and `respx>=0.21,<1`.

- [ ] **Step 4: Run security-focused tests**

Run: `python -m pytest pc_gateway/tests/test_config.py tests/test_no_tracked_secrets.py -v`

Expected: all pass; `git grep -n -E "gsk_|AIza|CERT_NONE" -- ':!*.md'` returns no secret or TLS-bypass implementation.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example pc_gateway tests \
  test_groq_simple.py test_groq_models.py test_gemini.py test_gemini_exhaustive.py \
  test_final_verification.py test_api_final.py \
  nao/scripts/diagnostics/test_groq_api.py \
  nao/scripts/runtime/nao_conversation.py \
  nao/scripts/runtime/test_whisper_nao.py \
  nao/scripts/runtime/llm_conversation
git commit -m "security: remove legacy cloud credentials"
```

Do not rewrite Git history in this task. Record mandatory key rotation and history cleanup in the security guide before any future push.

---

### Task 2: Implement the signed PC-to-robot protocol

**Files:**
- Create: `pc_gateway/src/nao_gateway/protocol.py`
- Create: `pc_gateway/tests/test_protocol.py`
- Create: `nao/scripts/runtime/intelligence/__init__.py`
- Create: `nao/scripts/runtime/intelligence/protocol.py`
- Create: `nao/scripts/runtime/intelligence/tests/test_protocol_py2.py`

**Interfaces:**
- Produces PC: `sign_envelope(payload: dict, secret: bytes) -> dict`
- Produces PC: `verify_envelope(envelope: dict, secret: bytes, now_ms: int, replay_guard: ReplayGuard) -> dict`
- Produces robot equivalents with Python 2-compatible syntax and identical canonical bytes
- Envelope fields: `protocol_version`, `message_type`, `message_id`, `issued_at_ms`, `expires_at_ms`, `payload`, `signature`

- [ ] **Step 1: Write shared golden-vector and rejection tests**

```python
def test_pc_signature_matches_robot_golden_vector():
    signed = sign_envelope(GOLDEN_PAYLOAD, b"test-secret")
    assert signed["signature"] == GOLDEN_SIGNATURE

@pytest.mark.parametrize("mutation", ["expired", "replayed", "bad_signature", "unknown_version"])
def test_invalid_envelopes_are_rejected(mutation):
    envelope = mutate(valid_signed_envelope(), mutation)
    with pytest.raises(ProtocolError):
        verify_envelope(envelope, b"test-secret", NOW_MS, ReplayGuard(100))
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest pc_gateway/tests/test_protocol.py -v`

Expected: import failure because protocol functions do not exist.

- [ ] **Step 3: Implement canonical JSON, HMAC-SHA256, expiry, and bounded replay protection**

Canonical body:

```python
json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
```

Signature:

```python
base64.b64encode(hmac.new(secret, canonical_body, hashlib.sha256).digest()).decode("ascii")
```

Use constant-time comparison. `ReplayGuard` stores at most 1,000 IDs and evicts expired entries.

- [ ] **Step 4: Run PC and Python 2 compatibility tests**

Run: `python -m pytest pc_gateway/tests/test_protocol.py nao/scripts/runtime/intelligence/tests/test_protocol_py2.py -v`

Run on a Python 2-equipped environment: `python2 -m pytest nao/scripts/runtime/intelligence/tests/test_protocol_py2.py -v`

Expected: matching golden signatures and all invalid-envelope cases rejected.

- [ ] **Step 5: Commit**

```bash
git add pc_gateway/src/nao_gateway/protocol.py pc_gateway/tests/test_protocol.py nao/scripts/runtime/intelligence
git commit -m "feat: add authenticated robot gateway protocol"
```

---

### Task 3: Build and test the robot operating-mode state machine

**Files:**
- Create: `nao/scripts/runtime/intelligence/mode_manager.py`
- Create: `nao/scripts/runtime/intelligence/tests/test_mode_manager.py`
- Modify: `nao/scripts/runtime/control_server/record_system.py`

**Interfaces:**
- Produces: `ModeManager.handle_bumper(left: bool, right: bool, now_ms: int) -> list[ModeEvent]`
- Produces: `ModeManager.handle_system(event_name: str, now_ms: int) -> list[ModeEvent]`
- States: `WEB_CONTROL`, `NEMOTRON_READY`, `CAPTURING`, `PROCESSING`, `ACTING`, `SPEAKING`, `EMERGENCY`
- Events: `MODE_ENTER_REQUESTED`, `MODE_EXIT_REQUESTED`, `CAPTURE_STARTED`, `CAPTURE_FINISHED`, `INTERACTION_CANCELLED`, `EMERGENCY_REQUESTED`

- [ ] **Step 1: Write transition, debounce, hold, and emergency tests**

```python
def test_left_hold_enters_nemotron_after_1500_ms():
    manager = ModeManager(initial_mode="WEB_CONTROL")
    assert manager.handle_bumper(True, False, 0) == []
    events = manager.handle_bumper(True, False, 1500)
    assert [event.name for event in events] == ["MODE_ENTER_REQUESTED"]

def test_right_release_finishes_capture():
    manager = ready_manager()
    assert manager.handle_bumper(False, True, 100)[0].name == "CAPTURE_STARTED"
    assert manager.handle_bumper(False, False, 900)[0].name == "CAPTURE_FINISHED"

def test_both_bumpers_preempt_every_state():
    manager = acting_manager()
    events = manager.handle_bumper(True, True, 500)
    assert manager.mode == "EMERGENCY"
    assert events[0].name == "EMERGENCY_REQUESTED"
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest nao/scripts/runtime/intelligence/tests/test_mode_manager.py -v`

Expected: import failure for `ModeManager`.

- [ ] **Step 3: Implement deterministic transitions without NAOqi dependencies**

Use injected `entry_check` and event callbacks; never call motion, audio, LEDs, or network from `ModeManager`. Require a release before recognizing a second hold. A simultaneous-bumper emergency has priority over every other event.

Modify `RecordSystem` so its bumper monitor cannot activate while the shared Mode Manager reports a Nemotron state.

- [ ] **Step 4: Run tests and Python 2 syntax verification**

Run: `python -m pytest nao/scripts/runtime/intelligence/tests/test_mode_manager.py -v`

Run: `python nao/scripts/test_python2_compatibility.py`

Expected: transitions pass and the compatibility scanner reports success.

- [ ] **Step 5: Commit**

```bash
git add nao/scripts/runtime/intelligence/mode_manager.py nao/scripts/runtime/intelligence/tests nao/scripts/runtime/control_server/record_system.py
git commit -m "feat: add physical Nemotron mode controller"
```

---

### Task 4: Add robot safety supervision and semantic action execution

**Files:**
- Create: `config/action_registry.json`
- Create: `config/behavior_registry.json`
- Create: `nao/scripts/runtime/intelligence/safety_supervisor.py`
- Create: `nao/scripts/runtime/intelligence/action_executor.py`
- Create: `nao/scripts/runtime/intelligence/tests/test_action_executor.py`
- Modify: `nao/scripts/runtime/control_server/commands/behavior_commands.py`

**Interfaces:**
- Produces: `SafetySupervisor.check_intelligent_entry() -> (bool, list[str])`
- Produces: `SafetySupervisor.emergency_stop(reason: str) -> dict`
- Produces: `ActionExecutor.execute(command: dict) -> dict`
- Consumes semantic actions: `get_robot_state`, `say`, `set_led`, `play_sound`, `look`, `set_posture`, `gesture`, `run_behavior`, `stop_all`

- [ ] **Step 1: Write allowlist, precondition, timeout, and stop tests using a fake facade**

```python
def test_unknown_action_is_rejected_without_facade_call():
    facade = FakeNaoFacade()
    result = ActionExecutor(facade, registry()).execute(command("move", {"joint": "HeadYaw"}))
    assert result["status"] == "rejected"
    assert facade.calls == []

def test_behavior_requires_known_posture_and_registry_id():
    facade = FakeNaoFacade(posture="Crouch")
    result = executor(facade).execute(command("run_behavior", {"behavior_id": "wave"}))
    assert result["status"] == "rejected"

def test_emergency_stop_bypasses_queue():
    supervisor = SafetySupervisor(FakeNaoFacade(moving=True))
    supervisor.emergency_stop("both_bumpers")
    assert supervisor.facade.calls[:2] == [("stop_move",), ("stop_all_behaviors",)]
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest nao/scripts/runtime/intelligence/tests/test_action_executor.py -v`

Expected: missing registry/executor modules.

- [ ] **Step 3: Implement registry-backed translation and safety checks**

Use stable behavior IDs in `behavior_registry.json`; resolve exact installed package names once at startup. Remove substring fallback from agent execution. Clamp tool-visible speed/intensity to registry maxima. Preserve the existing web behavior classes for Web Control.

- [ ] **Step 4: Run focused tests and existing command tests**

Run: `python -m pytest nao/scripts/runtime/intelligence/tests/test_action_executor.py nao/scripts/diagnostics/test/test_control_server_action.py -v`

Expected: all semantic-action tests pass; existing command behavior remains compatible.

- [ ] **Step 5: Commit**

```bash
git add config nao/scripts/runtime/intelligence nao/scripts/runtime/control_server/commands/behavior_commands.py
git commit -m "feat: enforce safe semantic NAO actions"
```

---

### Task 5: Implement the authenticated robot gateway and audio capture

**Files:**
- Create: `nao/scripts/runtime/intelligence/audio_capture.py`
- Create: `nao/scripts/runtime/intelligence/gateway_server.py`
- Create: `nao/scripts/runtime/intelligence/tests/test_gateway_server.py`
- Modify: `nao/scripts/runtime/control_server/server.py`
- Modify: `nao/scripts/runtime/launcher.py`

**Interfaces:**
- Gateway port: `6674`
- Consumes signed message types: `hello`, `heartbeat`, `mode_result`, `command`, `cancel`
- Produces signed types: `hello_result`, `mode_event`, `audio_result`, `state`, `command_result`, `emergency`
- Produces: `AudioCapture.start(interaction_id: str)`, `AudioCapture.stop() -> AudioResult`

- [ ] **Step 1: Write fake-WebSocket tests for authentication, heartbeat loss, mode events, audio limits, and command acknowledgements**

```python
def test_unsigned_command_is_rejected():
    server = gateway_with_fakes()
    result = server.handle_message({"message_type": "command"}, now_ms=1000)
    assert result["payload"]["status"] == "rejected"

def test_heartbeat_loss_stops_body_and_exits_intelligent_mode():
    server = gateway_with_fakes(mode="NEMOTRON_READY", last_heartbeat_ms=0)
    server.tick(now_ms=2001)
    assert server.safety.emergency_reasons == ["gateway_heartbeat_lost"]

def test_audio_capture_stops_at_twenty_seconds():
    capture = AudioCapture(FakeAudioRecorder(), clock=FakeClock())
    capture.start("interaction-1")
    capture.tick(elapsed_ms=20000)
    assert capture.result.duration_ms == 20000
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest nao/scripts/runtime/intelligence/tests/test_gateway_server.py -v`

Expected: missing gateway and audio modules.

- [ ] **Step 3: Implement gateway composition and bounded WAV transfer**

Use `ALAudioRecorder` at 16 kHz mono for the first hardware-compatible release. On release, read the WAV in bounded chunks and base64-encode it in the signed `audio_result`; reject payloads above the 20-second maximum. Delete the temporary file after acknowledged transfer.

Run the gateway in a separate process started by `launcher.py`. Share mode ownership with the existing control server using a small atomic JSON state file under `/tmp/nao_control_mode.json`; the Web Control server rejects body actions whenever the mode is not `WEB_CONTROL`.

- [ ] **Step 4: Run gateway, compatibility, and web-control regression tests**

Run: `python -m pytest nao/scripts/runtime/intelligence/tests/test_gateway_server.py -v`

Run: `python tools/verify_control_server_clean.py`

Run: `python nao/scripts/test_python2_compatibility.py`

Expected: signed gateway paths pass, heartbeat fail-safe works, and Web Control commands remain available only in Web Control mode.

- [ ] **Step 5: Commit**

```bash
git add nao/scripts/runtime/intelligence nao/scripts/runtime/control_server/server.py nao/scripts/runtime/launcher.py
git commit -m "feat: connect physical mode events to PC gateway"
```

---

### Task 6: Build the PC robot client, sensor hub, and interaction manager

**Files:**
- Create: `pc_gateway/src/nao_gateway/robot_client.py`
- Create: `pc_gateway/src/nao_gateway/sensor_hub.py`
- Create: `pc_gateway/src/nao_gateway/interaction_manager.py`
- Create: `pc_gateway/tests/test_robot_client.py`
- Create: `pc_gateway/tests/test_sensor_hub.py`
- Modify: `nao/scripts/runtime/video_stream.py`

**Interfaces:**
- Produces: `RobotClient.events() -> AsyncIterator[RobotEvent]`
- Produces: `RobotClient.execute(action: str, arguments: dict, interaction_id: str) -> CommandResult`
- Produces: `SensorHub.add_frame(jpeg: bytes, captured_at_ms: int)`
- Produces: `InteractionManager.finish(interaction_id: str, audio: bytes, ended_at_ms: int) -> Interaction`

- [ ] **Step 1: Write async client and synchronization tests**

```python
async def test_robot_client_correlates_command_result():
    client, socket = connected_fake_client()
    pending = asyncio.create_task(client.execute("set_led", {"color": "red"}, "i-1"))
    command_id = socket.last_payload["command_id"]
    socket.feed(command_result(command_id, "completed"))
    assert (await pending).status == "completed"

def test_interaction_selects_before_middle_and_release_frames():
    hub = populated_sensor_hub(frame_times=[900, 1100, 1500, 1990])
    interaction = manager(hub).finish("i-1", b"wav", ended_at_ms=2000)
    assert [frame.captured_at_ms for frame in interaction.frames] == [900, 1500, 1990]
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest pc_gateway/tests/test_robot_client.py pc_gateway/tests/test_sensor_hub.py -v`

Expected: missing classes.

- [ ] **Step 3: Implement heartbeat, correlation, cancellation, ring buffers, and immutable interactions**

Add `/snapshot.jpg` to the existing MJPEG server for diagnostics. The Sensor Hub consumes MJPEG locally into a five-second bounded deque. Raw frames and audio are released after the turn unless test retention is explicitly enabled.

- [ ] **Step 4: Run tests including disconnect and cancellation cases**

Run: `python -m pytest pc_gateway/tests/test_robot_client.py pc_gateway/tests/test_sensor_hub.py -v`

Expected: no orphan futures, buffers remain bounded, and interaction timestamps are deterministic.

- [ ] **Step 5: Commit**

```bash
git add pc_gateway/src/nao_gateway pc_gateway/tests nao/scripts/runtime/video_stream.py
git commit -m "feat: synchronize NAO audio vision and state"
```

---

### Task 7: Add NVIDIA ASR, vision, and agent clients

**Files:**
- Create: `pc_gateway/src/nao_gateway/nemotron/__init__.py`
- Create: `pc_gateway/src/nao_gateway/nemotron/clients.py`
- Create: `pc_gateway/src/nao_gateway/nemotron/orchestrator.py`
- Create: `pc_gateway/tests/nemotron/test_clients.py`
- Create: `pc_gateway/tests/nemotron/test_orchestrator.py`

**Interfaces:**
- Produces: `AsrClient.transcribe(audio_wav: bytes, language: str = "es") -> Transcript`
- Produces: `VisionClient.observe(frames: Sequence[bytes]) -> VisualObservation`
- Produces: `AgentClient.decide(context: AgentContext, tools: list[dict]) -> AgentDecision`
- Produces: `NemotronOrchestrator.process(interaction: Interaction, history: ConversationSummary, tools: list[dict]) -> AgentDecision`

- [ ] **Step 1: Write HTTP fixture tests for authorization, TLS defaults, response parsing, timeouts, and visual degradation**

```python
async def test_agent_uses_nvidia_openai_endpoint(respx_mock, settings):
    route = respx_mock.post(settings.nvidia_base_url + "/chat/completions").mock(
        return_value=httpx.Response(200, json=agent_tool_response())
    )
    decision = await AgentClient(settings).decide(agent_context(), tool_schemas())
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"
    assert decision.speech == "La botella es roja."

async def test_vision_failure_allows_non_visual_question():
    result = await orchestrator(vision_error=True).process(interaction("Hola"), summary(), tools=[])
    assert result.speech
    assert result.tool_calls == []
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest pc_gateway/tests/nemotron -v`

Expected: missing Nemotron clients.

- [ ] **Step 3: Implement clients with strict Pydantic response models**

Use `https://integrate.api.nvidia.com/v1/chat/completions` for agent and vision OpenAI-compatible calls. Make `NVIDIA_ASR_URL` fully configurable because NVIDIA Speech NIM deployments expose account/deployment-specific endpoints. Set explicit connect/read timeouts, one retry only before any response body, and a stable idempotency key per interaction.

Require vision JSON fields `scene_summary`, `objects`, `people`, and `uncertainties`. Do not pass vision reasoning text to the agent.

- [ ] **Step 4: Run client tests and a credential-free contract smoke test**

Run: `python -m pytest pc_gateway/tests/nemotron -v`

Run: `python -m nao_gateway.nemotron.clients --validate-config` with fixture environment variables.

Expected: all fixture tests pass without real NVIDIA traffic.

- [ ] **Step 5: Commit**

```bash
git add pc_gateway/src/nao_gateway/nemotron pc_gateway/tests/nemotron
git commit -m "feat: add NVIDIA multimodal model clients"
```

---

### Task 8: Implement the Action Registry, policy engine, and MCP server

**Files:**
- Create: `pc_gateway/src/nao_gateway/action_registry.py`
- Create: `pc_gateway/src/nao_gateway/policy_engine.py`
- Create: `pc_gateway/src/nao_gateway/mcp_server/__init__.py`
- Create: `pc_gateway/src/nao_gateway/mcp_server/server.py`
- Create: `pc_gateway/tests/test_policy_engine.py`
- Create: `pc_gateway/tests/test_mcp_server.py`

**Interfaces:**
- Produces: `ActionRegistry.tool_schemas() -> list[dict]`
- Produces: `PolicyEngine.authorize(tool_call: ToolCall, robot_state: RobotState, turn: TurnBudget) -> AuthorizedCommand`
- Produces MCP resources: `nao://state`, `nao://camera/latest`, `nao://behaviors`, `nao://capabilities`
- Produces MCP tools with the exact first-release action names from Task 4

- [ ] **Step 1: Write adversarial policy and MCP schema tests**

```python
@pytest.mark.parametrize("call", [
    {"name": "move", "arguments": {"joint": "HeadYaw"}},
    {"name": "run_behavior", "arguments": {"behavior_id": "../../tmp/x"}},
    {"name": "say", "arguments": {"text": "x" * 2001}},
])
def test_unsafe_calls_are_rejected(call):
    with pytest.raises(PolicyViolation):
        policy().authorize(ToolCall.model_validate(call), safe_state(), TurnBudget())

async def test_mcp_run_behavior_uses_policy_and_robot_client():
    result = await mcp_harness().call_tool("run_behavior", {"behavior_id": "wave"})
    assert result["status"] == "completed"
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest pc_gateway/tests/test_policy_engine.py pc_gateway/tests/test_mcp_server.py -v`

Expected: missing policy and MCP modules.

- [ ] **Step 3: Implement strict registry models, per-turn budget, resource locks, and FastMCP bindings**

Use the official MCP Python SDK. MCP handlers call `PolicyEngine` and `RobotClient`; they never construct raw robot action messages themselves. Limit speech length, enum values, speeds, timeouts, three tools per turn, and one body action per turn.

- [ ] **Step 4: Run policy/MCP tests and inspect exported tools**

Run: `python -m pytest pc_gateway/tests/test_policy_engine.py pc_gateway/tests/test_mcp_server.py -v`

Run: `python -m nao_gateway.mcp_server.server --list-tools`

Expected: only approved first-release tools and resources are printed.

- [ ] **Step 5: Commit**

```bash
git add pc_gateway/src/nao_gateway/action_registry.py pc_gateway/src/nao_gateway/policy_engine.py pc_gateway/src/nao_gateway/mcp_server pc_gateway/tests
git commit -m "feat: expose policy-controlled NAO MCP tools"
```

---

### Task 9: Compose the end-to-end agent host

**Files:**
- Create: `pc_gateway/src/nao_gateway/session_memory.py`
- Create: `pc_gateway/src/nao_gateway/agent_host.py`
- Create: `pc_gateway/src/nao_gateway/main.py`
- Create: `pc_gateway/tests/test_agent_host.py`
- Create: `pc_gateway/tests/test_end_to_end.py`

**Interfaces:**
- Produces: `AgentHost.run() -> None`
- Consumes robot events: mode enter/exit, capture start/finish, emergency, disconnect
- Produces robot commands through MCP only
- Maintains `ConversationSummary` scoped to one Nemotron-mode session

- [ ] **Step 1: Write end-to-end fake robot/fake NVIDIA tests**

```python
async def test_push_to_talk_answers_and_executes_approved_led_tool():
    system = end_to_end_system(
        transcript="¿De qué color es la botella?",
        vision=red_bottle_observation(),
        decision=decision("Es roja.", tool("set_led", color="red")),
    )
    await system.robot.emit(capture_finished_event("i-1", wav_bytes()))
    await system.wait_idle()
    assert system.robot.completed_actions == ["set_led", "say"]
    assert system.robot.say_text == "Es roja."

async def test_mode_exit_cancels_cloud_and_never_executes_pending_tool():
    system = end_to_end_system(agent_blocked=True)
    await system.robot.emit(capture_finished_event("i-1", wav_bytes()))
    await system.robot.emit(mode_exit_event())
    assert system.robot.completed_actions == ["stop_all"]
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest pc_gateway/tests/test_agent_host.py pc_gateway/tests/test_end_to_end.py -v`

Expected: missing Agent Host composition.

- [ ] **Step 3: Implement the event loop, cancellation scopes, tool-result feedback, TTS sequencing, and bounded session summary**

The Agent Host calls the orchestrator only after `CAPTURE_FINISHED`. Tool calls are executed serially through MCP. `say` runs after body tools unless the model explicitly returns speech-only. Mode exit and emergency cancel all HTTP tasks and invoke `stop_all` without waiting for cancellation completion.

- [ ] **Step 4: Run all PC gateway tests**

Run: `python -m pytest pc_gateway/tests -v`

Expected: complete fake end-to-end interaction passes; no network or robot is required.

- [ ] **Step 5: Commit**

```bash
git add pc_gateway/src/nao_gateway pc_gateway/tests
git commit -m "feat: orchestrate multimodal Nemotron interactions"
```

---

### Task 10: Complete deployment, remove the old conversation runtime, and document operation

**Files:**
- Delete: `nao/scripts/runtime/nao_conversation.py`
- Delete: `nao/scripts/runtime/llm_conversation/`
- Modify: `nao/scripts/runtime/control_server/command_factory.py`
- Modify: `nao/scripts/runtime/control_server/commands/__init__.py`
- Delete: `nao/scripts/runtime/control_server/commands/conversation_commands.py`
- Modify: `nao/deploy/deploy.py`
- Modify: `nao/deploy/structure.json`
- Modify: `README.md`
- Modify: `nao/README_NAO.md`
- Create: `docs/nemotron/installation.md`
- Create: `docs/nemotron/nvidia-api.md`
- Create: `docs/nemotron/operation.md`
- Create: `docs/nemotron/mcp-tools.md`
- Create: `docs/nemotron/security.md`
- Create: `docs/nemotron/testing.md`
- Create: `docs/nemotron/rollback.md`

**Interfaces:**
- Removes WebSocket actions: `startConversation`, `stopConversation`, `getConversationStatus`
- Adds documented processes: robot launcher and `nao-nemotron-gateway`

- [ ] **Step 1: Write deployment-manifest and legacy-removal tests**

```python
def test_deploy_manifest_contains_intelligent_runtime():
    manifest = json.loads(Path("nao/deploy/structure.json").read_text())
    paths = flatten_manifest_paths(manifest)
    assert "scripts/runtime/intelligence/gateway_server.py" in paths

def test_legacy_conversation_actions_are_absent():
    source = Path("nao/scripts/runtime/control_server/command_factory.py").read_text()
    assert "startConversation" not in source
    assert "GroqProvider" not in tracked_python_source()
```

- [ ] **Step 2: Run tests and confirm they fail while legacy code remains**

Run: `python -m pytest tests/test_deploy_manifest.py tests/test_legacy_conversation_removed.py -v`

Expected: manifest omission and legacy-action assertions fail.

- [ ] **Step 3: Remove legacy modules, update deployment, and write complete operator documentation**

`docs/nemotron/nvidia-api.md` must document:

```text
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_AGENT_MODEL=nvidia/nemotron-3-nano-30b-a3b
NVIDIA_VISION_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
NVIDIA_API_KEY=<created in NVIDIA Build; never commit>
NVIDIA_ASR_URL=<copied from the selected NVIDIA Speech NIM API page>
```

It must explain Build trial limitations, key rotation, a curl health/model test that does not print the key, and how to verify zero requests in Web Control. Security documentation must list every formerly exposed credential provider as requiring rotation and explain that current-history cleanup is still required before push.

- [ ] **Step 4: Run repository verification**

Run: `python -m pytest pc_gateway/tests tests -v`

Run: `python nao/scripts/test_python2_compatibility.py`

Run: `cd NaoControlReact && npm test -- --runInBand && npm run build`

Run: `git grep -n -E "gsk_|AIza|CERT_NONE|startConversation|GroqProvider" -- ':!docs/**'`

Expected: tests/build pass and grep returns no implementation matches.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: complete Nemotron migration and deployment guide"
```

---

### Task 11: Perform final security, integration, and supervised hardware verification

**Files:**
- Create: `docs/nemotron/test-results.md`
- Modify only files required by defects discovered during verification

**Interfaces:**
- Consumes the complete system produced by Tasks 1-10
- Produces a dated verification record with command output summaries and hardware observations

- [ ] **Step 1: Run the full automated matrix from a clean checkout of the branch**

```text
python -m pytest pc_gateway/tests tests -v
python nao/scripts/test_python2_compatibility.py
cd NaoControlReact && npm test -- --runInBand && npm run build
git diff main...HEAD --check
```

Expected: all commands pass. Record versions and counts in `test-results.md`.

- [ ] **Step 2: Run a security-focused diff review**

Verify secrets, TLS, HMAC/replay/expiry, role separation, input schemas, file handling, network exposure, cancellation, and denial-of-service bounds. Record each reviewed boundary and any fixes in `test-results.md`.

- [ ] **Step 3: Run NVIDIA smoke tests with user-provided environment variables**

```text
python -m nao_gateway.main --check-nvidia
python -m nao_gateway.main --shadow-mode
```

Expected: ASR, vision, and agent endpoints report healthy; one recorded fixture produces Spanish speech and a schema-valid shadow tool call without contacting the robot.

- [ ] **Step 4: Execute the supervised robot checklist**

Test startup Web Control, left hold entry/exit, right push-to-talk, simultaneous emergency, LED states, camera-grounded question, speech-only question, approved behavior, invalid tool rejection, Wi-Fi loss, PC loss, cloud timeout, and shutdown. Use a clear 1.5 m x 1.5 m area, battery above 30 percent, Fall Manager enabled, and an operator beside the robot.

Expected: every acceptance criterion is marked pass or accompanied by a blocking defect. Do not push with a blocking defect.

- [ ] **Step 5: Fix discovered defects with focused tests, rerun the affected and full suites, then commit the verification record**

```bash
git add docs/nemotron/test-results.md changed-tested-files
git commit -m "test: verify Nemotron agent integration"
```

Do not push. Report the branch, commit list, automated results, hardware results, remaining limitations, and the explicit need for credential-history cleanup before publishing.
