from __future__ import annotations

from plugins.journeyfit_orchestrator.context import OrchestrationContext
from plugins.journeyfit_orchestrator.planner import IntakeAnalyzer


def test_generic_protein_dinner_routes_to_nutrition():
    context = OrchestrationContext(user_message="Quero ideias de jantar com proteina", user_profile={})
    assessment = IntakeAnalyzer().assess(context)
    assert assessment.goal_type in {"meal_planning", "general_health", "unknown"}
    assert assessment.requires_nutrition is True
    assert assessment.requires_training is False
    assert assessment.requires_medical_intake is False


def test_knee_pain_requires_medical_and_training():
    context = OrchestrationContext(user_message="Tenho dor no joelho e quero correr", user_profile={})
    assessment = IntakeAnalyzer().assess(context)
    assert assessment.requires_medical_intake is True
    assert assessment.requires_training is True


def test_negated_pain_does_not_require_medical_intake():
    context = OrchestrationContext(
        user_message="Gere um plano upper/lower 4x para homem experiente, sem dor.",
        user_profile={},
    )
    assessment = IntakeAnalyzer().assess(context)
    assert assessment.goal_type == "training_plan"
    assert assessment.requires_medical_intake is False
    assert assessment.requires_training is True


def test_diabetes_diet_requires_medical_and_nutrition():
    context = OrchestrationContext(user_message="Tenho diabetes e quero emagrecer", user_profile={})
    assessment = IntakeAnalyzer().assess(context)
    assert assessment.requires_medical_intake is True
    assert assessment.requires_nutrition is True


def test_full_weekly_routine_requires_schedule():
    context = OrchestrationContext(user_message="Quero treino e dieta para 3 dias por semana", user_profile={})
    assessment = IntakeAnalyzer().assess(context)
    assert assessment.requires_nutrition is True
    assert assessment.requires_training is True
    assert assessment.requires_scheduler is True


def test_training_frequency_does_not_become_schedule_only():
    context = OrchestrationContext(user_message="tenho 28 anos. 78kg e quero treinar 3x por semana", user_profile={})
    assessment = IntakeAnalyzer().assess(context)
    assert assessment.goal_type == "training_plan"
    assert assessment.requested_domains == ["training"]
    assert assessment.requires_training is True
    assert assessment.requires_scheduler is False
