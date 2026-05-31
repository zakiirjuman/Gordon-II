from __future__ import annotations

from app.config import VOICE_WAKE_TERMS

QUESTION_STARTERS = (
    "what ",
    "how ",
    "when ",
    "where ",
    "why ",
    "should ",
    "can ",
    "do ",
    "is ",
    "are ",
)


def is_gordon_query(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if not normalized or len(normalized) < 8:
        return False
    if "?" in normalized:
        return True
    if any(term in normalized for term in VOICE_WAKE_TERMS):
        return True
    return normalized.startswith(QUESTION_STARTERS)
