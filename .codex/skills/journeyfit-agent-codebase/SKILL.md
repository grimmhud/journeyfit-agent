---
name: journeyfit-agent-codebase
description: Use when coding the JourneyFit Hermes agent.
---

# JourneyFit Agent Codebase

## Overview

Use this skill when changing the `journeyfit-agent` repo for JourneyFit work.
This repo is Hermes plus JourneyFit-specific profiles, plugins, skills, and
tests.

Prefer existing local skills for narrow work:

- `hermes-agent-ops` for profiles, logs, tools, plugins, and runtime setup.
- `journeyfit-orchestrator` for orchestration plugin behavior.
- `journeyfit-business-rules` for routing and safety defaults.
- `journeyfit-status-envelope` for response shape and plan readiness.

The sibling Flutter app has its own Codex skills under
`../journeyfit-app/.codex/skills/`. Use those when editing app code.

## Project Map

| Area | Files |
|---|---|
| Agent loop | `run_agent.py` |
| Tool dispatch | `model_tools.py`, `toolsets.py`, `tools/registry.py` |
| CLI | `cli.py`, `hermes_cli/` |
| Gateway/API | `gateway/run.py`, `gateway/platforms/api_server.py` |
| Profile-aware paths | `hermes_constants.py`, `hermes_logging.py` |
| JourneyFit plugin | `plugins/journeyfit_orchestrator/` |
| Orchestrator profile | `.hermes/profiles/orchestrator/` |
| Local Codex skills | `.codex/skills/` |
| Tests | `tests/`, especially `tests/plugins/journeyfit_orchestrator/` |

## JourneyFit Rules

- The first action for JourneyFit health, fitness, nutrition, pain, or check-in
  requests should route through `journeyfit_orchestrate`.
- Do not ask intake questions before the orchestrator tool has analyzed the raw
  user message.
- For normal users, return the tool's `user_facing_message` as the human reply.
- For app/backend/developer JSON requests, return raw JSON only.
- Keep safety conservative around pain, injury, medical conditions, medication,
  and missing profile data.
- Keep simple training requests on the small path: doctor only for medical risk,
  nutritionist for diet, personal trainer for training.

## Output Contract

JourneyFit agent responses may use a status envelope:

- `mode` or `status`: `conversation`, `needs_more_info`, `plan_ready`, or
  `urgent_stop`.
- `user_facing_message`: the text shown in chat.
- `follow_up_questions`: questions when the profile is insufficient.
- `training` and `nutrition`: structured specialist outputs.
- `renderable_plan`: full plan payload when available.

When changing this shape, update the plugin tests and the app parser together.
The Flutter app can adapt a `training` envelope, but the backend should still
prefer stable, explicit JSON.

Cross-repo app contract files live in `../journeyfit-app`:

- `lib/data/datasources/chat_remote_datasource.dart`
- `lib/data/datasources/plan_remote_datasource.dart`
- `test/unit/chat_remote_datasource_test.dart`
- `test/unit/plan_remote_datasource_test.dart`

## Profile And Runtime

Use the orchestrator profile for local JourneyFit API work:

```bash
./.venv/bin/python ./hermes -p orchestrator gateway
```

Important profile files:

```text
.hermes/profiles/orchestrator/SOUL.md
.hermes/profiles/orchestrator/config.yaml
.hermes/profiles/orchestrator/.env
.hermes/profiles/orchestrator/logs/
```

For web app access, the API server must allow the web origin through CORS.
Keep CORS configuration in profile env/config where possible instead of
hardcoding app ports into Hermes core.

## Commands

Activate the virtualenv first:

```bash
source .venv/bin/activate
```

Focused JourneyFit tests:

```bash
pytest tests/plugins/journeyfit_orchestrator/test_questions.py -q
```

Broader repo tests:

```bash
scripts/run_tests.sh
```

API smoke test:

```bash
curl -sS http://127.0.0.1:8642/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes-agent","stream":false,"messages":[{"role":"user","content":"Tenho 30 anos, peso 80 quilos e quero treino 3x por semana."}]}'
```

## Editing Rules

- Prefer plugin/profile changes over Hermes core changes.
- If changing a tool schema or handler, verify both registration and exposure in
  toolsets.
- Do not add project-specific hardcoding to generic Hermes core unless the user
  explicitly wants core behavior.
- Use `get_hermes_home()` and `display_hermes_home()` for profile-aware paths.
- Keep dependencies pinned with upper bounds in `pyproject.toml`.
- Do not commit runtime artifacts such as `test-results/`, profile logs, or
  downloaded skill bundles unless explicitly requested.

## Pitfalls

- Changing prompts without updating tests can hide broken routing.
- Returning conversational text around JSON breaks app parsing.
- Assuming `kg` only misses Portuguese inputs like `quilos`.
- Editing `.hermes/profiles/orchestrator/.env` may be local-only if ignored.
- A gateway restart can fail if another gateway is already active.

## Verification

- Focused plugin tests pass for changed JourneyFit behavior.
- Logs show the expected `journeyfit_orchestrate` path.
- Direct API calls return HTTP `200` and valid JSON shape.
- If the change affects the app, verify the sibling Flutter app in
  `../journeyfit-app` as well.
