from __future__ import annotations

from plugins.journeyfit_orchestrator.storage import (
    get_current_plan,
    get_latest_workout_plan,
    get_plan_status,
    get_workout_plan,
    save_workout_plan,
)


def test_save_and_get_workout_plan():
    plan = {
        "status": "plan_ready",
        "mode": "plan_ready",
        "training": {
            "status": "provisional",
            "sessions": [{"id": "day-1", "exercises": [{"name": "Supino reto"}]}],
        },
    }

    stored = save_workout_plan(
        plan=plan,
        source_message="quero treinar 3x por semana",
        user_id="user-1",
        session_id="session-1",
        trace_id="trace-1",
    )
    record = get_workout_plan(stored.plan_id)

    assert record is not None
    assert record["id"] == stored.plan_id
    assert record["version"] == 1
    assert record["user_id"] == "user-1"
    assert record["session_id"] == "session-1"
    assert record["trace_id"] == "trace-1"
    assert record["source_message"] == "quero treinar 3x por semana"
    assert record["plan"]["workout_plan_id"] == stored.plan_id
    assert record["plan"]["plan_version"] == 1
    assert record["plan"]["training"]["sessions"][0]["exercises"][0]["name"] == "Supino reto"


def test_get_latest_workout_plan_prefers_newest_record():
    older = save_workout_plan(
        plan={"status": "plan_ready", "mode": "plan_ready", "training": {"status": "provisional", "sessions": []}},
        source_message="older",
        user_id="user-latest",
    )
    newer = save_workout_plan(
        plan={"status": "plan_ready", "mode": "plan_ready", "training": {"status": "provisional", "sessions": []}},
        source_message="newer",
        user_id="user-latest",
    )

    latest = get_latest_workout_plan(user_id="user-latest")

    assert latest is not None
    assert latest["id"] == newer.plan_id
    assert latest["id"] != older.plan_id
    assert latest["source_message"] == "newer"


def test_get_plan_status_reports_training_and_nutrition_domains():
    stored = save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "sessions": [{"id": "day-1", "exercises": [{"name": "Supino reto"}]}],
            },
            "nutrition": {
                "status": "provisional",
                "kcal": {"min": 2200, "max": 2400},
                "meal_examples": {"breakfast": ["Ovos com aveia"]},
            },
        },
        source_message="treino e dieta",
        user_id="user-status-domains",
    )

    status = get_plan_status(user_id="user-status-domains")

    assert status["has_any_plan"] is True
    assert status["has_training_plan"] is True
    assert status["has_nutrition_plan"] is True
    assert status["latest_plan"]["id"] == stored.plan_id


def test_get_plan_status_prefers_user_id_and_falls_back_to_session_id():
    stored = save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "sessions": [{"id": "day-1", "exercises": [{"name": "Agachamento"}]}],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino salvo",
        user_id="user-status-preferred",
        session_id="session-status-fallback",
    )

    by_user = get_plan_status(user_id="user-status-preferred", session_id="new-session")
    by_session = get_plan_status(session_id="session-status-fallback")

    assert by_user["latest_plan"]["id"] == stored.plan_id
    assert by_session["latest_plan"]["id"] == stored.plan_id
    assert by_user["has_training_plan"] is True
    assert by_user["has_nutrition_plan"] is False


def test_plan_lookup_without_user_falls_back_to_latest_local_plan():
    stored = save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "sessions": [{"id": "day-1", "exercises": [{"name": "Remada"}]}],
            },
            "nutrition": {"status": "unavailable"},
        },
        source_message="treino salvo em outro chat",
        session_id="api-plan-session",
    )

    status = get_plan_status(session_id="api-chat-ola")
    current = get_current_plan(domain="training", session_id="api-chat-ola")

    assert status["has_training_plan"] is True
    assert status["latest_plan"]["id"] == stored.plan_id
    assert current is not None
    assert current["plan_id"] == stored.plan_id
    assert current["training"]["sessions"][0]["exercises"][0]["name"] == "Remada"


def test_get_current_plan_returns_requested_domain_only():
    stored = save_workout_plan(
        plan={
            "status": "plan_ready",
            "mode": "plan_ready",
            "training": {
                "status": "provisional",
                "sessions": [{"id": "day-1", "exercises": [{"name": "Remada"}]}],
            },
            "nutrition": {
                "status": "provisional",
                "kcal": {"min": 2100, "max": 2300},
                "meal_examples": {"breakfast": ["Iogurte com fruta"]},
            },
        },
        source_message="plano completo",
        user_id="user-current-domain",
    )

    training = get_current_plan(domain="training", user_id="user-current-domain")
    nutrition = get_current_plan(domain="nutrition", user_id="user-current-domain")

    assert training is not None
    assert training["plan_id"] == stored.plan_id
    assert "training" in training
    assert "nutrition" not in training
    assert training["training"]["sessions"][0]["exercises"][0]["name"] == "Remada"
    assert nutrition is not None
    assert nutrition["plan_id"] == stored.plan_id
    assert "nutrition" in nutrition
    assert "training" not in nutrition
    assert nutrition["nutrition"]["kcal"] == {"min": 2100, "max": 2300}
