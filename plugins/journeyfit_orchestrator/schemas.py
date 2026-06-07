"""JSON schemas for JourneyFit tool and specialist calls."""

from __future__ import annotations

from typing import Any, Dict


JOURNEYFIT_ORCHESTRATE_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit_orchestrate",
    "description": "Run the JourneyFit orchestration flow and return a JSON result.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_message": {"type": "string", "description": "Texto do pedido original do usuario."},
            "user_profile": {"type": "object", "description": "Perfil estruturado do usuario."},
            "conversation_history": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Historico curto da conversa.",
            },
            "profile_name": {
                "type": "string",
                "description": "Perfil Hermes ativo, se conhecido.",
            },
        },
        "required": ["user_message"],
        "additionalProperties": False,
    },
}


JOURNEYFIT_PLAN_STATUS_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit_plan_status",
    "description": (
        "Check whether the current JourneyFit user/session already has a saved training or nutrition plan. "
        "Use before suggesting creation of a new workout or diet plan."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_profile": {"type": "object", "description": "Perfil estruturado do usuario, se conhecido."},
            "user_id": {"type": "string", "description": "ID explicito do usuario, se conhecido."},
            "session_id": {"type": "string", "description": "ID explicito da sessao, se conhecido."},
        },
        "additionalProperties": False,
    },
}


JOURNEYFIT_CURRENT_PLAN_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit_current_plan",
    "description": (
        "Read the current saved JourneyFit plan for a specialist. "
        "Personal trainer should request domain='training'; nutritionist should request domain='nutrition'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": ["training", "nutrition", "both"],
                "description": "Which part of the saved plan to read.",
            },
            "user_profile": {"type": "object", "description": "Perfil estruturado do usuario, se conhecido."},
            "user_id": {"type": "string", "description": "ID explicito do usuario, se conhecido."},
            "session_id": {"type": "string", "description": "ID explicito da sessao, se conhecido."},
        },
        "required": ["domain"],
        "additionalProperties": False,
    },
}


_LIST_STRING_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {"type": "string"},
}

_LIST_OBJECT_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {"type": "object"},
}

MEDICAL_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.medical",
    "type": "object",
    "properties": {
        "mode": {"type": "string"},
        "risk_level": {"type": "string"},
        "red_flags": _LIST_STRING_SCHEMA,
        "requires_professional_review": {"type": "boolean"},
        "allowed_scope": {"type": "string"},
        "constraints_for_other_agents": _LIST_STRING_SCHEMA,
        "validation_target": {"type": ["string", "null"]},
        "validation_status": {"type": "string"},
        "revision_requests": _LIST_OBJECT_SCHEMA,
        "user_questions_needed": _LIST_STRING_SCHEMA,
        "summary": {"type": "string"},
        "missing_information": _LIST_STRING_SCHEMA,
    },
    "required": ["mode", "risk_level", "red_flags", "requires_professional_review", "allowed_scope", "constraints_for_other_agents", "validation_target", "validation_status", "revision_requests", "user_questions_needed"],
    "additionalProperties": True,
}

NUTRITION_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.nutrition",
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "assumptions": _LIST_STRING_SCHEMA,
        "nutrition_strategy": {"type": "object"},
        "meal_structure": _LIST_OBJECT_SCHEMA,
        "constraints_respected": _LIST_STRING_SCHEMA,
        "warnings": _LIST_STRING_SCHEMA,
        "questions": _LIST_STRING_SCHEMA,
    },
    "required": ["summary", "assumptions", "nutrition_strategy", "meal_structure", "constraints_respected", "warnings", "questions"],
    "additionalProperties": True,
}

TRAINING_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.training",
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "assumptions": _LIST_STRING_SCHEMA,
        "weekly_training_plan": _LIST_OBJECT_SCHEMA,
        "progression": {"type": "object"},
        "constraints_respected": _LIST_STRING_SCHEMA,
        "warnings": _LIST_STRING_SCHEMA,
        "questions": _LIST_STRING_SCHEMA,
    },
    "required": ["summary", "assumptions", "weekly_training_plan", "progression", "constraints_respected", "warnings", "questions"],
    "additionalProperties": True,
}

TRAINING_CONVERSATION_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.training_conversation",
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "referenced_plan": {"type": "object"},
        "safety_notes": _LIST_STRING_SCHEMA,
        "follow_up_questions": _LIST_STRING_SCHEMA,
        "warnings": _LIST_STRING_SCHEMA,
    },
    "required": ["answer", "referenced_plan", "safety_notes", "follow_up_questions", "warnings"],
    "additionalProperties": True,
}

SCHEDULE_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.schedule",
    "type": "object",
    "properties": {
        "weekly_schedule": _LIST_OBJECT_SCHEMA,
        "routine_notes": _LIST_STRING_SCHEMA,
        "tradeoffs": _LIST_STRING_SCHEMA,
        "missing_inputs": _LIST_STRING_SCHEMA,
    },
    "required": ["weekly_schedule", "routine_notes", "tradeoffs", "missing_inputs"],
    "additionalProperties": True,
}

REVIEWER_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.reviewer",
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "issues": _LIST_OBJECT_SCHEMA,
        "revision_requests": _LIST_OBJECT_SCHEMA,
    },
    "required": ["approved", "issues", "revision_requests"],
    "additionalProperties": True,
}

SYNTHESIZER_SCHEMA: Dict[str, Any] = {
    "name": "journeyfit.synthesizer",
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "sections": _LIST_OBJECT_SCHEMA,
        "safety_notes": _LIST_STRING_SCHEMA,
        "follow_up_questions": _LIST_STRING_SCHEMA,
        "trace_summary": {"type": "object"},
    },
    "required": ["answer", "sections", "safety_notes", "follow_up_questions", "trace_summary"],
    "additionalProperties": True,
}


SPECIALIST_SCHEMAS: Dict[tuple[str, str], Dict[str, Any]] = {
    ("doctor", "intake"): MEDICAL_SCHEMA,
    ("doctor", "validation"): MEDICAL_SCHEMA,
    ("nutritionist", "domain_plan"): NUTRITION_SCHEMA,
    ("nutritionist", "revision"): NUTRITION_SCHEMA,
    ("personal_trainer", "domain_plan"): TRAINING_SCHEMA,
    ("personal_trainer", "existing_plan_conversation"): TRAINING_CONVERSATION_SCHEMA,
    ("personal_trainer", "revision"): TRAINING_SCHEMA,
    ("scheduler", "schedule"): SCHEDULE_SCHEMA,
    ("reviewer", "review"): REVIEWER_SCHEMA,
    ("synthesizer", "synthesis"): SYNTHESIZER_SCHEMA,
}
