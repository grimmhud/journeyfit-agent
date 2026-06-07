"""Heuristics for JourneyFit routing."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


MEDICAL_INTAKE_TERMS = [
    "dor no peito",
    "desmaio",
    "tontura",
    "falta de ar",
    "gravida",
    "gravidez",
    "pos-parto",
    "pos parto",
    "diabetes",
    "hipertensao",
    "cardiaco",
    "cirurgia",
    "lesao",
    "dor no joelho",
    "dor lombar",
    "remedio",
    "medicamento",
    "transtorno alimentar",
    "tendinite",
    "lesao no ombro",
    "lesao no joelho",
]

AGGRESSIVE_GOAL_TERMS = [
    "perder 10 kg em 1 mes",
    "1000 calorias",
    "jejum extremo",
    "secar rapido",
    "emagrecer muito rapido",
]


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower()


def _without_negated_risk_terms(text: str) -> str:
    normalized = normalize_text(text)
    patterns = [
        r"\bsem\s+dor(?:es)?\b",
        r"\bsem\s+les(?:ao|oes)\b",
        r"\bsem\s+tendinite\b",
        r"\bsem\s+limitac(?:ao|oes)\b",
        r"\bnao\s+tenho\s+dor(?:es)?\b",
        r"\bnao\s+tenho\s+les(?:ao|oes)\b",
        r"\bnao\s+sinto\s+dor(?:es)?\b",
    ]
    for pattern in patterns:
        normalized = re.sub(pattern, " ", normalized)
    return normalized


def contains_any(text: str, terms: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms)


def _profile_field_names() -> list[str]:
    return [
        "age",
        "sex",
        "height_cm",
        "weight_kg",
        "training_experience",
        "training_days_per_week",
        "available_days",
        "equipment_available",
        "injuries",
        "pain",
        "conditions",
        "medications",
    ]


def missing_profile_fields(profile: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in _profile_field_names():
        value = profile.get(field)
        if field in {"injuries", "pain", "conditions", "medications"}:
            if value in (None, "", {}):
                missing.append(field)
            continue
        if value in (None, "", [], {}):
            missing.append(field)
    return missing


def infer_goal_type(message: str) -> str:
    text = _without_negated_risk_terms(message)
    mapping = [
        ("rehab_or_pain", ["dor", "lesao", "tendinite", "reabil", "retorno ao treino", "voltar a correr"]),
        ("meal_planning", ["dieta", "aliment", "cardapio", "refeicao", "cafe da manha", "jantar", "almoco", "lanche"]),
        (
            "training_plan",
            ["treino", "treinar", "musculacao", "exercicio", "workout", "plano", "plano de treino", "upper/lower", "academia"],
        ),
        ("routine_planning", ["rotina", "semana", "agenda", "dias por semana", "horarios"]),
        ("weight_loss", ["emagrec", "perder peso", "perder gordura", "secar", "cutting"]),
        ("muscle_gain", ["hipertrof", "ganhar massa", "ganhar musculo", "bulk", "crescer"]),
        ("performance", ["correr", "corrida", "performance", "maratona", "vo2", "condicionamento"]),
        ("maintenance", ["manter peso", "manutenc", "manter"]),
        ("general_health", ["saude", "saudavel", "saudável", "bem-estar", "bem estar"]),
    ]
    for goal, needles in mapping:
        if any(normalize_text(needle) in text for needle in needles):
            return goal
    return "unknown"


def infer_requested_domains(message: str) -> list[str]:
    text = normalize_text(message)
    risk_text = _without_negated_risk_terms(message)
    domains = []
    if any(tok in text for tok in ["dieta", "aliment", "cardapio", "refeicao", "proteina", "caloria"]):
        domains.append("nutrition")
    if any(tok in text for tok in ["treino", "treinar", "muscul", "exercicio", "corr", "corrida", "bike", "academia"]):
        domains.append("training")
    frequency_only = bool(re.search(r"\b\d+\s*(?:x|vezes|dias?)\s*(?:por semana|na semana|/semana)\b", text))
    if any(tok in text for tok in ["rotina", "agenda", "horario", "disponibilidade"]) or ("semana" in text and not frequency_only):
        domains.append("schedule")
    if contains_any(risk_text, MEDICAL_INTAKE_TERMS) or any(tok in risk_text for tok in ["seguro", "medicamente", "clinicamente"]):
        domains.append("medical")
    if any(tok in text for tok in ["habito", "aderencia", "consistencia", "check in", "check-in"]):
        domains.append("behavior")
    if any(tok in text for tok in ["peso", "medida", "gordura corporal", "progresso"]):
        domains.append("measurement")
    return sorted(set(domains))


def infer_risk_signals(message: str, profile: dict[str, Any]) -> list[str]:
    text = _without_negated_risk_terms(message)
    signals: list[str] = []
    if contains_any(text, MEDICAL_INTAKE_TERMS):
        signals.append("medical_keyword")
    if contains_any(text, AGGRESSIVE_GOAL_TERMS):
        signals.append("aggressive_goal")
    if any(tok in text for tok in ["dor no peito", "desmaio", "falta de ar", "perda de forca", "fraqueza", "dormencia", "febre"]):
        signals.append("red_flag")
    injuries = profile.get("injuries") or profile.get("pain") or []
    conditions = profile.get("conditions") or []
    medications = profile.get("medications") or []
    if injuries:
        signals.append("profile_injury")
    if conditions:
        signals.append("profile_condition")
    if medications:
        signals.append("profile_medication")
    return sorted(set(signals))
