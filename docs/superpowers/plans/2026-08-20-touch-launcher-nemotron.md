# Touch Launcher Nemotron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the middle-head-touch launcher as the sole supervisor that starts and stops the deployed NAO Control plus Nemotron services.

**Architecture:** `autoload.ini` loads `launcher.py` as a resident Python program. The launcher delegates service lifecycle to the deployed `start_nemotron.sh` and `stop_nemotron.sh`, and derives its state from robot PID files rather than stale `Popen` objects.

**Tech Stack:** Python 2.7, NAOqi ALMemory/ALTextToSpeech, POSIX shell, pytest on PC.

**Spec:** `docs/superpowers/specs/2026-08-15-nemotron-multimodal-agent-design.md`

## Global Constraints

- Keep the three-second middle tactile hold as the control/Choregraphe toggle.
- The NAO runs Python 2.7; no Python 3 syntax in robot runtime files.
- `NVIDIA_API_KEY` remains on the PC only.
- Starting services launches web control, camera and Nemotron gateway together.

---

### Task 1: Testable deployed-service supervisor

**Files:**
- Create: `nao/scripts/runtime/intelligence/service_supervisor.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_service_supervisor.py`

- [ ] Write failing tests for all four PID files being live and for invoking the exact start/stop shell scripts.
- [ ] Run the test and verify it fails because `NemotronServiceSupervisor` is absent.
- [ ] Implement Python-2-compatible PID checks and shell delegation.
- [ ] Run the test and commit the supervisor.

### Task 2: Make launcher use the supervisor

**Files:**
- Modify: `nao/scripts/runtime/launcher.py`
- Test: `nao/scripts/runtime/intelligence/tests/test_service_supervisor.py`

- [ ] Write failing tests proving launcher service state is derived from deployed PID files.
- [ ] Replace legacy `/home/nao/scripts` paths and direct child process tracking with the supervisor.
- [ ] Preserve `handle_long_press`: running services stop; stopped services start.
- [ ] Run runtime tests and commit.

### Task 3: Deploy and restore autoload contract

**Files:**
- Modify: `docs/nemotron/physical-test.md`

- [ ] Copy launcher and supervisor to `/home/nao/naoControl`.
- [ ] Back up and change autoload to load `launcher.py` under `[python]`.
- [ ] Start the launcher in foreground/background with a dedicated log, verify it sees current service state, then validate one three-second tactile transition.
- [ ] Run live port and PC-gateway handshake checks; commit documentation only.
