# NAO Action Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make NAO LED, posture, and allowlisted behavior actions reliable and discoverable to Nemotron.

**Architecture:** Preserve the existing PC policy and signed NAO executor boundary. Normalize model-visible tool constraints on the PC, keep physical enforcement on the NAO, and use exact NAOqi LED overloads instead of packed-color overload resolution.

**Tech Stack:** Python 3.13 PC gateway, Python 2.7 NAO runtime, pytest, NAOqi `ALLeds`, `ALRobotPosture`, `ALBehaviorManager`.

**Spec:** `docs/superpowers/specs/2026-08-24-nao-action-reliability-design.md`

## Global Constraints

- Default posture speed is exactly `0.35`; maximum posture speed remains exactly `0.50`.
- Only one body action is authorized per turn, and it requires explicit transcript intent.
- No locomotion, unrestricted joints, unregistered behaviors, or browser-selected package names.
- Face and chest colors use `fadeRGB(group, r, g, b, duration)` with native strings and floats.
- `EarLeds` supports only `blue` and `off` through intensity-based `fade`.
- Python files deployed to the NAO remain Python 2.7 compatible.

---

### Task 1: Make the allowlisted action layer reliable

**Files:**
- Modify: `nao/scripts/runtime/control_server/facades/nao_facade.py`
- Modify: `nao/scripts/runtime/intelligence/action_executor.py`
- Modify: `nao/scripts/runtime/intelligence/tests/test_nao_facade_runtime.py`
- Modify: `nao/scripts/runtime/intelligence/tests/test_action_executor.py`
- Modify: `pc_gateway/src/nao_gateway/agent_host.py`
- Modify: `pc_gateway/src/nao_gateway/nemotron.py`
- Modify: `pc_gateway/src/nao_gateway/policy_engine.py`
- Modify: `pc_gateway/tests/test_agent_host.py`
- Modify: `pc_gateway/tests/test_nemotron_client.py`
- Modify: `pc_gateway/tests/test_policy_engine.py`
- Modify: `config/action_registry.json`
- Modify: `docs/nemotron/physical-test.md`

**Interfaces:**
- Consumes: `AgentHost.tool_schemas() -> list[dict]`, `NemotronClient.decide(transcript, scene, tools)`, `ActionExecutor.execute(command)`, `NAOFacade.set_led_rgb(group, r, g, b, duration)`.
- Produces: `run_behavior.constraints.allowed_behavior_ids: list[str]`; normalized `set_posture.arguments.speed: float`; group-aware LED validation and exact NAOqi calls.

- [ ] **Step 1: Write failing LED facade tests**

Add tests that require the exact calls:

```python
assert facade.set_led_rgb("FaceLeds", 1.0, 0.0, 0.0, 0.3) is True
assert facade.leds.calls[-1] == (
    "fadeRGB", "FaceLeds", 1.0, 0.0, 0.0, 0.3,
)

assert facade.set_led_rgb("EarLeds", 0.0, 0.0, 1.0, 0.3) is True
assert facade.leds.calls[-1] == ("fade", "EarLeds", 1.0, 0.3)
```

- [ ] **Step 2: Run the focused LED tests and observe failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest nao\scripts\runtime\intelligence\tests\test_nao_facade_runtime.py nao\scripts\runtime\intelligence\tests\test_action_executor.py -q
```

Expected: failure because the facade currently calls the packed integer overload and the executor permits impossible ear colors.

- [ ] **Step 3: Implement exact LED behavior**

Change the facade call to:

```python
self.leds.fadeRGB(
    str(group), float(r), float(g), float(b), float(duration)
)
```

For `EarLeds`, use:

```python
intensity = float(b)
self.leds.fade(str(group), intensity, float(duration))
```

In both `PolicyEngine` and `ActionExecutor`, reject `EarLeds` unless `color` is `blue` or `off`.

- [ ] **Step 4: Write failing speed and behavior-catalog tests**

Require `0.35` when speed is omitted and require exact behavior IDs in the tool schema:

```python
assert robot.actions[0] == (
    "set_posture", {"posture": "Stand", "speed": 0.35},
)

run_behavior = next(
    tool for tool in host.tool_schemas() if tool["name"] == "run_behavior"
)
assert run_behavior["constraints"]["allowed_behavior_ids"] == [
    "dance_gangnam", "dance_macarena", "dance_siu", "no",
    "play_saxophone", "taichi", "thinking", "wave", "yes",
]
```

Require `_function_parameters("run_behavior", constraints)` to emit those values as the `behavior_id.enum`.

- [ ] **Step 5: Run the focused PC tests and observe failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest pc_gateway\tests\test_agent_host.py pc_gateway\tests\test_nemotron_client.py pc_gateway\tests\test_policy_engine.py -q
```

Expected: failure because posture defaults to `0.30` and behavior IDs are not propagated.

- [ ] **Step 6: Implement speed normalization and behavior discovery**

Build the behavior constraints from sorted registry keys in `AgentHost.tool_schemas()`. In `PolicyEngine.authorize`, copy posture arguments, set missing `speed` to `0.35`, coerce it to `float`, and clamp it to the registry maximum before returning the signed command.

Update `DECISION_SYSTEM_PROMPT` posture examples to `0.35` and add concise behavior examples using only IDs supplied by the schema. Update `_function_parameters` so `run_behavior.behavior_id` is an enum from `allowed_behavior_ids`.

- [ ] **Step 7: Run all relevant suites**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests nao\scripts\runtime\intelligence\tests pc_gateway\tests -q
```

Expected: all tests pass with no collection errors.

- [ ] **Step 8: Document the physical verification matrix**

Update `docs/nemotron/physical-test.md` with commands for `set_led` on face, chest, and ears; `set_posture` at `0.35`; and each behavior ID. Record that behavior packages must be installed in Choregraphe when `unknown_behavior` or `facade_failed` appears.

- [ ] **Step 9: Commit the implementation**

```powershell
git add config/action_registry.json nao/scripts/runtime pc_gateway docs/nemotron/physical-test.md
git commit -m "fix: expand reliable NAO action execution"
```

