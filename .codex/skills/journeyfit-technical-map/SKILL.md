---
name: journeyfit-technical-map
description: Locate JourneyFit storage, profiles, and runtime files.
---

# JourneyFit Technical Map

Use this skill when the task is about finding where JourneyFit or Hermes data
lives, inspecting persisted chat/session state, debugging saved workout plans,
or orienting yourself in the `journeyfit-agent` repo.

This is a navigation skill. It does not replace the narrower JourneyFit skills
for orchestration, business rules, status envelopes, or Hermes operations.

## When to Use

- The user asks where chat sessions, messages, plans, logs, profiles, tools, or
  config are stored.
- The task mentions `state.db`, `journeyfit.db`, workout plans, session history,
  saved plans, `/resume`, `/history`, gateway sessions, or profile-aware paths.
- Codex needs a quick map before changing storage, runtime, profile, plugin, or
  app-contract behavior.

## Core Locations

| What | Location |
|---|---|
| Chat/session SQLite DB | `get_hermes_home() / "state.db"` |
| Session DB implementation | `hermes_state.py` |
| JourneyFit plans SQLite DB | `get_hermes_home() / "journeyfit.db"` |
| JourneyFit plan storage code | `plugins/journeyfit_orchestrator/storage.py` |
| Active Hermes home resolver | `hermes_constants.py` |
| JourneyFit orchestrator plugin | `plugins/journeyfit_orchestrator/` |
| Orchestrator profile | `.hermes/profiles/orchestrator/` |
| Profile config | `.hermes/profiles/orchestrator/config.yaml` |
| Profile secrets | `.hermes/profiles/orchestrator/.env` |
| Profile prompt/persona | `.hermes/profiles/orchestrator/SOUL.md` |
| Profile logs | `.hermes/profiles/orchestrator/logs/` |
| Local Codex skills | `.codex/skills/` |
| JourneyFit plugin tests | `tests/plugins/journeyfit_orchestrator/` |
| App contract repo | `../journeyfit-app` |

Always resolve runtime state through `get_hermes_home()` instead of assuming a
fixed `~/.hermes` path. This repo supports profile-aware state, and the active
profile can move the real DBs under `.hermes/profiles/<profile>/`.

## Chat Sessions

Chat sessions live in `state.db`, created by `hermes_state.py`.

Important tables and concepts:

- `sessions`: session metadata, source/platform, model config, parent session,
  handoff fields, user/chat/thread identifiers.
- `messages`: ordered message history for each session, including roles,
  content, tool calls, tool names, timestamps, and contextual metadata.
- `messages_fts`: FTS5 search index for message content and tool-call text.
- `state_meta`: state DB metadata such as maintenance timestamps.

Common code paths:

- `SessionDB` in `hermes_state.py` owns session persistence.
- CLI and gateway session commands such as `/resume`, `/history`, `/title`, and
  `/branch` depend on this DB.
- `tools/session_search_tool.py` searches historical sessions.
- Gateway session behavior lives around `gateway/session.py`,
  `gateway/session_context.py`, and `gateway/run.py`.

If a session-related feature fails, inspect `hermes_state.py` first, then the
caller in CLI, TUI gateway, or messaging gateway code.

## JourneyFit Plans

JourneyFit workout and nutrition plans live in `journeyfit.db`, created by
`plugins/journeyfit_orchestrator/storage.py`.

Primary table:

- `workout_plans`: saved plan records with `id`, `user_id`, `session_id`,
  `trace_id`, `source_message`, serialized `plan_json`, `status`, `mode`,
  `version`, `created_at`, and `updated_at`.

Primary functions:

- `save_workout_plan(...)`: saves a generated plan and injects
  `workout_plan_id` plus `plan_version` into the payload.
- `get_workout_plan(plan_id)`: loads one plan.
- `get_latest_workout_plan(user_id=..., session_id=...)`: finds the newest plan.
- `get_plan_status(...)`: reports whether a user/session has training or
  nutrition plans.
- `get_current_plan(domain=...)`: returns latest training, nutrition, or both.

Use `tests/plugins/journeyfit_orchestrator/test_storage.py` as the fastest
reference for expected storage behavior.

