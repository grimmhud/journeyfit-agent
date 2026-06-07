---
name: journeyfit-business-rules
description: Use when changing JourneyFit routing or safety defaults.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [journeyfit, routing, safety, training, nutrition, medical]
    related_skills: [hermes-agent, hermes-agent-ops, journeyfit-orchestrator, codex]
---

# JourneyFit Business Rules

## Overview

Use this skill when you are changing the decision rules behind JourneyFit:
which specialist runs, when to ask for more information, and how conservative
the default plan should be.

The guiding principle is simple: keep the first answer safe, useful, and small.
Do not invent extra agents or complicated branches unless the user request
really needs them.

See [reference/routing-matrix.md](references/routing-matrix.md) for the
current routing defaults.

## When to Use

- A request should route to doctor, nutritionist, personal_trainer, or none
- You need to change the conservative defaults for sparse profiles
- A new rule should ask follow-up questions instead of overfitting the plan
- You are deciding whether reviewer/scheduler should stay out of the simple path
- A plan is too aggressive for injury, pain, medication, or missing profile data

## Quick Reference

| Scenario | Default action |
|---|---|
| Training request | `personal_trainer` |
| Nutrition request | `nutritionist` |
| Existing training plan | keep focus on the saved plan; do not create another |
| Existing nutrition plan | keep focus on the saved diet; do not create another |
| Pain, injury, condition, medication, red flags | `doctor` first |
| Training + nutrition | both specialists |
| Sparse profile | conservative starter plan + questions |
| Simple request | avoid adding extra agents |

## Procedure

1. Start from the user request, not from the desired end state.
2. Check the medical risk signals before adding training or nutrition details.
3. Keep the plan conservative when age, sex, equipment, experience, or
   limitations are missing.
4. Use the existing specialists first; add new roles only when there is a
   clear gap.
5. If a saved workout or diet exists, keep the conversation on that plan and
   route only missing domains or safety checks.
6. Update the tests for any routing change so the plan and the logs stay aligned.

## Common Pitfalls

1. Letting the model assume a fully healthy user without checking the request.
2. Reintroducing reviewer/scheduler into the simple path without a strong need.
3. Returning a polished answer while the profile is still missing critical data.
4. Changing routing in one place but not in the task planner or prompts.
5. Letting the assistant create multiple workouts or diets for the same user
   instead of revising the existing saved plan.

## Verification

- Confirm the `selected_agents` list matches the scenario.
- Confirm existing workout/diet state suppresses duplicate plan creation.
- Check that medical risk routes to `doctor` before training details.
- Confirm follow-up questions are present when data is sparse.
- Run the JourneyFit planner and plugin tests after changing a rule.
