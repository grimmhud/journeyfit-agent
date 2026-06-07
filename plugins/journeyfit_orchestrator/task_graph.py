"""Task model for JourneyFit orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TaskStatus = Literal["pending", "running", "done", "failed", "skipped"]
TaskType = Literal["intake", "domain_plan", "existing_plan_conversation", "validation", "revision", "schedule", "review", "synthesis"]


@dataclass
class AgentTask:
    id: str
    agent: str
    task_type: TaskType
    objective: str
    dependencies: list[str] = field(default_factory=list)
    input_context: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    validation_target: str | None = None
    revision_of: str | None = None
    status: TaskStatus = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 0
