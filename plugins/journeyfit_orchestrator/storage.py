"""SQLite persistence for JourneyFit plans."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home


@dataclass(frozen=True)
class StoredWorkoutPlan:
    plan_id: str
    version: int
    db_path: Path


def _db_path() -> Path:
    return get_hermes_home() / "journeyfit.db"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workout_plans (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            session_id TEXT,
            trace_id TEXT,
            source_message TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            status TEXT NOT NULL,
            mode TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workout_plans_user_updated
        ON workout_plans(user_id, updated_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workout_plans_session_updated
        ON workout_plans(session_id, updated_at DESC)
        """
    )


def save_workout_plan(
    *,
    plan: dict[str, Any],
    source_message: str,
    user_id: str | None = None,
    session_id: str | None = None,
    trace_id: str | None = None,
) -> StoredWorkoutPlan:
    plan_id = f"wplan_{uuid.uuid4().hex}"
    version = 1
    now = time.time()
    status = str(plan.get("status") or plan.get("training", {}).get("status") or "plan_ready")
    mode = str(plan.get("mode") or "plan_ready")
    plan["workout_plan_id"] = plan_id
    plan["plan_version"] = version
    plan_json = json.dumps(plan, ensure_ascii=False, sort_keys=True)

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO workout_plans (
                id, user_id, session_id, trace_id, source_message, plan_json,
                status, mode, version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                user_id or None,
                session_id or None,
                trace_id or None,
                source_message,
                plan_json,
                status,
                mode,
                version,
                now,
                now,
            ),
        )
    return StoredWorkoutPlan(plan_id=plan_id, version=version, db_path=_db_path())


def get_workout_plan(plan_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, user_id, session_id, trace_id, source_message, plan_json, status, mode, version, created_at, updated_at "
            "FROM workout_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
    if row is None:
        return None
    keys = [
        "id",
        "user_id",
        "session_id",
        "trace_id",
        "source_message",
        "plan_json",
        "status",
        "mode",
        "version",
        "created_at",
        "updated_at",
    ]
    record = dict(zip(keys, row, strict=True))
    record["plan"] = json.loads(str(record.pop("plan_json")))
    return record


def get_latest_workout_plan(*, user_id: str | None = None, session_id: str | None = None) -> dict[str, Any] | None:
    where: list[str] = []
    params: list[Any] = []
    if user_id:
        where.append("user_id = ?")
        params.append(user_id)
    if session_id:
        where.append("session_id = ?")
        params.append(session_id)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM workout_plans "
            f"{where_sql} "
            "ORDER BY updated_at DESC LIMIT 1",
            params,
        ).fetchone()
    if row is None:
        return None
    return get_workout_plan(str(row[0]))


def _has_training(plan: dict[str, Any]) -> bool:
    training = plan.get("training")
    if not isinstance(training, dict):
        return False
    status = str(training.get("status") or "").strip().lower()
    if status in {"", "unavailable", "none", "null"}:
        return False
    sessions = training.get("sessions")
    return bool(sessions) or status not in {"unavailable"}


def _has_nutrition(plan: dict[str, Any]) -> bool:
    nutrition = plan.get("nutrition")
    if not isinstance(nutrition, dict):
        return False
    status = str(nutrition.get("status") or "").strip().lower()
    if status in {"", "unavailable", "none", "null"}:
        return False
    meal_examples = nutrition.get("meal_examples")
    if isinstance(meal_examples, dict) and any(bool(items) for items in meal_examples.values() if isinstance(items, list)):
        return True
    kcal = nutrition.get("kcal")
    if isinstance(kcal, dict) and any(value not in (None, "", 0) for value in kcal.values()):
        return True
    return status not in {"unavailable"}


def get_plan_status(*, user_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
    """Return whether the current user/session already has JourneyFit plans."""
    record = get_latest_workout_plan(user_id=user_id) if user_id else None
    if record is None and session_id:
        record = get_latest_workout_plan(session_id=session_id)
    if record is None and not user_id:
        record = get_latest_workout_plan()
    if record is None:
        return {
            "has_any_plan": False,
            "has_training_plan": False,
            "has_nutrition_plan": False,
            "latest_plan": None,
        }

    plan = record.get("plan") if isinstance(record.get("plan"), dict) else {}
    has_training = _has_training(plan)
    has_nutrition = _has_nutrition(plan)
    return {
        "has_any_plan": has_training or has_nutrition,
        "has_training_plan": has_training,
        "has_nutrition_plan": has_nutrition,
        "latest_plan": {
            "id": record.get("id"),
            "version": record.get("version"),
            "status": record.get("status"),
            "mode": record.get("mode"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        },
    }


def get_current_plan(
    *,
    domain: str = "both",
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the latest saved plan, optionally narrowed to training/nutrition."""
    record = get_latest_workout_plan(user_id=user_id) if user_id else None
    if record is None and session_id:
        record = get_latest_workout_plan(session_id=session_id)
    if record is None and not user_id:
        record = get_latest_workout_plan()
    if record is None:
        return None

    plan = record.get("plan") if isinstance(record.get("plan"), dict) else {}
    requested = (domain or "both").strip().lower()
    if requested not in {"training", "nutrition", "both"}:
        requested = "both"

    payload: dict[str, Any] = {
        "plan_id": record.get("id"),
        "plan_version": record.get("version"),
        "status": record.get("status"),
        "mode": record.get("mode"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }
    if requested in {"training", "both"}:
        payload["training"] = plan.get("training")
    if requested in {"nutrition", "both"}:
        payload["nutrition"] = plan.get("nutrition")
    return payload
