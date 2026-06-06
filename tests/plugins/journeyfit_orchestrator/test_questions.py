from __future__ import annotations

import json
from types import SimpleNamespace

from plugins.journeyfit_orchestrator.tools import (
    passthrough_journeyfit_tool_result,
    remember_journeyfit_tool_result,
    run_journeyfit_orchestration,
    run_journeyfit_slash_command,
)


class _FakeLLM:
    def complete_structured(self, *, schema_name=None, **kwargs):
        if schema_name == "journeyfit.nutrition":
            return SimpleNamespace(
                parsed={
                    "summary": "Plano alimentar pronto.",
                    "assumptions": [],
                    "nutrition_strategy": {},
                    "meal_structure": [],
                    "constraints_respected": [],
                    "warnings": [],
                    "questions": [],
                },
                text="{}",
            )
        if schema_name == "journeyfit.training":
            return SimpleNamespace(
                parsed={
                    "summary": "Plano de treino pronto.",
                    "assumptions": [],
                    "weekly_training_plan": [],
                    "progression": {},
                    "constraints_respected": [],
                    "warnings": [],
                    "questions": [],
                },
                text="{}",
            )
        if schema_name == "journeyfit.synthesizer":
            return SimpleNamespace(
                parsed={
                    "answer": "Resposta final.",
                    "sections": [],
                    "safety_notes": [],
                    "follow_up_questions": [],
                    "trace_summary": {},
                },
                text="{}",
            )
        return SimpleNamespace(
            parsed={
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
            },
            text="{}",
        )


class _FakeLLMEmptySynthesis(_FakeLLM):
    def complete_structured(self, *, schema_name=None, **kwargs):
        if schema_name == "journeyfit.synthesizer":
            return SimpleNamespace(
                parsed={
                    "answer": "",
                    "sections": [],
                    "safety_notes": [],
                    "follow_up_questions": [],
                    "trace_summary": {},
                },
                text="{}",
            )
        return super().complete_structured(schema_name=schema_name, **kwargs)


class _FakeLLMRenderable(_FakeLLM):
    def complete_structured(self, *, schema_name=None, **kwargs):
        if schema_name == "journeyfit.nutrition":
            return SimpleNamespace(
                parsed={
                    "target_calories": {"amount": 2400, "unit": "kcal"},
                    "macronutrient_distribution": {
                        "protein_g": 160,
                        "carb_g": 280,
                        "fat_g": 70,
                    },
                    "daily_meals": [
                        {
                            "meal_name": "Café da Manhã",
                            "food_items": [
                                {"item_name": "ovos", "quantity": 3, "unit": "unidades"},
                                {"item_name": "aveia", "quantity": 40, "unit": "g"},
                            ],
                        },
                        {
                            "meal_name": "Almoço",
                            "food_items": [
                                {"item_name": "frango", "quantity": 150, "unit": "g"},
                                {"item_name": "arroz", "quantity": 100, "unit": "g"},
                            ],
                        },
                        {
                            "meal_name": "Pré-treino",
                            "food_items": [{"item_name": "banana", "quantity": 1, "unit": "unidade"}],
                        },
                    ],
                    "hydration_recommendations": {
                        "daily_water_intake": {"amount": 3.0, "unit": "litros"},
                    },
                    "assumptions": [],
                    "nutrition_strategy": {},
                    "meal_structure": [],
                    "constraints_respected": [],
                    "warnings": [],
                    "questions": [],
                    "summary": "Plano alimentar pronto.",
                },
                text="{}",
            )
        if schema_name == "journeyfit.training":
            return SimpleNamespace(
                parsed={
                    "training_split": "Upper/lower",
                    "target_frequency_days_per_week": 4,
                    "workout_days": [
                        {
                            "day_name": "Dia 1: Upper",
                            "focus": "Força de superiores",
                            "exercises": [
                                {
                                    "exercise_name": "Supino reto",
                                    "sets": 4,
                                    "reps": "6-8",
                                    "rest_seconds": 90,
                                    "notes": "Controle a descida.",
                                }
                            ],
                        }
                    ],
                    "summary": "Plano de treino pronto.",
                    "assumptions": [],
                    "weekly_training_plan": [],
                    "progression": {},
                    "constraints_respected": [],
                    "warnings": [],
                    "questions": [],
                },
                text="{}",
            )
        return super().complete_structured(schema_name=schema_name, **kwargs)


class _FakeLLMSplitList(_FakeLLMRenderable):
    def complete_structured(self, *, schema_name=None, **kwargs):
        if schema_name == "journeyfit.training":
            return SimpleNamespace(
                parsed={
                    "split": [
                        {
                            "day_name": "A - Superior",
                            "day_description": "Treino de superiores",
                            "workouts": [
                                {
                                    "exercise_name": "Supino reto",
                                    "sets": 4,
                                    "reps": "6-8",
                                    "rest_seconds": 90,
                                }
                            ],
                        }
                    ],
                    "target_frequency_days_per_week": 4,
                    "summary": "Plano de treino pronto.",
                    "assumptions": [],
                    "weekly_training_plan": [],
                    "progression": {},
                    "constraints_respected": [],
                    "warnings": [],
                    "questions": [],
                },
                text="{}",
            )
        return super().complete_structured(schema_name=schema_name, **kwargs)


