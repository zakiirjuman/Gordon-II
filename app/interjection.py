from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.config import MOCK_BACKUP_ETA_MINUTES

DANGER_TERMS = {
    "agitated",
    "angry",
    "backup",
    "crowd",
    "fight",
    "force",
    "knife",
    "resisting",
    "screaming",
    "subject",
    "weapon",
}

PRAISE_TERMS = {
    "articulable grounds",
    "clear grounds",
    "de-escalate",
    "distance",
    "document",
    "explain",
    "right to counsel",
    "slow down",
}


@dataclass(frozen=True)
class Interjection:
    level: str
    stress_score: int
    backup_eta_minutes: int | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_situation(
    question: str,
    snapshot: dict[str, Any],
) -> Interjection:
    text = question.lower()
    stress_score = 0
    stress_score += sum(1 for term in DANGER_TERMS if term in text) * 2
    stress_score += min(question.count("?"), 3)
    stress_score += 2 if question.isupper() and len(question) > 12 else 0

    counts = snapshot.get("counts") or {}
    if counts.get("active_road_restrictions", 0) > 0:
        stress_score += 1
    if counts.get("construction_hubs", 0) > 0:
        stress_score += 1

    if "backup" in text or stress_score >= 5:
        return Interjection(
            level="danger",
            stress_score=stress_score,
            backup_eta_minutes=MOCK_BACKUP_ETA_MINUTES,
            message=f"Nearest backup estimate: {MOCK_BACKUP_ETA_MINUTES} min. Slow the sequence down.",
        )

    if any(term in text for term in PRAISE_TERMS):
        return Interjection(
            level="praise",
            stress_score=stress_score,
            message="Clear, accountable framing. Star earned.",
        )

    return Interjection(level="silent", stress_score=stress_score)


def prompt_overlay(interjection: Interjection | None) -> str:
    if not interjection or interjection.level != "danger":
        return ""
    backup = (
        f"Backup estimate: {interjection.backup_eta_minutes} minutes.\n"
        if interjection.backup_eta_minutes is not None
        else ""
    )
    return (
        "\nELEVATED-STRESS RESPONSE MODE:\n"
        f"{backup}"
        "- Start with immediate safety sequencing; do not sound alarmist.\n"
        "- If backup is far, surface that first and recommend time, distance, cover, and containment when safe.\n"
        "- Keep the officer calm, confident, and in control.\n"
        "- Reinforce lawful grounds, documentation, and explicit do-not boundaries.\n"
    )
