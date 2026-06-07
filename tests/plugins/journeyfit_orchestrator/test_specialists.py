from __future__ import annotations

import json
from types import SimpleNamespace

from plugins.journeyfit_orchestrator.context import OrchestrationContext
from plugins.journeyfit_orchestrator.planner import IntakeAnalyzer, TaskPlanner
from plugins.journeyfit_orchestrator.specialists import SpecialistRunner
from plugins.journeyfit_orchestrator.task_graph import AgentTask


class _FakeLLM:
    def __init__(self):
        self.calls = []

    def complete_structured(self, *, instructions, input, json_schema=None, schema_name=None, **kwargs):
        self.calls.append((schema_name, instructions))
        if schema_name == "journeyfit.nutrition":
            parsed = {
                "summary": "Nutrição pronta.",
                "assumptions": [],
                "nutrition_strategy": {},
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
        else:
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
                "summary": "Sem risco.",
                "missing_information": [],
            }
        return SimpleNamespace(parsed=parsed, text="{}")


def test_runner_uses_delegate_task_when_parent_agent_exists():
    calls = []

    def _fake_delegate_task(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "results": [
                    {
                        "status": "completed",
                        "exit_reason": "completed",
                        "summary": json.dumps(
                            {
                                "summary": "Plano alimentar por subagente.",
                                "assumptions": [],
                                "nutrition_strategy": {"goal": "support"},
                                "meal_structure": [],
                                "constraints_respected": [],
                                "warnings": [],
                                "questions": [],
                            }
                        ),
                        "tool_trace": [{"tool": "read_file"}],
                    }
                ],
                "total_duration_seconds": 1.23,
            }
        )

    parent_agent = SimpleNamespace(session_id="parent-1")
    ctx = SimpleNamespace(llm=_FakeLLM())
    context = OrchestrationContext(user_message="Quero jantar com proteina", user_profile={})
    context.intake = IntakeAnalyzer().assess(context).__dict__
    task = next(task for task in TaskPlanner().plan(context) if task.id == "nutrition_plan")
    result = SpecialistRunner(ctx, parent_agent=parent_agent, delegate_fn=_fake_delegate_task).run(task, context)
    assert result["summary"] == "Plano alimentar por subagente."
    assert result["agent"] == "nutritionist"
    assert calls[0]["parent_agent"] is parent_agent
    assert calls[0]["role"] == "leaf"
    assert calls[0]["toolsets"] == ["__journeyfit_leaf__"]


def test_runner_falls_back_to_structured_llm_without_parent_agent():
    ctx = SimpleNamespace(llm=_FakeLLM())
    context = OrchestrationContext(user_message="Quero jantar com proteina", user_profile={})
    context.intake = IntakeAnalyzer().assess(context).__dict__
    task = next(task for task in TaskPlanner().plan(context) if task.id == "nutrition_plan")
    result = SpecialistRunner(ctx).run(task, context)
    assert result["summary"] == "Nutrição pronta."
def test_existing_training_conversation_delegate_uses_leaf_toolset_without_plan_injection():
    calls = []

    def _fake_delegate_task(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "results": [
                    {
                        "status": "completed",
                        "exit_reason": "completed",
                        "summary": json.dumps(
                            {
                                "answer": "Vi o treino salvo pela tool e ajustaria o treino de perna.",
                                "referenced_plan": {"source": "journeyfit_current_plan"},
                                "safety_notes": [],
                                "follow_up_questions": [],
                                "warnings": [],
                            }
                        ),
                        "tool_trace": [{"tool": "journeyfit_current_plan"}],
                    }
                ]
            }
        )

    parent_agent = SimpleNamespace(session_id="parent-1")
    ctx = SimpleNamespace(llm=_FakeLLM())
    context = OrchestrationContext(
        user_message="estou tendo dificuldade no treino de perna",
        user_profile={},
    )
    context.intake = {"requires_training": False}
    context.shared["session_id"] = "api-chat-ola"
    context.shared["plan_status"] = {"has_training_plan": True}
    task = AgentTask(
        id="existing_training_conversation",
        agent="personal_trainer",
        task_type="existing_plan_conversation",
        objective="Responder sobre o treino salvo.",
        expected_output="Resposta sobre treino salvo.",
    )

    result = SpecialistRunner(ctx, parent_agent=parent_agent, delegate_fn=_fake_delegate_task).run(task, context)

    assert result["answer"].startswith("Vi o treino salvo")
    assert calls[0]["toolsets"] == ["__journeyfit_leaf__"]
    assert "journeyfit_current_plan" in calls[0]["goal"]
    assert '"session_id": "api-chat-ola"' in calls[0]["context"]
    assert "current_plan" not in calls[0]["context"]
