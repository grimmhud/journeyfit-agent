from __future__ import annotations

import json
from types import SimpleNamespace

from plugins.journeyfit_orchestrator.tools import (
    passthrough_journeyfit_tool_result,
    remember_journeyfit_tool_result,
    run_journeyfit_orchestration,
    run_journeyfit_slash_command,
)
from plugins.journeyfit_orchestrator.storage import get_workout_plan
from plugins.journeyfit_orchestrator.storage import save_workout_plan


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
        if schema_name == "journeyfit.training_conversation":
            return SimpleNamespace(
                parsed={
                    "user_facing_message": json.dumps(
                        {
                            "agent_message": "Vamos ajustar seu treino de perna salvo com mais descanso e tecnica.",
                        }
                    ),
                    "referenced_plan": {"lookup": "journeyfit_current_plan"},
                    "safety_notes": [],
                    "follow_up_questions": ["A dificuldade e dor, carga ou execucao?"],
                    "warnings": [],
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


class _FakeLLMPosteriorGeneric(_FakeLLM):
    def complete_structured(self, *, schema_name=None, **kwargs):
        if schema_name == "journeyfit.training_conversation":
            return SimpleNamespace(
                parsed={
                    "answer": "Voce se refere a qual desses exercicios do treino de perna?",
                    "referenced_plan": {"lookup": "journeyfit_current_plan"},
                    "safety_notes": [],
                    "follow_up_questions": [],
                    "warnings": [],
                },
                text="{}",
            )
        return super().complete_structured(schema_name=schema_name, **kwargs)


class _FakeLLMPosteriorRecommendation(_FakeLLM):
    def complete_structured(self, *, schema_name=None, **kwargs):
        if schema_name == "journeyfit.training_conversation":
            return SimpleNamespace(
                parsed={
                    "answer": (
                        "Para focar mais nos isquiotibiais, poderiamos incluir Stiff "
                        "ou Mesa Flexora. Gostaria de adicionar um desses?"
                    ),
                    "referenced_plan": {"lookup": "journeyfit_current_plan"},
                    "safety_notes": [],
                    "follow_up_questions": ["Adicionar Stiff?"],
                    "warnings": [],
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
        "Qual a sua altura?",
        "Qual o seu peso atual?",
        "Quantos dias por semana voce consegue treinar?",
    ]
    assert result["renderable_plan"] is None
    assert result["follow_up_questions"] == [
        "Qual a sua idade?",
        "Qual a sua altura?",
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


def test_orchestration_uses_parent_session_history_when_args_are_empty():
    ctx = SimpleNamespace(llm=_FakeLLM())
    parent_agent = SimpleNamespace(
        _session_messages=[
            {
                "role": "user",
                "content": "tenho 29 anos, peso 78kg, tenho 172cm e treino 5x por semana",
            }
        ]
    )
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero mais musculos",
                "user_profile": {},
            },
            parent_agent=parent_agent,
        )
    )

    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert result["selected_agents"] == ["personal_trainer"]
    assert result["follow_up_questions"] == []
    assert result["renderable_plan"]["training"]["weekly_frequency"] == 5


def test_orchestration_keeps_goal_from_history_on_short_follow_up():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "29 anos",
                "user_profile": {},
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "gostaria de um treino, tenho 29 anos, peso 78kg e consigo treinar 5x por semana",
                    }
                ],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert result["selected_agents"] == ["personal_trainer"]
    assert result["follow_up_questions"] == []
    assert result["renderable_plan"]["training"]["weekly_frequency"] == 5


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


def test_orchestration_builds_training_for_treinar_frequency_request():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "tenho 28 anos.  78kg e quero treinar 3x por semana",
                "user_profile": {},
                "conversation_history": [],
            },
        )
    )

    training = result["renderable_plan"]["training"]
    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert result["follow_up_questions"] == []
    assert result["selected_agents"] == ["personal_trainer"]
    assert training["status"] == "provisional"
    assert training["weekly_frequency"] == 3
    assert len(training["sessions"]) == 3
    assert len(training["sessions"][0]["exercises"]) > 1


