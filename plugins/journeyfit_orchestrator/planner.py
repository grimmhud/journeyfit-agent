"""Intake analysis and task planning for JourneyFit."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from plugins.journeyfit_orchestrator.context import OrchestrationContext
from plugins.journeyfit_orchestrator.policies import (
    infer_goal_type,
    infer_requested_domains,
    infer_risk_signals,
    missing_profile_fields,
)
from plugins.journeyfit_orchestrator.task_graph import AgentTask


@dataclass
class IntakeAssessment:
    goal_type: str
    requested_domains: list[str]
    risk_signals: list[str]
    limitations: list[str]
    missing_profile_fields: list[str]
    requires_medical_intake: bool
    requires_medical_validation: bool
    requires_nutrition: bool
    requires_training: bool
    requires_scheduler: bool
    can_answer_lightweight: bool


class IntakeAnalyzer:
    def assess(self, context: OrchestrationContext) -> IntakeAssessment:
        started_at = time.monotonic()
        profile = context.user_profile or {}
        history_text = _conversation_text(context)
        goal_type = infer_goal_type(history_text)
        requested_domains = infer_requested_domains(history_text)
        risk_signals = infer_risk_signals(history_text, profile)
        limitations: list[str] = []

        if goal_type == "rehab_or_pain" or "medical" in requested_domains:
            limitations.append("medical_sensitive")
        if profile.get("injuries") or profile.get("pain"):
            limitations.append("injury_or_pain")
        if profile.get("medications"):
            limitations.append("medication_context")

        requires_medical_intake = bool(risk_signals) or goal_type == "rehab_or_pain" or "medical" in requested_domains
        requires_medical_validation = requires_medical_intake or any(sig in risk_signals for sig in {"aggressive_goal", "profile_condition", "profile_medication"})
        requires_nutrition = "nutrition" in requested_domains or goal_type in {"weight_loss", "muscle_gain", "maintenance", "meal_planning", "general_health"}
        requires_training = "training" in requested_domains or goal_type in {"training_plan", "performance", "rehab_or_pain", "muscle_gain", "weight_loss"}
        requires_scheduler = "schedule" in requested_domains or goal_type == "routine_planning" or ("nutrition" in requested_domains and "training" in requested_domains)
        can_answer_lightweight = not requires_medical_intake and not requires_scheduler and (requires_nutrition ^ requires_training or (not requires_nutrition and not requires_training))

        assessment = IntakeAssessment(
            goal_type=goal_type,
            requested_domains=requested_domains,
            risk_signals=risk_signals,
            limitations=limitations,
            missing_profile_fields=missing_profile_fields(profile),
            requires_medical_intake=requires_medical_intake,
            requires_medical_validation=requires_medical_validation,
            requires_nutrition=requires_nutrition,
            requires_training=requires_training,
            requires_scheduler=requires_scheduler,
            can_answer_lightweight=can_answer_lightweight,
        )
        context.trace.append(
            {
                "event": "intake_assessed",
                "goal_type": goal_type,
                "requested_domains": requested_domains,
                "risk_signals": risk_signals,
                "requires_medical_intake": requires_medical_intake,
                "requires_nutrition": requires_nutrition,
                "requires_training": requires_training,
                "requires_scheduler": requires_scheduler,
                "can_answer_lightweight": can_answer_lightweight,
                "elapsed_ms": round((time.monotonic() - started_at) * 1000),
            }
        )
        return assessment


def _conversation_text(context: OrchestrationContext) -> str:
    parts = [context.user_message or ""]
    for item in context.conversation_history or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
        else:
            parts.append(str(item))
    return "\n".join(part for part in parts if part)


class TaskPlanner:
    def plan(self, context: OrchestrationContext) -> list[AgentTask]:
        started_at = time.monotonic()
        intake = context.intake
        tasks: list[AgentTask] = []
        medical_deps: list[str] = []

        if intake.get("requires_medical_intake"):
            tasks.append(AgentTask(
                id="medical_intake",
                agent="doctor",
                task_type="intake",
                objective="Avaliar risco, restricoes e limites clinicos do pedido.",
                expected_output="Triagem clinica, red flags, guardrails e perguntas necessarias.",
            ))
            medical_deps.append("medical_intake")

        if intake.get("requires_nutrition"):
            tasks.append(AgentTask(
                id="nutrition_plan",
                agent="nutritionist",
                task_type="domain_plan",
                objective="Criar orientacao alimentar aderente ao objetivo e restricoes.",
                dependencies=list(medical_deps),
                expected_output="Plano alimentar estruturado.",
            ))

        if intake.get("requires_training"):
            tasks.append(AgentTask(
                id="training_plan",
                agent="personal_trainer",
                task_type="domain_plan",
                objective="Criar plano de treino aderente ao objetivo, rotina e restricoes.",
                dependencies=list(medical_deps),
                expected_output="Plano de treino estruturado.",
            ))

        final_deps = [task.id for task in tasks if task.id != "final_answer"]
        if not final_deps and intake.get("requires_medical_intake"):
            final_deps = ["medical_intake"]

        tasks.append(AgentTask(
            id="final_answer",
            agent="synthesizer",
            task_type="synthesis",
            objective="Consolidar a resposta final para o usuario.",
            dependencies=final_deps,
            expected_output="Resposta final e segura.",
        ))
        context.trace.append(
            {
                "event": "plan_created",
                "task_ids": [task.id for task in tasks],
                "elapsed_ms": round((time.monotonic() - started_at) * 1000),
            }
        )
        return tasks
