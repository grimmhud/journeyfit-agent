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

## Contract — Schema v0 (FIXED)

When `mode` is `plan_ready` or `needs_more_info`, the response **must** match this exact schema. No extra fields.

```json
{
  "status": "plan_ready | needs_more_info | conversation | urgent_stop",
  "mode": "plan_ready | needs_more_info | conversation",
  "user_facing_message": "short, friendly message in pt-BR",

  "notices": [
    {
      "agent": "doctor | nutritionist | personal_trainer",
      "type": "warning | info | restriction",
      "severity": "high | moderate | low",
      "message": "single readable sentence for the user"
    }
  ],

  "follow_up_questions": [
    { "id": "q1", "question": "...", "priority": "high | medium" }
  ],

  "training": {
    "status": "ready | provisional | unavailable",
    "split": "Upper/Lower 4x",
    "weekly_frequency": 4,
    "session_duration_minutes": { "min": 60, "max": 85 },
    "sessions": [
      {
        "id": "day_1_upper_a",
        "name": "Superiores A",
        "focus": "Empurrar + Puxar horizontal",
        "estimated_duration_minutes": 70,
        "exercises": [
          {
            "name": "exercise name",
            "sets": 4,
            "reps": "5-8",
            "rest_seconds": 120,
            "rir": "1-3",
            "note": "short execution note or null"
          }
        ]
      }
    ]
  },

  "nutrition": {
    "status": "ready | provisional | unavailable",
    "kcal": { "min": 2300, "max": 2700 },
    "macros": {
      "protein_g_per_kg": { "min": 1.6, "max": 2.2 },
      "carbs_g_per_kg": { "min": 3.0, "max": 5.0 },
      "fat_g_per_kg": { "min": 0.6, "max": 1.0 }
    },
    "meals_per_day": { "min": 3, "max": 5 },
    "hydration_ml_per_kg": { "min": 30, "max": 40 },
    "timing": {
      "pre_workout_window": "60-150 min before",
      "post_workout_window": "up to 2h after"
    },
    "meal_examples": {
      "breakfast": [],
      "lunch_dinner": [],
      "snacks": [],
      "pre_workout": [],
      "post_workout": []
    }
  }
}
```

Rules:

- `user_facing_message` is always the human-facing message, in pt-BR.
- `mode` tells the frontend what kind of turn this is.
- `notices` replaces all `guardrails`, `restrictions`, `stop_conditions`, and `safety` fields from sub-agents.
- `follow_up_questions` is deduplicated across all agents — max 8 total.
- `training` and `nutrition` come directly from `personal_trainer.v0_output` and `nutritionist.v0_output`.
- All arrays must be present even when empty. Never omit a field.
- `reps` is always a string like `"5-8"`, never `"5_a_8"`.
- `rir` is always a string like `"1-3"` or `null` — never an integer.
- `note` is always a string or `null` — never an empty string.
- No `trace`, `task_results`, `delegate_*`, `assumptions`, `restrictions`, `guardrails`, or internal routing fields.

## Orchestration Workflow

1.  **Mandatory First Action**: For any user request related to health, fitness, diet, pain, or a check-in, the **first and only** initial action must be to call the `journeyfit_orchestrate` tool. Pass the user's raw, unmodified message to the `user_message` parameter.

2.  **No Pre-Tool Intake**: **Do not** ask clarifying questions (e.g., about age, weight, goals) before making the first call to `journeyfit_orchestrate`. The tool is responsible for intake analysis. If more information is needed, the tool will return a `mode: "needs_more_info"` response with the appropriate `follow_up_questions`. Your job is to present those questions to the user.

3.  **Handling Follow-ups and Check-ins**: When the user answers follow-up questions or provides a "check-in" with feedback, treat this new message as a complete request. Call `journeyfit_orchestrate` again with the user's latest message. The tool will handle the logic of merging the new information and adjusting the plan.

## Output Formatting

- **Standard Response**: For a normal conversational user, use the `user_facing_message` from the tool's output as your primary response.

- **Developer Response (JSON)**: When the user identifies as a "frontend", "backend", or explicitly asks for "the JSON back", your response **must be only the raw JSON payload**.
    - If the tool returns a complete plan, your entire response should be the JSON object from the `renderable_plan` field.
    - If the tool returns a response without a `renderable_plan` (e.g., `needs_more_info`), return the entire tool output as a JSON object.
    - **Do not** add any conversational text, explanations, markdown, or code fences (` ```json `) around the JSON output in these cases. The JSON is the entire response.


## Pitfalls

- Do not include any field not present in the schema above.
- Do not return the sub-agent internal schemas (`task_results`, `agent_outputs`, etc.) in the final response.
- Do not make greetings like `oi` produce a full plan.
- Do not mix transport format decisions with orchestration decisions.

## Verification

- `oi` → `mode: conversation`, only `user_facing_message` populated, all other fields at defaults.
- Missing intake → `mode: needs_more_info`, provisional training/nutrition, follow_up_questions populated.
- Full request → `mode: plan_ready`, all v0 fields populated from sub-agent v0_outputs.
- The frontend renders without any field access errors.
