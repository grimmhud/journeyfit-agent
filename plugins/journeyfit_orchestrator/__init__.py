"""JourneyFit orchestration plugin."""

from __future__ import annotations

from plugins.journeyfit_orchestrator.schemas import (
    JOURNEYFIT_CURRENT_PLAN_SCHEMA,
    JOURNEYFIT_ORCHESTRATE_SCHEMA,
    JOURNEYFIT_PLAN_STATUS_SCHEMA,
)
from plugins.journeyfit_orchestrator.tools import (
    passthrough_journeyfit_tool_result,
    remember_journeyfit_tool_result,
    run_journeyfit_current_plan,
    run_journeyfit_plan_status,
    run_journeyfit_orchestration,
    run_journeyfit_slash_command,
)


def register(ctx) -> None:
    """Register the JourneyFit tool and slash command."""
    ctx.register_tool(
        name="journeyfit_orchestrate",
        toolset="journeyfit",
        schema=JOURNEYFIT_ORCHESTRATE_SCHEMA,
        handler=lambda args, **kw: run_journeyfit_orchestration(ctx, args, **kw),
    )
    ctx.register_tool(
        name="journeyfit_plan_status",
        toolset="journeyfit",
        schema=JOURNEYFIT_PLAN_STATUS_SCHEMA,
        handler=lambda args, **kw: run_journeyfit_plan_status(args, **kw),
    )
    ctx.register_tool(
        name="journeyfit_current_plan",
        toolset="__journeyfit_leaf__",
        schema=JOURNEYFIT_CURRENT_PLAN_SCHEMA,
        handler=lambda args, **kw: run_journeyfit_current_plan(args, **kw),
    )
    ctx.register_command(
        "journeyfit",
        handler=lambda raw: run_journeyfit_slash_command(ctx, raw),
        description="Run the JourneyFit orchestration flow.",
        args_hint="<request>",
    )
    if hasattr(ctx, "register_hook"):
        ctx.register_hook("post_tool_call", remember_journeyfit_tool_result)
        ctx.register_hook("transform_llm_output", passthrough_journeyfit_tool_result)