def test_orchestration_collects_missing_context_only():
    ctx = SimpleNamespace()
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero mais musculos",
                "user_profile": {},
                "conversation_history": [],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "needs_more_info"
    assert result["selected_agents"] == []
    assert result["tasks"] == []
    assert result["task_results"] == {}
    assert result["answer"] == ""
    assert result["missing_information"] == [
        "Qual a sua idade?",
        "Qual o seu peso atual?",
        "Quantos dias por semana voce consegue treinar?",
    ]
    assert result["renderable_plan"] is None
    assert result["follow_up_questions"] == [
        "Qual a sua idade?",
        "Qual o seu peso atual?",
        "Quantos dias por semana voce consegue treinar?",
    ]


def test_orchestration_progresses_to_specialists_with_minimum_context():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero mais musculos",
                "user_profile": {
                    "age": 29,
                    "weight_kg": 82,
                    "training_days_per_week": 4,
                },
                "conversation_history": [],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert result["answer"] == "Resposta final."
    assert result["selected_agents"] == ["personal_trainer"]
    assert result["renderable_plan"]["mode"] == "plan_ready"
    assert result["renderable_plan"]["training"]["status"] == "provisional"
    assert result["renderable_plan"]["nutrition"]["status"] == "unavailable"


def test_orchestration_understands_weight_written_as_quilos():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "gostaria de um treino, tenho 28 anos, peso 78 quilos e consigo treinar 3 dias por semana",
                "user_profile": {},
                "conversation_history": [],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert result["follow_up_questions"] == []
    assert result["selected_agents"] == ["personal_trainer"]
    assert result["renderable_plan"]["training"]["weekly_frequency"] == 3


def test_orchestration_maps_specialist_outputs_to_renderable_v0():
    ctx = SimpleNamespace(llm=_FakeLLMRenderable())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero treino e dieta para recomposição",
                "user_profile": {
                    "age": 32,
                    "weight_kg": 78,
                    "training_days_per_week": 4,
                },
                "conversation_history": [],
            },
        )
    )

    plan = result["renderable_plan"]
    assert plan["mode"] == "plan_ready"
    assert plan["training"]["split"] == "Upper/lower"
    assert plan["training"]["weekly_frequency"] == 4
    assert plan["training"]["sessions"][0]["name"] == "Dia 1: Upper"
    assert plan["training"]["sessions"][0]["exercises"][0]["name"] == "Supino reto"
    assert plan["nutrition"]["kcal"] == {"min": 2250.0, "max": 2550.0}
    assert plan["nutrition"]["macros"]["protein_g_per_kg"] == {"min": 2.0, "max": 2.2}
    assert "3 unidades ovos" in plan["nutrition"]["meal_examples"]["breakfast"][0]
    assert result["task_results"]["training_plan"]["workout_days"]


def test_orchestration_normalizes_split_list_to_sessions():
    ctx = SimpleNamespace(llm=_FakeLLMSplitList())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero treino e dieta para recomposição",
                "user_profile": {
                    "age": 32,
                    "weight_kg": 78,
                    "training_days_per_week": 4,
                },
                "conversation_history": [],
            },
        )
    )

    plan = result["renderable_plan"]
    assert plan["training"]["split"] == "Upper/lower"
    assert plan["training"]["sessions"][0]["name"] == "A - Superior"
    assert plan["training"]["sessions"][0]["exercises"][0]["name"] == "Supino reto"


def test_orchestration_adds_medical_notice_and_knee_sensitive_starter():
    ctx = SimpleNamespace(llm=_FakeLLMEmptySynthesis())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "tenho dor no joelho ao agachar e quero treinar 3x por semana",
                "user_profile": {
                    "age": 40,
                    "weight_kg": 92,
                    "training_days_per_week": 3,
                },
                "conversation_history": [],
            },
        )
    )

    plan = result["renderable_plan"]
    assert plan["notices"][0]["agent"] == "doctor"
    exercise_names = [
        exercise["name"].lower()
        for session in plan["training"]["sessions"]
        for exercise in session["exercises"]
    ]
    assert "ponte de gluteos" in exercise_names
    assert not any("agachamento" in name for name in exercise_names)


def test_orchestration_fallback_message_is_user_facing():
    ctx = SimpleNamespace(llm=_FakeLLMEmptySynthesis())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero treino upper lower 4x",
                "user_profile": {
                    "age": 28,
                    "weight_kg": 78,
                    "training_days_per_week": 4,
                },
                "conversation_history": [],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert "intake" not in result["assistant_message"].lower()
    assert result["assistant_message"] == "Montei uma primeira versao do plano de treino com os dados disponiveis."


def test_journeyfit_tool_result_passthrough_for_final_response():
    result = json.dumps({"success": True, "mode": "plan_ready", "renderable_plan": {"status": "plan_ready"}})

    remember_journeyfit_tool_result(
        tool_name="journeyfit_orchestrate",
        result=result,
        session_id="session-1",
    )

    assert passthrough_journeyfit_tool_result(session_id="session-1") == '{"status": "plan_ready"}'
    assert passthrough_journeyfit_tool_result(session_id="session-1") is None


def test_journeyfit_passthrough_wraps_plain_conversation_as_json():
    result = json.loads(
        passthrough_journeyfit_tool_result(
            session_id="missing",
            response_text="Oi! Como posso ajudar?",
        )
    )

    assert result == {
        "status": "conversation",
        "mode": "conversation",
        "user_facing_message": "Oi! Como posso ajudar?",
        "follow_up_questions": [],
        "renderable_plan": None,
    }


def test_slash_command_returns_intake_message():
    ctx = SimpleNamespace()
    answer = run_journeyfit_slash_command(ctx, "oi")
    assert answer == "Oi! Como posso te ajudar hoje?"
