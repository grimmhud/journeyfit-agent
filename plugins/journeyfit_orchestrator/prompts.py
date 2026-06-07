"""Prompt templates for JourneyFit specialists."""

from __future__ import annotations

import json
from typing import Any

from plugins.journeyfit_orchestrator.context import OrchestrationContext
from plugins.journeyfit_orchestrator.task_graph import AgentTask


def _payload(context: OrchestrationContext, task: AgentTask) -> dict[str, Any]:
    return {
        "user_message": context.user_message,
        "user_profile": context.user_profile,
        "conversation_history": context.conversation_history,
        "intake": context.intake,
        "active_constraints": context.active_constraints,
        "task": {
            "id": task.id,
            "agent": task.agent,
            "task_type": task.task_type,
            "objective": task.objective,
            "dependencies": task.dependencies,
            "expected_output": task.expected_output,
            "validation_target": task.validation_target,
            "revision_of": task.revision_of,
        },
        "task_results": context.task_results,
        "warnings": context.warnings,
        "shared": context.shared,
    }


def build_instructions(context: OrchestrationContext, task: AgentTask) -> str:
    payload = json.dumps(_payload(context, task), ensure_ascii=False, indent=2)
    if task.agent == "doctor":
        return (
            "Você é o agente Medico do JourneyFit. Faça triagem de risco e validação clínica. "
            "Responda somente em JSON válido seguindo o schema solicitado. "
            "Se houver sinal grave, marque risk_level='urgent' e explique de forma prudente. "
            "Se faltarem dados importantes para triagem, marque status='needs_more_info' e liste perguntas opcionais curtas, "
            "mas continue com suposições seguras quando isso não aumentar risco. "
            f"Contexto:\n{payload}"
        )
    if task.agent == "nutritionist":
        return (
            "Se shared.plan_status.has_nutrition_plan for true, nao crie outra dieta; ajuste ou explique a dieta salva. "
            "Quando precisar ver a dieta atual, chame journeyfit_current_plan com domain='nutrition'. "
            "Você é o agente Nutricionista do JourneyFit. Crie orientação alimentar aderente, prática e segura. "
            "Responda somente em JSON válido seguindo o schema solicitado. "
            "Se faltarem dados importantes para personalização, marque status='needs_more_info' e liste perguntas opcionais curtas, "
            "mas siga com suposições explícitas quando for seguro. "
            f"Contexto:\n{payload}"
        )
    if task.agent == "personal_trainer":
        if task.task_type == "existing_plan_conversation":
            return (
                "Voce e o agente Personal Trainer do JourneyFit. O usuario quer conversar sobre um treino ja salvo. "
                "Nao crie outro treino e nao invente o conteudo do plano. "
                "Use journeyfit_current_plan com domain='training' quando precisar ver exercicios, sessoes, frequencia ou detalhes do treino salvo. "
                "Responda somente em JSON valido seguindo o schema solicitado. "
                "Se a conversa anterior fala de problema, dificuldade, desconforto ou exercicio ruim e a nova mensagem mencionar posterior, parte de tras da perna, isquiotibiais, hamstrings ou gluteos, trate como continuidade para entender o problema. Primeiro pergunte se e dor/fisgada, falta de ativacao, execucao, carga ou amplitude; nao recomende adicionar, trocar ou intensificar exercicios antes disso. "
                "Se a dificuldade envolver dor forte, piora, sintomas neurologicos, tontura, falta de ar, dor no peito ou lesao, seja conservador e recomende avaliacao profissional. "
                f"Contexto:\n{payload}"
            )
        return (
            "Se shared.plan_status.has_training_plan for true, nao crie outro treino; ajuste ou explique o treino salvo. "
            "Quando precisar ver o treino atual, chame journeyfit_current_plan com domain='training'. "
            "Você é o agente Personal Trainer do JourneyFit. Crie um plano de treino estruturado, progressivo e seguro. "
            "Responda somente em JSON válido seguindo o schema solicitado. "
            "Se faltarem dados importantes para personalização, marque status='needs_more_info' e liste perguntas opcionais curtas, "
            "mas siga com suposições explícitas quando for seguro. "
            f"Contexto:\n{payload}"
        )
    if task.agent == "scheduler":
        return (
            "Você é o agente Scheduler do JourneyFit. Combine treino, nutrição e disponibilidade em uma rotina executável. "
            "Responda somente em JSON válido seguindo o schema solicitado. "
            f"Contexto:\n{payload}"
        )
    if task.agent == "reviewer":
        return (
            "Você é o agente Reviewer do JourneyFit. Verifique consistência, segurança e conflitos entre saídas. "
            "Responda somente em JSON válido seguindo o schema solicitado. "
            f"Contexto:\n{payload}"
        )
    return (
        "Você é o agente Synthesizer do JourneyFit. Converta os outputs estruturados em uma resposta final amigável. "
        "Responda somente em JSON válido seguindo o schema solicitado. "
        f"Contexto:\n{payload}"
    )
