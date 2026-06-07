"""Specialist runner for JourneyFit."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Any

from plugins.journeyfit_orchestrator.context import OrchestrationContext
from plugins.journeyfit_orchestrator.prompts import build_instructions
from plugins.journeyfit_orchestrator.schemas import SPECIALIST_SCHEMAS
from plugins.journeyfit_orchestrator.task_graph import AgentTask
from tools.delegate_tool import delegate_task


SPECIALIST_TIMEOUT_SECONDS = 300.0
_DELEGATE_TOOLSET_SENTINEL = "__journeyfit_leaf__"

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) <= 2:
        return ""
    body = "\n".join(lines[1:])
    if body.endswith("```"):
        body = body[:-3]
    return body.strip()


def _parse_json_dict(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    for candidate in (text, _strip_code_fences(text)):
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _specialist_prompt(task: AgentTask) -> str:
    if task.agent == "doctor":
        return "Você é o agente Medico do JourneyFit. Faça triagem de risco e validação clínica."
    if task.agent == "nutritionist":
        return "Voce e o agente Nutricionista do JourneyFit. Crie orientacao alimentar aderente, pratica e segura. Se ja houver dieta salva no contexto, use journeyfit_current_plan com domain='nutrition' quando precisar ver o conteudo e ajuste ou explique a dieta atual em vez de criar outra."
    if task.agent == "personal_trainer":
        if task.task_type == "existing_plan_conversation":
            return "Voce e o agente Personal Trainer do JourneyFit. Converse tecnicamente sobre o treino salvo do usuario. Nao crie outro treino. Use journeyfit_current_plan com domain='training' para ver o conteudo salvo antes de responder sobre exercicios, dificuldades, ajustes, progressao ou execucao. Se a conversa fala de problema ou dificuldade e a nova mensagem mencionar posterior, parte de tras da perna, isquiotibiais, hamstrings ou gluteos, trate como continuidade para entender o problema: pergunte se e dor/fisgada, falta de ativacao, execucao, carga ou amplitude antes de recomendar adicionar ou trocar exercicios."
        return "Voce e o agente Personal Trainer do JourneyFit. Crie um plano de treino estruturado, progressivo e seguro. Se ja houver treino salvo no contexto, use journeyfit_current_plan com domain='training' quando precisar ver o conteudo e ajuste ou explique o treino atual em vez de criar outro."
    if task.agent == "scheduler":
        return "Você é o agente Scheduler do JourneyFit. Combine treino, nutrição e disponibilidade em uma rotina executável."
    if task.agent == "reviewer":
        return "Você é o agente Reviewer do JourneyFit. Verifique consistência, segurança e conflitos entre saídas."
    return "Você é o agente Synthesizer do JourneyFit. Converta os outputs estruturados em uma resposta final amigável."


def _build_delegate_goal(task: AgentTask, schema_name: str) -> str:
    return (
        f"{_specialist_prompt(task)} "
        f"Seu objetivo especifico e: {task.objective}. "
        f"Retorne APENAS um JSON valido seguindo o schema {schema_name}. "
        "Nao use markdown, blocos de codigo ou explicacoes fora do JSON."
    )


def _build_delegate_context(context: OrchestrationContext, task: AgentTask, schema: dict[str, Any]) -> str:
    payload = {
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
    return (
        "Use o contexto abaixo como entrada estruturada.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Regras de saida:\n"
        f"- Retorne apenas um objeto JSON valido conforme o schema {schema['name']}.\n"
        "- Nao inclua texto adicional, marcadores de markdown ou blocos de codigo.\n"
        "- Se faltar informacao, use os campos apropriados do schema para refletir isso."
    )


class SpecialistRunner:
    def __init__(self, plugin_ctx, parent_agent=None, delegate_fn=delegate_task):
        self.plugin_ctx = plugin_ctx
        self.parent_agent = parent_agent
        self.delegate_fn = delegate_fn

    def _run_via_delegate(self, task: AgentTask, context: OrchestrationContext, schema: dict[str, Any]) -> dict[str, Any]:
        started_at = time.monotonic()
        logger.debug("JourneyFit delegating task %s to subagent %s", task.id, task.agent)
        context.trace.append(
            {
                "event": "delegate_task_invoked",
                "task_id": task.id,
                "agent": task.agent,
                "task_type": task.task_type,
            }
        )
        delegated = self.delegate_fn(
            goal=_build_delegate_goal(task, schema["name"]),
            context=_build_delegate_context(context, task, schema),
            toolsets=[_DELEGATE_TOOLSET_SENTINEL],
            role="leaf",
            parent_agent=self.parent_agent,
        )
        try:
            payload = json.loads(delegated)
        except Exception as exc:
            logger.warning(
                "JourneyFit delegate task failed to parse task_id=%s agent=%s elapsed_ms=%d",
                task.id,
                task.agent,
                round((time.monotonic() - started_at) * 1000),
            )
            return {
                "error": "delegate_task_parse_failed",
                "raw": delegated,
                "details": str(exc),
            }
        if not isinstance(payload, dict):
            return {
                "error": "delegate_task_returned_invalid_payload",
                "raw": payload,
            }
        results = payload.get("results") or []
        if not results or not isinstance(results, list):
            logger.warning(
                "JourneyFit delegate task returned no results task_id=%s agent=%s elapsed_ms=%d",
                task.id,
                task.agent,
                round((time.monotonic() - started_at) * 1000),
            )
            return {
                "error": "delegate_task_returned_no_results",
                "raw": payload,
            }
        entry = results[0] if isinstance(results[0], dict) else {}
        status = str(entry.get("status") or "").lower()
        summary = str(entry.get("summary") or "").strip()
        if status not in {"completed", ""} and not summary:
            logger.warning(
                "JourneyFit delegate task returned error task_id=%s agent=%s status=%s elapsed_ms=%d",
                task.id,
                task.agent,
                status,
                round((time.monotonic() - started_at) * 1000),
            )
            return {
                "error": entry.get("error") or f"delegate_task_{status or 'failed'}",
                "delegate_result": payload,
            }
        parsed = _parse_json_dict(summary)
        if parsed is None:
            logger.warning(
                "JourneyFit delegate task parse failed task_id=%s agent=%s elapsed_ms=%d",
                task.id,
                task.agent,
                round((time.monotonic() - started_at) * 1000),
            )
            return {
                "error": "specialist_parse_failed",
                "raw": summary,
                "delegate_result": payload,
            }
        parsed.setdefault("agent", task.agent)
        parsed.setdefault("task_id", task.id)
        parsed.setdefault("delegate_status", entry.get("status"))
        parsed.setdefault("delegate_exit_reason", entry.get("exit_reason"))
        parsed.setdefault("delegate_tool_trace", entry.get("tool_trace") or [])
        context.trace.append(
            {
                "event": "delegate_task_completed",
                "task_id": task.id,
                "agent": task.agent,
                "status": entry.get("status"),
                "exit_reason": entry.get("exit_reason"),
                "elapsed_ms": round((time.monotonic() - started_at) * 1000),
            }
        )
        logger.info(
            "JourneyFit delegate task done task_id=%s agent=%s status=%s elapsed_ms=%d",
            task.id,
            task.agent,
            entry.get("status") or "-",
            round((time.monotonic() - started_at) * 1000),
        )
        return parsed

    def run(self, task: AgentTask, context: OrchestrationContext) -> dict[str, Any]:
        started_at = time.monotonic()
        schema = SPECIALIST_SCHEMAS.get((task.agent, task.task_type))
        if schema is None:
            return {
                "error": "unknown_specialist",
                "task": asdict(task),
            }
        if self.parent_agent is not None:
            try:
                return self._run_via_delegate(task, context, schema)
            except Exception as exc:
                return {
                    "error": "delegate_task_failed",
                    "details": str(exc),
                }

        result = self.plugin_ctx.llm.complete_structured(
            instructions=build_instructions(context, task),
            input=[{"type": "text", "text": context.user_message}],
            json_schema=schema,
            schema_name=schema["name"],
            purpose=f"journeyfit.{task.agent}.{task.task_type}",
            temperature=0.2,
            max_tokens=1600,
            timeout=SPECIALIST_TIMEOUT_SECONDS,
        )
        parsed = getattr(result, "parsed", None)
        if parsed is None:
            logger.warning(
                "JourneyFit specialist structured call failed task_id=%s agent=%s task_type=%s elapsed_ms=%d",
                task.id,
                task.agent,
                task.task_type,
                round((time.monotonic() - started_at) * 1000),
            )
            return {
                "error": "specialist_parse_failed",
                "raw": getattr(result, "text", ""),
            }
        if isinstance(parsed, dict) and "agent" not in parsed:
            parsed["agent"] = task.agent
        logger.info(
            "JourneyFit specialist done task_id=%s agent=%s task_type=%s elapsed_ms=%d",
            task.id,
            task.agent,
            task.task_type,
            round((time.monotonic() - started_at) * 1000),
        )
        return parsed