def test_orchestration_does_not_block_when_only_height_is_missing():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "tenho 28 anos. 78kg e quero treinar 3x por semana",
                "user_profile": {},
                "conversation_history": [],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "plan_ready"
    assert result["follow_up_questions"] == []
    assert result["renderable_plan"]["training"]["weekly_frequency"] == 3


def test_orchestration_extracts_height_from_message():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "tenho 28 anos, 1,78 m, 78kg e quero treinar 3x por semana",
                "user_profile": {},
                "conversation_history": [],
            },
        )
    )

    assert "height_cm" not in result["intake"]["missing_profile_fields"]
    assert result["renderable_plan"]["training"]["weekly_frequency"] == 3


def test_orchestration_persists_renderable_workout_plan_when_session_is_present():
    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "tenho 28 anos, 1,78 m, 78kg e quero treinar 3x por semana",
                "user_profile": {"user_id": "user-123"},
                "conversation_history": [],
            },
            session_id="api-session-1",
        )
    )

    plan_id = result["workout_plan_id"]
    record = get_workout_plan(plan_id)

    assert result["plan_version"] == 1
    assert result["renderable_plan"]["workout_plan_id"] == plan_id
    assert record is not None
    assert record["user_id"] == "user-123"
    assert record["session_id"] == "api-session-1"
    assert record["source_message"] == "tenho 28 anos, 1,78 m, 78kg e quero treinar 3x por semana"
    assert record["plan"]["training"]["weekly_frequency"] == 3


def test_orchestration_does_not_create_duplicate_training_plan():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "weekly_frequency": 3,
                "sessions": [{"id": "day-1", "exercises": [{"name": "Supino reto"}]}],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino original",
        user_id="user-existing-training",
    )

    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero montar outro treino 4x por semana",
                "user_profile": {
                    "user_id": "user-existing-training",
                    "age": 28,
                    "weight_kg": 78,
                    "training_days_per_week": 4,
                },
                "conversation_history": [],
            },
        )
    )

    assert result["success"] is True
    assert result["mode"] == "conversation"
    assert result["selected_agents"] == []
    assert result["tasks"] == []
    assert result["renderable_plan"] is None
    assert result["plan_status"]["has_training_plan"] is True
    assert "nao vou criar outro plano" in result["user_facing_message"]


def test_orchestration_can_talk_about_existing_training_without_user_id():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "weekly_frequency": 3,
                "split": "Full body",
                "sessions": [
                    {
                        "id": "day-1",
                        "name": "Treino A",
                        "exercises": [{"name": "Supino reto"}, {"name": "Remada baixa"}],
                    }
                ],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino original",
        session_id="api-original-plan",
    )

    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "eu ja tenho um treino, voce consegue ver?",
                "user_profile": {},
                "conversation_history": [{"role": "user", "content": "ola"}],
            },
            session_id="api-chat-ola",
        )
    )

    assert result["success"] is True
    assert result["mode"] == "conversation"
    assert result["renderable_plan"] is None
    assert result["plan_status"]["has_training_plan"] is True
    assert result["current_plan"]["training"]["sessions"][0]["name"] == "Treino A"
    assert "Sim, consigo ver" in result["user_facing_message"]
    assert "Supino reto" in result["user_facing_message"]


def test_orchestration_routes_existing_training_difficulty_to_personal():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "weekly_frequency": 3,
                "split": "Full body",
                "sessions": [
                    {
                        "id": "day-2",
                        "name": "Treino B - Inferiores",
                        "exercises": [{"name": "Agachamento ou leg press"}],
                    }
                ],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino original",
        session_id="api-original-plan",
    )

    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "gostaria de falar sobre o meu treino, estou tendo dificuldade no treino de perna",
                "user_profile": {},
                "conversation_history": [{"role": "user", "content": "ola"}],
            },
            session_id="api-chat-ola",
        )
    )

    assert result["success"] is True
    assert result["mode"] == "conversation"
    assert result["selected_agents"] == ["personal_trainer"]
    assert result["tasks"] == ["existing_training_conversation"]
    assert result["task_results"]["existing_training_conversation"]["referenced_plan"]["lookup"] == "journeyfit_current_plan"
    assert "Vamos ajustar seu treino de perna" in result["user_facing_message"]


