from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import INTERACTIONS_DIR

MAX_SESSIONS = 100


def _session_path(session_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in session_id)
    return INTERACTIONS_DIR / f"{safe}.json"


def save_session(payload: dict[str, Any]) -> dict[str, Any]:
    INTERACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_id = payload.get("session_id") or uuid.uuid4().hex[:12]
    payload = {
        **payload,
        "session_id": session_id,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _session_path(session_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _trim_old_sessions()
    return payload


def list_sessions(*, limit: int = 20) -> list[dict[str, Any]]:
    if not INTERACTIONS_DIR.exists():
        return []
    files = sorted(
        INTERACTIONS_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    sessions: list[dict[str, Any]] = []
    for path in files[:limit]:
        data = json.loads(path.read_text(encoding="utf-8"))
        sessions.append(
            {
                "session_id": data.get("session_id"),
                "saved_at": data.get("saved_at"),
                "duration_s": data.get("duration_s"),
                "turn_count": data.get("turn_count"),
                "star_awarded": data.get("evaluation", {}).get("star_awarded"),
                "officer_speaker": data.get("evaluation", {}).get("officer_speaker"),
            }
        )
    return sessions


def get_session(session_id: str) -> dict[str, Any] | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _trim_old_sessions() -> None:
    files = sorted(
        INTERACTIONS_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files[MAX_SESSIONS:]:
        path.unlink(missing_ok=True)
