---
name: journeyfit-status-envelope
description: Use when handling JourneyFit turn status and envelopes.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [journeyfit, status, envelope, schema, chat]
    related_skills: [journeyfit-orchestrator, journeyfit-business-rules]
---

# JourneyFit Status Envelope

## Overview

JourneyFit uses a conversational message plus a structured envelope. The
envelope tells us whether a turn is conversation, needs more info, or is ready
to render a plan.

The agent owns this envelope. The sibling Flutter app in `../journeyfit-app`
consumes it through its own app-local skills and datasource tests.

## When to Use

- You are changing JourneyFit response shape, status, or prompt rules.
- You need to decide when `renderable_plan` should exist.
- You are editing the orchestrator or the Flutter app interpretation of its output.

## Rules

- `assistant_message` or `user_facing_message` is the human reply.
- `mode` or `status` marks the turn type.
- `missing_information` is for follow-up questions.
- `renderable_plan` stays `null` until the request is ready.
- `training` and `nutrition` may exist before a full app-ready plan exists.
- Greetings and vague prompts should stay conversational.

## App Boundary

When changing envelope fields, update and verify the app parser in
`../journeyfit-app` during the same workstream. The key app files are:

- `lib/data/datasources/chat_remote_datasource.dart`
- `lib/data/datasources/plan_remote_datasource.dart`
- `test/unit/chat_remote_datasource_test.dart`
- `test/unit/plan_remote_datasource_test.dart`

## Pitfalls

- Do not force a plan for greetings like `oi`.
- Do not overwrite the chat transcript with raw JSON.
- Do not make the app infer plan readiness from text alone.

## Verification

- A greeting returns a normal message.
- Sparse input returns missing fields or questions.
- A complete request returns a populated renderable plan.
