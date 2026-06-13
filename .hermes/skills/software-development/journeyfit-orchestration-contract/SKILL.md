---
name: journeyfit-orchestration-contract
description: Use when shaping JourneyFit chat and JSON outputs.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [journeyfit, orchestration, schema, chat, frontend]
    category: software-development
    related_skills: [subagent-driven-development, writing-plans]
---

# JourneyFit Orchestration Contract

## Overview

JourneyFit should return a conversational answer and a structured envelope together.
The envelope is not the user-facing message itself; it is the transport for intent, missing data,
and optional renderable JSON.

## When to Use

- You are designing JourneyFit prompts, endpoint payloads, or frontend rendering rules.
- The user may be chatting naturally before a plan exists.
- The output may be `needs_more_info`, `conversation`, or `plan_ready`.
- You need to decide when the app should render JSON and when it should only show chat.

## Contract

Use a structured envelope like this:

```json
{
  "mode": "conversation",
  "assistant_message": "texto normal para o chat",
  "missing_information": [],
  "renderable_plan": null,
  "debug": {
    "agent": "journeyfit_orchestrator"
  }
}
```

Rules:

- `assistant_message` is always the human-facing response.
- `mode` tells the frontend what kind of turn this is.
- `missing_information` is for follow-up questions and intake gaps.
- `follow_up_questions` can be surfaced when the orchestrator wants optional clarification without blocking the flow.
- `renderable_plan` stays `null` until the orchestrator has enough context.
- `debug` is for tracing and should not drive the user experience.
- The orchestrator should not invent specialist advice in this envelope.

## Procedure

1. Treat greetings, short replies, and vague prompts as conversational turns.
2. If context is missing, ask for it in `assistant_message` and keep `renderable_plan: null`.
3. Only mark `mode: plan_ready` when the orchestrator has enough information to build the user plan.
4. Keep the frontend dumb: it should render the chat immediately and only render the plan when the envelope says to.
5. Do not force JSON output for every turn just because the endpoint is API-shaped.

## Pitfalls

- Do not make the frontend infer when a plan exists from raw text alone.
- Do not overwrite the chat transcript with structured JSON.
- Do not make greetings like `oi` produce a full renderable plan.
- Do not mix transport format decisions with orchestration decisions.

## Verification

- `oi` produces a normal conversational reply, not a plan.
- Missing intake produces a helpful follow-up message.
- A fully specified request produces `mode: plan_ready` with a populated `renderable_plan`.
- The frontend can show the conversation even when no plan is available yet.
- The JSON contract stays stable enough to render later without reworking the UI.