def test_orchestration_clarifies_posterior_leg_problem_in_saved_training_chat():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "weekly_frequency": 3,
                "split": "Full body",
                "sessions": [
                    {
                        "id": "day-2",
                        "name": "Treino B - Inferiores",
                        "exercises": [{"name": "Agachamento"}, {"name": "Leg press"}],
                    }
                ],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino original",
        session_id="api-original-plan",
    )

    ctx = SimpleNamespace(llm=_FakeLLMPosteriorGeneric())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "é um focado na parte de tras da perna",
                "user_profile": {},
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "queria falar sobre o treino de perna que tem um exercicio que esta ruim",
                    },
                    {
                        "role": "assistant",
                        "content": "Qual desses exercicios esta te incomodando?",
                    },
                ],
            },
            session_id="api-chat-ola",
        )
    )

    assert result["success"] is True
    assert result["mode"] == "conversation"
    assert "posteriores" in result["user_facing_message"]
    assert "dor" in result["user_facing_message"]
    assert "execucao" in result["user_facing_message"]
    assert "qual desses" not in result["user_facing_message"].lower()
    assert "stiff" not in result["user_facing_message"].lower()


def test_orchestration_does_not_recommend_new_posterior_exercise_when_user_reports_problem():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "weekly_frequency": 3,
                "split": "Full body",
                "sessions": [
                    {
                        "id": "day-2",
                        "name": "Treino B - Inferiores",
                        "exercises": [{"name": "Agachamento"}, {"name": "Leg press"}],
                    }
                ],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino original",
        session_id="api-original-plan",
    )

    ctx = SimpleNamespace(llm=_FakeLLMPosteriorRecommendation())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "é um pra parte de tras da perna",
                "user_profile": {},
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "tem um exercicio de perna que nao esta muito legal",
                    },
                    {
                        "role": "assistant",
                        "content": "Qual exercício está sentindo dificuldade ou desconforto?",
                    },
                ],
            },
            session_id="api-chat-ola",
        )
    )

    message = result["user_facing_message"].lower()
    assert result["success"] is True
    assert "antes de eu sugerir qualquer mudanca" in message
    assert "dor" in message
    assert "execucao" in message
    assert "stiff" not in message
    assert "mesa flexora" not in message
    assert "adicionar" not in message


def test_orchestration_skips_existing_training_but_allows_missing_nutrition():
    save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "weekly_frequency": 4,
                "sessions": [{"id": "day-1", "exercises": [{"name": "Remada"}]}],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino original",
        user_id="user-training-needs-diet",
    )

    ctx = SimpleNamespace(llm=_FakeLLM())
    result = json.loads(
        run_journeyfit_orchestration(
            ctx,
            {
                "user_message": "quero treino e dieta, pode assumir o que faltar",
                "user_profile": {
                    "user_id": "user-training-needs-diet",
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
    assert result["selected_agents"] == ["nutritionist"]
    assert result["tasks"] == ["nutrition_plan", "final_answer"]
    assert result["renderable_plan"]["training"]["status"] == "unavailable"
    assert result["renderable_plan"]["nutrition"]["status"] == "provisional"


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


def test_journeyfit_passthrough_rewrites_needs_more_info_json_to_text():
    result = passthrough_journeyfit_tool_result(
        session_id="missing",
        response_text=json.dumps(
            {
                "status": "needs_more_info",
                "mode": "needs_more_info",
                "user_facing_message": "Posso te perguntar algumas coisas para personalizar melhor?",
                "follow_up_questions": ["Qual a sua idade?"],
                "renderable_plan": None,
            }
        ),
    )

    assert result == "Posso te perguntar algumas coisas para personalizar melhor?"


def test_slash_command_returns_intake_message():
    ctx = SimpleNamespace()
    answer = run_journeyfit_slash_command(ctx, "oi")
    assert answer == "Oi! Como posso te ajudar hoje?"
