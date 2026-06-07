from __future__ import annotations

from types import SimpleNamespace

from hermes_cli.plugins import PluginContext, PluginManifest, PluginManager
from plugins.journeyfit_orchestrator import register
from plugins.journeyfit_orchestrator.storage import save_workout_plan
from plugins.journeyfit_orchestrator.tools import (
    run_journeyfit_current_plan,
    run_journeyfit_orchestration,
    run_journeyfit_plan_status,
    run_journeyfit_slash_command,
)


class _FakeLLM:
    def __init__(self):
        self.calls = []

    def complete_structured(self, *, instructions, input, json_schema=None, schema_name=None, **kwargs):
        self.calls.append({"schema_name": schema_name, "instructions": instructions})
        if schema_name == "journeyfit.nutrition":
            parsed = {
                "summary": "Plano alimentar simples.",
                "assumptions": [],
                "nutrition_strategy": {"goal": "support"},
                "meal_structure": [],
                "constraints_respected": [],
                "warnings": [],
                "questions": [],
            }
        elif schema_name == "journeyfit.synthesizer":
            parsed = {
                "answer": "Resposta final.",
                "sections": [],
                "safety_notes": [],
                "follow_up_questions": [],
                "trace_summary": {},
            }
        elif schema_name == "journeyfit.medical":
            parsed = {
                "mode": "intake",
                "risk_level": "low",
                "red_flags": [],
                "requires_professional_review": False,
                "allowed_scope": "general_wellness",
                "constraints_for_other_agents": [],
                "validation_target": None,
                "validation_status": "approved",
                "revision_requests": [],
                "user_questions_needed": [],
                "summary": "Sem red flags.",
                "missing_information": [],
            }
        else:
            parsed = {
                "summary": "Plano de treino simples.",
                "assumptions": [],
                "weekly_training_plan": [],
                "progression": {},
                "constraints_respected": [],
                "warnings": [],
                "questions": [],
            }
        return SimpleNamespace(parsed=parsed, text="{}")


class _FakeCtx:
    def __init__(self):
        self.llm = _FakeLLM()
        self.tools = []
        self.commands = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands.append({"name": name, "handler": handler, "description": description, "args_hint": args_hint})


def test_registers_tool_and_command():
    ctx = _FakeCtx()
    register(ctx)
    assert any(tool["name"] == "journeyfit_orchestrate" for tool in ctx.tools)
    assert any(tool["name"] == "journeyfit_plan_status" for tool in ctx.tools)
    assert any(tool["name"] == "journeyfit_current_plan" for tool in ctx.tools)
    tool = next(tool for tool in ctx.tools if tool["name"] == "journeyfit_orchestrate")
    assert tool["toolset"] == "journeyfit"
    status_tool = next(tool for tool in ctx.tools if tool["name"] == "journeyfit_plan_status")
    assert status_tool["toolset"] == "journeyfit"
    current_plan_tool = next(tool for tool in ctx.tools if tool["name"] == "journeyfit_current_plan")
    assert current_plan_tool["toolset"] == "__journeyfit_leaf__"
    assert any(cmd["name"] == "journeyfit" for cmd in ctx.commands)


def test_plan_status_tool_returns_json():
    payload = __import__("json").loads(
        run_journeyfit_plan_status(
            {
                "user_profile": {"user_id": "user-no-plan"},
            }
        )
    )

    assert payload["success"] is True
    assert payload["has_any_plan"] is False
    assert payload["lookup"]["user_id"] == "user-no-plan"


def test_current_plan_tool_returns_domain_slice():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "sessions": [{"id": "day-1", "exercises": [{"name": "Supino"}]}],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino salvo",
        user_id="user-current-tool",
    )

    payload = __import__("json").loads(
        run_journeyfit_current_plan(
            {
                "domain": "training",
                "user_profile": {"user_id": "user-current-tool"},
            }
        )
    )

    assert payload["success"] is True
    assert payload["found"] is True
    assert payload["domain"] == "training"
    assert "training" in payload["plan"]
    assert "nutrition" not in payload["plan"]
    assert payload["plan"]["training"]["sessions"][0]["exercises"][0]["name"] == "Supino"


def test_orchestration_tool_returns_json():
    ctx = _FakeCtx()
    result = run_journeyfit_orchestration(
        ctx,
        {"user_message": "Quero ideias de jantar com proteina"},
    )
    payload = __import__("json").loads(result)
    assert payload["success"] is True
    assert payload["mode"] == "needs_more_info"
    assert payload["selected_agents"] == []
    assert payload["tasks"] == []
    assert payload["follow_up_questions"] == [
        "Qual a sua idade?",
        "Qual a sua altura?",
        "Qual o seu peso atual?",
        "Como e sua rotina de refeicoes ao longo do dia?",
    ]


def test_slash_command_uses_same_path():
    ctx = _FakeCtx()
    answer = run_journeyfit_slash_command(ctx, "Quero ideias de jantar com proteina")
    assert "Posso personalizar melhor o contexto" in answer
