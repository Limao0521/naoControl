# One-command NAO deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the NAO-side runtime from Windows with one command and validate it remotely.

**Architecture:** A PowerShell script creates a temporary archive from `nao`, `config`, and the built web UI; transfers it with SCP; replaces `/home/nao/naoControl` while preserving the robot secret; then compiles and verifies required runtime files. It excludes `.env` and does not touch `autoload.ini`.

**Tech Stack:** PowerShell 7, OpenSSH, NAO Linux shell, Python 2.

**Spec:** `docs/nemotron/physical-test.md`

### Task 1: Test deployment contract

**Files:**

- Create: `tests/test_deploy_script.py`
- Create: `tools/deploy-nao.ps1`

- [ ] Write tests that assert the script excludes `.env`, preserves `robot_gateway.secret`, compiles `gateway_server.py`, and never modifies `autoload.ini`.
- [ ] Run the tests and confirm failure before implementation.
- [ ] Implement staging, SCP, atomic remote replacement, and validation.
- [ ] Re-run the tests and commit `feat: add one-command NAO deployment`.

### Task 2: Document operation

**Files:**

- Modify: `docs/nemotron/physical-test.md`
- Modify: `README.md`

- [ ] Document the exact command, the optional service-start switch, and excluded secret files.
- [ ] Run deployment and gateway tests, then commit documentation.
