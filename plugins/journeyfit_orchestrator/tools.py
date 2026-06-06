"""Tool handlers for JourneyFit."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from plugins.journeyfit_orchestrator.context import OrchestrationContext
from plugins.journeyfit_orchestrator.executor import TaskExecutor
from plugins.journeyfit_orchestrator.planner import IntakeAnalyzer, TaskPlanner
from plugins.journeyfit_orchestrator.policies import normalize_text
from plugins.journeyfit_orchestrator.specialists import SpecialistRunner
from tools.registry import tool_error


logger = logging.getLogger(__name__)

_RECENT_TOOL_RESULTS: dict[str, tuple[float, str]] = {}
_TOOL_RESULT_TTL_SECONDS = 300


def _default_training() -> dict[str, Any]:
    return {
        "status": "unavailable",
        "split": None,
        "weekly_frequency": None,
        "session_duration_minutes": {"min": None, "max": None},
        "sessions": [],
    }


def _default_nutrition() -> dict[str, Any]:
    return {
        "status": "unavailable",
        "kcal": {"min": None, "max": None},
        "macros": {
            "protein_g_per_kg": {"min": None, "max": None},
            "carbs_g_per_kg": {"min": None, "max": None},
            "fat_g_per_kg": {"min": None, "max": None},
        },
        "meals_per_day": {"min": None, "max": None},
        "hydration_ml_per_kg": {"min": None, "max": None},
        "timing": {
            "pre_workout_window": None,
            "post_workout_window": None,
        },
        "meal_examples": {
            "breakfast": [],
            "lunch_dinner": [],
            "snacks": [],
            "pre_workout": [],
            "post_workout": [],
        },
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"\d+(?:[.,]\d+)?", value)
        if match:
            return float(match.group(0).replace(",", "."))
    return None


def _range_around(value: Any, *, delta: float, fallback: dict[str, Any]) -> dict[str, Any]:
    number = _number(value)
    if number is None:
        return fallback
    return {"min": round(max(0, number - delta), 1), "max": round(number + delta, 1)}


def _range_from_pair(value: Any, *, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        min_value = _number(value.get("min"))
        max_value = _number(value.get("max"))
        if min_value is not None and max_value is not None:
            return {"min": min_value, "max": max_value}
        amount = _number(value.get("amount"))
        if amount is not None:
            return {"min": amount, "max": amount}
    amount = _number(value)
    if amount is not None:
        return {"min": amount, "max": amount}
    return fallback


def _question_items(questions: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for index, question in enumerate(questions[:8], start=1):
        if question:
            items.append({"id": f"q{index}", "question": question, "priority": "medium"})
    return items


def _notice_from_v0(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    notice = value.get("notice")
    if isinstance(notice, dict):
        return notice
    return None


def _exercise_item(raw: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = raw.get("name") or raw.get("exercise_name")
    if not name:
        return None
    return {
        "name": str(name),
        "sets": int(_number(raw.get("sets")) or 0),
        "reps": str(raw.get("reps") or ""),
        "rest_seconds": int(_number(raw.get("rest_seconds")) or _number(raw.get("rest")) or 60),
        "rir": str(raw.get("rir")) if raw.get("rir") not in (None, "") else None,
        "note": str(raw.get("note") or raw.get("notes")) if raw.get("note") or raw.get("notes") else None,
    }


def _starter_training_sessions(frequency: int, *, knee_sensitive: bool = False) -> list[dict[str, Any]]:
    templates = [
        (
            "Treino A - Superiores",
            "Peito, costas, ombros e braços",
            [
                ("Supino reto", "3-4", "6-10", "Mantenha 1-3 repeticoes em reserva."),
                ("Remada baixa", "3-4", "8-12", "Controle a volta do movimento."),
                ("Desenvolvimento com halteres", "3", "8-12", None),
                ("Puxada na frente", "3", "8-12", None),
                ("Triceps na polia", "2-3", "10-15", None),
                ("Rosca direta", "2-3", "10-15", None),
            ],
        ),
        (
            "Treino B - Inferiores",
            "Quadriceps, posteriores, gluteos e core",
            [
                ("Agachamento ou leg press", "3-4", "6-10", "Priorize amplitude segura."),
                ("Levantamento terra romeno", "3", "8-12", "Coluna neutra durante toda a serie."),
                ("Cadeira extensora", "3", "10-15", None),
                ("Mesa flexora", "3", "10-15", None),
                ("Panturrilha em pe", "3", "12-20", None),
                ("Prancha", "3", "30-60s", None),
            ],
        ),
        (
            "Treino C - Superiores volume",
            "Hipertrofia com volume moderado",
            [
                ("Supino inclinado com halteres", "3", "8-12", None),
                ("Remada unilateral", "3", "8-12", None),
                ("Elevacao lateral", "3", "12-20", "Use carga controlavel."),
                ("Crucifixo ou peck deck", "2-3", "10-15", None),
                ("Pulldown braços retos", "2-3", "10-15", None),
                ("Biceps alternado", "2-3", "10-15", None),
            ],
        ),
        (
            "Treino D - Inferiores volume",
            "Pernas e gluteos com foco em controle",
            [
                ("Leg press", "3-4", "10-12", None),
                ("Afundo ou passada", "3", "8-12", "Por perna."),
                ("Hip thrust", "3", "8-12", None),
                ("Cadeira flexora", "3", "10-15", None),
                ("Cadeira abdutora", "2-3", "12-20", None),
                ("Abdominal cabo ou maquina", "3", "10-15", None),
            ],
        ),
    ]
    if knee_sensitive:
        templates[1] = (
            "Treino B - Inferiores adaptado",
            "Pernas, gluteos e core com baixo estresse no joelho",
            [
                ("Bike leve ou eliptico", "1", "8-10 min", "Aquecimento sem dor."),
                ("Ponte de gluteos", "3", "10-15", "Interrompa se houver dor no joelho."),
                ("Mesa flexora", "3", "10-15", None),
                ("Abducao de quadril", "2-3", "12-20", None),
                ("Panturrilha sentada", "3", "12-20", None),
                ("Dead bug", "3", "8-12", "Controle o tronco."),
            ],
        )
        templates[3] = (
            "Treino D - Condicionamento adaptado",
            "Cardio leve, core e mobilidade sem impacto",
            [
                ("Bike ou caminhada leve", "1", "15-25 min", "Mantenha intensidade conversavel."),
                ("Remada baixa leve", "3", "10-12", None),
                ("Puxada na frente", "3", "10-12", None),
                ("Pallof press", "3", "10-12", "Por lado."),
                ("Mobilidade de quadril", "2", "8-10", "Sem forcar amplitude dolorosa."),
                ("Prancha lateral", "2-3", "20-40s", None),
            ],
        )
    count = min(max(frequency or 3, 1), len(templates))
    sessions: list[dict[str, Any]] = []
    for index, (name, focus, exercises) in enumerate(templates[:count], start=1):
        sessions.append(
            {
                "id": f"day-{index}",
                "name": name,
                "focus": focus,
                "estimated_duration_minutes": 60,
                "exercises": [
                    {
                        "name": exercise_name,
                        "sets": int(str(sets).split("-")[0]),
                        "reps": reps,
                        "rest_seconds": 90 if ex_index <= 2 else 60,
                        "rir": "1-3",
                        "note": note,
                    }
                    for ex_index, (exercise_name, sets, reps, note) in enumerate(exercises, start=1)
                ],
            }
        )
    return sessions


def _training_from_result(
    result: dict[str, Any],
    profile: dict[str, Any],
    *,
    risk_signals: list[str] | None = None,
    user_message: str = "",
) -> dict[str, Any]:
    default = _default_training()
    raw_sessions = result.get("sessions") or result.get("weekly_training_plan") or result.get("workout_days") or []
    if not raw_sessions and isinstance(result.get("split"), list):
        raw_sessions = result["split"]
    sessions: list[dict[str, Any]] = []
    if isinstance(raw_sessions, list):
        for index, raw_session in enumerate(raw_sessions, start=1):
            if not isinstance(raw_session, dict):
                continue
            raw_exercises = raw_session.get("exercises") or raw_session.get("workouts") or []
            exercises = [
                item
                for item in (_exercise_item(raw_exercise, exercise_index) for exercise_index, raw_exercise in enumerate(raw_exercises, start=1))
                if item is not None
            ]
            sessions.append(
                {
                    "id": str(raw_session.get("id") or f"day-{index}"),
                    "name": str(raw_session.get("name") or raw_session.get("day_name") or f"Treino {index}"),
                    "focus": str(raw_session.get("focus") or raw_session.get("day_description") or raw_session.get("objective") or "Treino"),
                    "estimated_duration_minutes": int(_number(raw_session.get("estimated_duration_minutes")) or 60),
                    "exercises": exercises,
                }
            )

    frequency = (
        _number(result.get("weekly_frequency"))
        or _number(result.get("target_frequency_days_per_week"))
        or _number(profile.get("training_days_per_week"))
    )
    if not sessions and not frequency:
        return default
    frequency_int = int(frequency or len(sessions) or 0)
    if not sessions and frequency_int:
        risk_text = normalize_text(" ".join(risk_signals or []) + " " + user_message)
        sessions = _starter_training_sessions(frequency_int, knee_sensitive="joelho" in risk_text)

    split = result.get("split") or result.get("training_split")
    if not isinstance(split, str) or not split.strip():
        split = "Upper/lower" if frequency_int >= 4 else "Full body"

    return {
        "status": "provisional",
        "split": split,
        "weekly_frequency": frequency_int,
        "session_duration_minutes": result.get("session_duration_minutes") or {"min": 45, "max": 75},
        "sessions": sessions,
    }


def _food_items_to_text(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    parts: list[str] = []
    for item in items:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("item_name") or item.get("name")
        if not name:
            continue
        quantity = item.get("quantity")
        unit = item.get("unit")
        if quantity not in (None, "") and unit:
            parts.append(f"{quantity} {unit} {name}")
        elif quantity not in (None, ""):
            parts.append(f"{quantity} {name}")
        else:
            parts.append(str(name))
    return ", ".join(parts)


def _meal_examples_from_result(result: dict[str, Any]) -> dict[str, list[str]]:
    examples = {key: list(value) for key, value in _default_nutrition()["meal_examples"].items()}
    direct = result.get("meal_examples")
    if isinstance(direct, dict):
        for key in examples:
            value = direct.get(key)
            if isinstance(value, list):
                examples[key] = [str(item) for item in value if item]

    raw_meals = result.get("daily_meals") or result.get("meal_structure") or []
    if not isinstance(raw_meals, list):
        return examples
    for raw_meal in raw_meals:
        if not isinstance(raw_meal, dict):
            continue
        name = normalize_text(str(raw_meal.get("meal_name") or raw_meal.get("name") or ""))
        text = raw_meal.get("description")
        foods = _food_items_to_text(raw_meal.get("food_items") or raw_meal.get("items"))
        line = str(foods or text or "").strip()
        if not line:
            continue
        if "cafe" in name or "manhã" in name or "manha" in name:
            examples["breakfast"].append(line)
        elif "pre" in name:
            examples["pre_workout"].append(line)
        elif "pos" in name or "pós" in name:
            examples["post_workout"].append(line)
        elif "lanche" in name or "ceia" in name:
            examples["snacks"].append(line)
        elif "almoco" in name or "almoço" in name or "jantar" in name:
            examples["lunch_dinner"].append(line)
    return examples


def _nutrition_from_result(result: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    default = _default_nutrition()
    strategy = result.get("nutrition_strategy") if isinstance(result.get("nutrition_strategy"), dict) else {}
    kcal_source = result.get("kcal") or strategy.get("kcal") or result.get("target_calories")
    macros_source = result.get("macros") if isinstance(result.get("macros"), dict) else {}
    distribution = result.get("macronutrient_distribution") if isinstance(result.get("macronutrient_distribution"), dict) else {}
    weight = _number(profile.get("weight_kg"))

    def grams_per_kg(key: str, grams_key: str, fallback: dict[str, Any]) -> dict[str, Any]:
        direct = _range_from_pair(macros_source.get(key), fallback=fallback)
        if direct != fallback:
            return direct
        grams = _number(distribution.get(grams_key))
        if grams is not None and weight:
            per_kg = grams / weight
            return {"min": round(max(0, per_kg - 0.1), 1), "max": round(per_kg + 0.1, 1)}
        return fallback

    meals = result.get("daily_meals") or result.get("meal_structure") or []
    meals_count = len(meals) if isinstance(meals, list) and meals else None
    hydration = result.get("hydration_ml_per_kg")
    hydration_recs = result.get("hydration_recommendations")
    if hydration in (None, {}) and isinstance(hydration_recs, dict):
        intake = hydration_recs.get("daily_water_intake")
        liters = _number(intake.get("amount") if isinstance(intake, dict) else intake)
        if liters is not None and weight:
            hydration = {"min": round((liters * 1000 / weight) - 3, 1), "max": round((liters * 1000 / weight) + 3, 1)}

    meal_examples = _meal_examples_from_result(result)
    if meal_examples == default["meal_examples"]:
        meal_examples = {
            "breakfast": ["Ovos ou iogurte natural com aveia e fruta"],
            "lunch_dinner": [
                "Frango, peixe ou carne magra com arroz, feijao e salada",
                "Omelete ou tofu com batata, legumes e azeite",
            ],
            "snacks": ["Iogurte, fruta e castanhas", "Sanduiche integral com proteina magra"],
            "pre_workout": ["Banana com aveia ou pao integral com proteina leve"],
            "post_workout": ["Refeicao com proteina magra e carboidrato complexo"],
        }

    estimated_kcal = None
    if kcal_source:
        estimated_kcal = kcal_source.get("amount") if isinstance(kcal_source, dict) else kcal_source
    elif weight:
        estimated_kcal = weight * 30

    return {
        "status": "provisional",
        "kcal": _range_around(estimated_kcal, delta=150, fallback=default["kcal"]),
        "macros": {
            "protein_g_per_kg": grams_per_kg("protein_g_per_kg", "protein_g", {"min": 1.6, "max": 2.2}),
            "carbs_g_per_kg": grams_per_kg("carbs_g_per_kg", "carb_g", {"min": 2.0, "max": 4.0}),
            "fat_g_per_kg": grams_per_kg("fat_g_per_kg", "fat_g", {"min": 0.6, "max": 1.0}),
        },
        "meals_per_day": {"min": meals_count, "max": meals_count} if meals_count else {"min": 3, "max": 5},
        "hydration_ml_per_kg": _range_from_pair(hydration, fallback={"min": 30, "max": 40}),
        "timing": result.get("timing") if isinstance(result.get("timing"), dict) else {
            "pre_workout_window": "60-120 min antes do treino",
            "post_workout_window": "ate 2h apos o treino",
        },
        "meal_examples": meal_examples,
    }


def _medical_notices(context: OrchestrationContext) -> list[dict[str, Any]]:
    intake = context.intake if isinstance(context.intake, dict) else {}
    risk_signals = intake.get("risk_signals") if isinstance(intake.get("risk_signals"), list) else []
    if not intake.get("requires_medical_intake") and not risk_signals:
        return []
    risk_text = normalize_text(", ".join(str(item) for item in risk_signals) + " " + context.user_message)
    if "joelho" in risk_text:
        message = (
            "Dor no joelho ao agachar pede triagem profissional antes de cargas altas, "
            "saltos, corrida intensa, agachamentos profundos ou afundos."
        )
    else:
        message = (
            "Ha sinais de dor, lesao ou condicao clinica no pedido; mantenha o plano leve "
            "e procure avaliacao profissional se houver piora, dor persistente ou sintomas novos."
        )
    return [
        {
            "agent": "doctor",
            "type": "restriction",
            "severity": "moderate",
            "message": message,
        }
    ]


def _extract_v0_output(context: OrchestrationContext, *, mode: str, assistant_message: str, questions: list[str]) -> dict[str, Any] | None:
    if mode != "plan_ready":
        return None

    notices: list[dict[str, Any]] = _medical_notices(context)
    training = _default_training()
    nutrition = _default_nutrition()

    for result in (context.task_results or {}).values():
        if not isinstance(result, dict):
            continue
        v0_output = result.get("v0_output")
        if isinstance(v0_output, dict):
            notice = _notice_from_v0(v0_output)
            if notice:
                notices.append(notice)
            if isinstance(v0_output.get("training"), dict):
                training = v0_output["training"]
            if isinstance(v0_output.get("nutrition"), dict):
                nutrition = v0_output["nutrition"]

    training_result = context.task_results.get("training_plan")
    if isinstance(training_result, dict) and training == _default_training():
        risk_signals = context.intake.get("risk_signals") if isinstance(context.intake, dict) else []
        training = _training_from_result(
            training_result,
            context.user_profile,
            risk_signals=risk_signals,
            user_message=context.user_message,
        )

    nutrition_result = context.task_results.get("nutrition_plan")
    if isinstance(nutrition_result, dict) and nutrition == _default_nutrition():
        nutrition = _nutrition_from_result(nutrition_result, context.user_profile)

    return {
        "status": mode,
        "mode": mode,
        "user_facing_message": assistant_message,
        "notices": notices,
        "follow_up_questions": _question_items(questions),
        "training": training,
        "nutrition": nutrition,
    }


def _envelope(payload: dict[str, Any], *, questions: list[str] | None = None) -> dict[str, Any]:
    questions = questions or []
    payload.setdefault("status", payload.get("mode") or "conversation")
    payload.setdefault("missing_information", questions)
    payload.setdefault("renderable_plan", None)
    payload.setdefault("debug", {"agent": "journeyfit_orchestrator"})
    return payload


def remember_journeyfit_tool_result(
    *,
    tool_name: str,
    result: str,
    session_id: str = "",
    **_: Any,
) -> None:
    if tool_name != "journeyfit_orchestrate" or not session_id:
        return
    try:
        parsed = json.loads(result)
    except Exception:
        return
    if isinstance(parsed, dict) and parsed.get("success") is True:
        _RECENT_TOOL_RESULTS[session_id] = (time.monotonic(), result)


def passthrough_journeyfit_tool_result(
    *,
    session_id: str = "",
    response_text: str = "",
    **_: Any,
) -> str | None:
    if session_id:
        stored = _RECENT_TOOL_RESULTS.pop(session_id, None)
        if stored:
            created_at, result = stored
            if time.monotonic() - created_at <= _TOOL_RESULT_TTL_SECONDS:
                try:
                    parsed = json.loads(result)
                except Exception:
                    return result
                if isinstance(parsed, dict) and isinstance(parsed.get("renderable_plan"), dict):
                    return json.dumps(parsed["renderable_plan"], ensure_ascii=False)
                return result

    text = (response_text or "").strip()
    if not text:
        return None
    try:
        parsed_text = json.loads(text)
    except Exception:
        parsed_text = None
    if isinstance(parsed_text, dict):
        return None
    return json.dumps(
        {
            "status": "conversation",
            "mode": "conversation",
            "user_facing_message": text,
            "follow_up_questions": [],
            "renderable_plan": None,
        },
        ensure_ascii=False,
    )


def _build_context(args: dict[str, Any]) -> OrchestrationContext:
    return OrchestrationContext(
        user_message=str(args.get("user_message") or ""),
        user_profile=args.get("user_profile") or {},
        conversation_history=args.get("conversation_history") or [],
        profile_name=str(args.get("profile_name") or args.get("profile") or "orchestrator"),
    )


def _history_text(context: OrchestrationContext) -> str:
    parts = [context.user_message or ""]
    for item in context.conversation_history or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
        else:
            parts.append(str(item))
    return "\n".join(part for part in parts if part)


def _user_prefers_assumptions(text: str) -> bool:
    normalized = normalize_text(text)
    markers = [
        "pode assumir",
        "pode fazer suposicoes",
        "pode seguir com suposicoes",
        "sem mais perguntas",
        "segue com o que tem",
        "não precisa perguntar",
        "nao precisa perguntar",
        "não pergunte",
        "nao pergunte",
    ]
    return any(marker in normalized for marker in markers)


def _infer_profile_hints(context: OrchestrationContext) -> dict[str, Any]:
    profile = dict(context.user_profile or {})
    text = _history_text(context)
    normalized = normalize_text(text)

    if "age" not in profile or profile.get("age") in (None, ""):
        match = re.search(r"\b(\d{1,3})\s*(?:anos|anos de idade)\b", normalized)
        if match:
            profile["age"] = int(match.group(1))

    if "weight_kg" not in profile or profile.get("weight_kg") in (None, ""):
        match = re.search(r"\b(\d{2,3}(?:[.,]\d+)?)\s*(?:kg|kgs|quilo|quilos|kilo|kilos)\b", normalized)
        if match:
            profile["weight_kg"] = float(match.group(1).replace(",", "."))

    if "training_days_per_week" not in profile or profile.get("training_days_per_week") in (None, ""):
        match = re.search(r"\b(\d)\s*(?:x|vezes|dias?)\s*(?:por semana|na semana|/semana)?\b", normalized)
        if match:
            profile["training_days_per_week"] = int(match.group(1))

    if "equipment_available" not in profile or profile.get("equipment_available") in (None, "", []):
        equipment: list[str] = []
        if "academia" in normalized or "gym" in normalized:
            equipment.append("academia")
        if "casa" in normalized or "home" in normalized:
            equipment.append("casa")
        if any(token in normalized for token in ["halter", "dumbbell", "barra", "elast", "máquina", "maquina", "rack", "banco"]):
            equipment.extend(["equipamentos livres"])
        if equipment:
            profile["equipment_available"] = sorted(set(equipment))

    return profile


def _question_for_field(field_name: str) -> str | None:
    mapping = {
        "age": "Qual a sua idade?",
        "weight_kg": "Qual o seu peso atual?",
        "training_days_per_week": "Quantos dias por semana voce consegue treinar?",
        "meal_schedule": "Como e sua rotina de refeicoes ao longo do dia?",
        "equipment_available": "Voce treina em academia, em casa ou nos dois?",
        "injuries": "Tem alguma lesao que eu precise considerar?",
        "pain": "Tem alguma dor atual ou recorrente?",
        "conditions": "Tem alguma condicao de saude importante?",
        "medications": "Usa algum medicamento?",
    }
    return mapping.get(field_name)


def _render_follow_up_message(questions: list[str]) -> str:
    if not questions:
        return "Posso personalizar melhor o contexto. Se quiser, responda com mais detalhes e eu ajusto."
    lines = [
        "Posso personalizar melhor o contexto com algumas perguntas opcionais.",
        "Voce pode responder so as que quiser; se preferir, eu sigo com suposicoes seguras.",
        "",
    ]
    lines.extend(f"- {question}" for question in questions)
    return "\n".join(lines)


def _fallback_assistant_message(context: OrchestrationContext, *, mode: str, questions: list[str]) -> str:
    if mode == "needs_more_info":
        return _render_follow_up_message(questions)
    has_training = isinstance(context.task_results.get("training_plan"), dict)
    has_nutrition = isinstance(context.task_results.get("nutrition_plan"), dict)
    if has_training and has_nutrition:
        return "Montei uma primeira versao do plano de treino e nutricao com os dados disponiveis."
    if has_training:
        return "Montei uma primeira versao do plano de treino com os dados disponiveis."
    if has_nutrition:
        return "Montei uma primeira versao do plano alimentar com os dados disponiveis."
    return "Montei uma primeira resposta com os dados disponiveis."


def _conversation_mode(context: OrchestrationContext) -> bool:
    text = normalize_text(context.user_message or "")
    return text in {"oi", "ola", "bom dia", "boa tarde", "boa noite", "hello", "hi"}


def _route_question_fields(assessment) -> list[str]:
    if assessment.requires_medical_intake:
        return ["pain", "injuries", "conditions"]
    if assessment.requires_training and assessment.requires_nutrition:
        return ["age", "weight_kg", "training_days_per_week"]
    if assessment.requires_nutrition:
        return ["age", "weight_kg", "meal_schedule"]
    if assessment.requires_training:
        return ["age", "weight_kg", "training_days_per_week"]
    return ["age", "weight_kg", "training_days_per_week"]


def _missing_route_fields(profile: dict[str, Any], fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        value = profile.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    return missing


def run_journeyfit_orchestration(ctx, args: dict, **kwargs) -> str:
    try:
        started_at = time.monotonic()
        parent_agent = kwargs.get("parent_agent")
        trace_id = str(kwargs.get("task_id") or kwargs.get("request_id") or kwargs.get("session_id") or "-")
        context = _build_context(args)
        context.shared["trace_id"] = trace_id
        context.trace.append(
            {
                "event": "tool_invoked",
                "tool": "journeyfit_orchestrate",
                "profile": context.profile_name,
                "trace_id": trace_id,
                "user_message": context.user_message,
            }
        )
        logger.info(
            "journeyfit_orchestrate start trace_id=%s profile=%s message_chars=%d history_messages=%d",
            trace_id,
            context.profile_name,
            len(context.user_message or ""),
            len(context.conversation_history or []),
        )
        if _conversation_mode(context):
            payload = {
                "success": True,
                "mode": "conversation",
                "answer": "",
                "assistant_message": "Oi! Como posso te ajudar hoje?",
                "user_facing_message": "Oi! Como posso te ajudar hoje?",
                "intake": {},
                "selected_agents": [],
                "tasks": [],
                "task_results": {},
                "warnings": [],
                "follow_up_questions": [],
                "trace": context.trace,
            }
            _envelope(payload)
            return json.dumps(payload, ensure_ascii=False)

        context.user_profile = _infer_profile_hints(context)
        intake_started_at = time.monotonic()
        assessment = IntakeAnalyzer().assess(context)
        logger.info(
            "journeyfit_orchestrate intake done trace_id=%s elapsed_ms=%d goal_type=%s medical=%s nutrition=%s training=%s scheduler=%s lightweight=%s",
            trace_id,
            round((time.monotonic() - intake_started_at) * 1000),
            assessment.goal_type,
            assessment.requires_medical_intake,
            assessment.requires_nutrition,
            assessment.requires_training,
            assessment.requires_scheduler,
            assessment.can_answer_lightweight,
        )
        context.intake = assessment.__dict__

        route_fields = _route_question_fields(assessment)
        missing_route_fields = _missing_route_fields(context.user_profile, route_fields)
        if not assessment.requires_medical_intake and missing_route_fields and not _user_prefers_assumptions(context.user_message or ""):
            follow_up_questions: list[str] = []
            for field_name in missing_route_fields[:3]:
                question = _question_for_field(field_name)
                if question and question not in follow_up_questions:
                    follow_up_questions.append(question)
            assistant_message = _render_follow_up_message(follow_up_questions)
            payload = {
                "success": True,
                "mode": "needs_more_info",
                "answer": "",
                "assistant_message": assistant_message,
                "user_facing_message": assistant_message,
                "intake": context.intake,
                "selected_agents": [],
                "tasks": [],
                "task_results": {},
                "warnings": context.warnings,
                "follow_up_questions": follow_up_questions,
                "trace": context.trace,
            }
            _envelope(payload, questions=follow_up_questions)
            logger.info(
                "journeyfit_orchestrate needs_more_info trace_id=%s profile=%s questions=%d trace=%d elapsed_ms=%d",
                trace_id,
                context.profile_name,
                len(follow_up_questions),
                len(context.trace),
                round((time.monotonic() - started_at) * 1000),
            )
            return json.dumps(payload, ensure_ascii=False)

        context.active_constraints = {
            "risk_signals": assessment.risk_signals,
            "limitations": assessment.limitations,
        }
        tasks = TaskPlanner().plan(context)
        context.selected_agents = sorted({task.agent for task in tasks if task.agent != "synthesizer"})
        runner = SpecialistRunner(ctx, parent_agent=parent_agent)
        TaskExecutor(runner=runner).run(tasks, context)
        final = context.task_results.get("final_answer") or {}
        answer = final.get("user_facing_response") or final.get("answer") or final.get("summary") or ""
        follow_up_questions: list[str] = []
        for task_id in [task.id for task in tasks]:
            result = context.task_results.get(task_id) or {}
            if not isinstance(result, dict):
                continue
            for field_name in ("questions", "user_questions_needed", "follow_up_questions"):
                items = result.get(field_name)
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, str) and item not in follow_up_questions:
                        follow_up_questions.append(item)
        needs_more_info = any(
            str((context.task_results.get(task_id) or {}).get("status") or "").lower() == "needs_more_info"
            for task_id in context.task_results
        )
        mode = "needs_more_info" if needs_more_info else "plan_ready"
        assistant_message = answer or _fallback_assistant_message(
            context,
            mode=mode,
            questions=follow_up_questions,
        )
        payload = {
            "success": True,
            "mode": mode,
            "answer": answer,
            "assistant_message": assistant_message,
            "user_facing_message": assistant_message,
            "intake": context.intake,
            "selected_agents": context.selected_agents,
            "tasks": [task.id for task in tasks],
            "task_results": context.task_results,
            "warnings": context.warnings,
            "follow_up_questions": follow_up_questions,
            "trace": context.trace,
        }
        _envelope(payload, questions=follow_up_questions)
        payload["renderable_plan"] = _extract_v0_output(
            context,
            mode=mode,
            assistant_message=assistant_message,
            questions=follow_up_questions,
        )
        logger.info(
            "journeyfit_orchestrate done trace_id=%s profile=%s tasks=%d follow_up_questions=%d trace=%d elapsed_ms=%d",
            trace_id,
            context.profile_name,
            len(tasks),
            len(follow_up_questions),
            len(context.trace),
            round((time.monotonic() - started_at) * 1000),
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.exception("journeyfit_orchestrate failed")
        return tool_error(f"journeyfit_orchestrate failed: {exc}")


def run_journeyfit_slash_command(ctx, raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "Uso: /journeyfit <pedido>"
    result_json = run_journeyfit_orchestration(
        ctx,
        {"user_message": text, "user_profile": {}, "conversation_history": []},
    )
    try:
        result = json.loads(result_json)
    except Exception:
        return result_json
    if result.get("mode") == "needs_more_info":
        return result.get("assistant_message") or result_json
    return result.get("answer") or result.get("assistant_message") or result.get("user_facing_message") or result_json