## Runtime Orientation

Hermes home resolution is centralized in `hermes_constants.py`:

- `HERMES_HOME` env var wins when set.
- A checkout-local `.hermes/active_profile` can select
  `.hermes/profiles/<profile>`.
- Otherwise Hermes falls back to `~/.hermes`.
- Use `display_hermes_home()` in user-facing messages and schemas.
- Use `get_hermes_home()` for real filesystem paths.

For JourneyFit API/gateway work, the usual local profile is:

```bash
./.venv/bin/python ./hermes -p orchestrator gateway
```

The profile-local DBs are usually:

```text
.hermes/profiles/orchestrator/state.db
.hermes/profiles/orchestrator/journeyfit.db
```

but always verify the active profile or `HERMES_HOME` before reading or changing
runtime files.

## Codebase Bearings

Start here when the task is broad:

- `run_agent.py`: core synchronous agent loop and agent-level tool handling.
- `model_tools.py`: tool discovery, schemas, and function-call dispatch.
- `toolsets.py`: tool exposure; registered tools must still appear in a toolset.
- `tools/registry.py`: central tool registry used by tool modules.
- `cli.py` and `hermes_cli/`: classic CLI and slash command handling.
- `ui-tui/` and `tui_gateway/`: Ink TUI plus Python JSON-RPC gateway.
- `gateway/`: messaging/API gateway and platform adapters.
- `plugins/journeyfit_orchestrator/`: JourneyFit routing, specialists,
  policies, schemas, planner, executor, and storage.
- `.codex/skills/`: repo-local Codex orientation skills.

Use existing local skills for narrower behavior:

- `journeyfit-agent-codebase`: general repo coding rules.
- `journeyfit-orchestrator`: orchestrator flow and subagents.
- `journeyfit-business-rules`: routing and safety defaults.
- `journeyfit-status-envelope`: response envelope and app-ready payloads.
- `hermes-agent-ops`: profiles, logs, tools, plugins, and runtime setup.

## Inspection Commands

Prefer read-only inspection unless the user explicitly asks for data changes.

```bash
sqlite3 .hermes/profiles/orchestrator/state.db ".tables"
sqlite3 .hermes/profiles/orchestrator/state.db "SELECT id, source, started_at FROM sessions ORDER BY started_at DESC LIMIT 10;"
sqlite3 .hermes/profiles/orchestrator/state.db "SELECT role, substr(content,1,120) FROM messages WHERE session_id = '<session_id>' ORDER BY timestamp, id;"
sqlite3 .hermes/profiles/orchestrator/journeyfit.db ".schema workout_plans"
sqlite3 .hermes/profiles/orchestrator/journeyfit.db "SELECT id, user_id, session_id, status, mode, updated_at FROM workout_plans ORDER BY updated_at DESC LIMIT 10;"
```

If `sqlite3` is unavailable, use Python's `sqlite3` module from the active
virtualenv for read-only queries.

## Pitfalls

- Do not confuse `state.db` with `journeyfit.db`: chats and tool transcripts are
  in `state.db`; saved JourneyFit plans are in `journeyfit.db`.
- Do not hardcode `~/.hermes` in code. Use `get_hermes_home()`.
- Do not edit runtime DBs as a migration shortcut. Add code-level migrations or
  tests when schema behavior changes.
- WAL mode may fail on some network filesystems; `hermes_state.py` has fallback
  handling for `state.db` and shared logic for related DBs.
- Runtime files, logs, and profile-local secrets should not be committed unless
  the user explicitly asks.
- App-facing JSON shape changes must be checked against `../journeyfit-app`.

## Verification

- For plan storage changes, run:

```bash
pytest tests/plugins/journeyfit_orchestrator/test_storage.py -q
```

- For orchestration behavior, run the focused plugin tests under:

```bash
pytest tests/plugins/journeyfit_orchestrator/ -q
```

- For session DB behavior, start with:

```bash
pytest tests/test_hermes_state.py tests/hermes_state/ -q
```

- For gateway/API behavior, inspect profile logs and smoke-test the API only
  after confirming the gateway is running under the intended profile.
