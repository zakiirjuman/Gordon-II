from __future__ import annotations

import json
import math
import struct
import time
import wave
from pathlib import Path
from typing import Any

from app.config import DATA_DIR, SPEAKER_MATCH_THRESHOLD

MAX_STARS_STORED = 50


def _profile_path(officer_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in officer_id.strip())
    if not safe:
        raise ValueError("Officer ID is required.")
    return DATA_DIR / f"{safe}.json"


def _load_profile(officer_id: str) -> dict[str, Any] | None:
    path = _profile_path(officer_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _profile_path(profile["officer_id"])
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def fingerprint_wav(path: str | Path, *, bins: int = 32) -> list[float]:
    """Lightweight voice fingerprint from mono PCM (not forensic speaker ID)."""
    with wave.open(str(path), "rb") as wf:
        sample_width = wf.getsampwidth()
        frame_count = wf.getnframes()
        sample_rate = wf.getframerate()
        raw = wf.readframes(frame_count)

    if sample_width != 2 or not raw:
        return [0.0] * (bins + 3)

    count = len(raw) // 2
    samples = struct.unpack(f"<{count}h", raw)
    floats = [sample / 32768.0 for sample in samples]
    duration_s = len(floats) / max(sample_rate, 1)

    rms = math.sqrt(sum(value * value for value in floats) / len(floats))
    signs = [1 if value >= 0 else -1 for value in floats]
    zcr = sum(1 for idx in range(1, len(signs)) if signs[idx] != signs[idx - 1]) / max(
        len(signs) - 1,
        1,
    )

    window = max(len(floats) // bins, 1)
    magnitudes: list[float] = []
    for idx in range(bins):
        chunk = floats[idx * window : (idx + 1) * window]
        if not chunk:
            magnitudes.append(0.0)
            continue
        energy = math.sqrt(sum(value * value for value in chunk) / len(chunk))
        magnitudes.append(energy)

    peak = max(magnitudes) or 1.0
    magnitudes = [value / peak for value in magnitudes]
    return [rms, zcr, duration_s, *magnitudes]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def enroll_officer(
    officer_id: str,
    *,
    wav_path: str | Path,
    display_name: str | None = None,
) -> dict[str, Any]:
    profile = _load_profile(officer_id) or {
        "officer_id": officer_id.strip(),
        "display_name": display_name or officer_id.strip(),
        "stars": [],
        "star_count": 0,
    }
    if display_name:
        profile["display_name"] = display_name.strip()
    profile["voice_fingerprint"] = fingerprint_wav(wav_path)
    profile["enrolled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return _save_profile(profile)


def match_officer_voice(officer_id: str, wav_path: str | Path) -> dict[str, Any]:
    profile = _load_profile(officer_id)
    probe = fingerprint_wav(wav_path)
    if not profile or not profile.get("voice_fingerprint"):
        return {
            "enrolled": False,
            "matched": True,
            "score": None,
            "note": "No enrollment yet; stars attach to this device officer ID.",
        }

    score = cosine_similarity(profile["voice_fingerprint"], probe)
    return {
        "enrolled": True,
        "matched": score >= SPEAKER_MATCH_THRESHOLD,
        "score": round(score, 3),
        "threshold": SPEAKER_MATCH_THRESHOLD,
    }


def award_star(
    officer_id: str,
    *,
    message: str,
    transcript: str,
) -> dict[str, Any]:
    profile = _load_profile(officer_id) or {
        "officer_id": officer_id.strip(),
        "display_name": officer_id.strip(),
        "stars": [],
        "star_count": 0,
    }
    entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": message,
        "transcript": transcript[:220],
    }
    profile.setdefault("stars", [])
    profile["stars"].insert(0, entry)
    profile["stars"] = profile["stars"][:MAX_STARS_STORED]
    profile["star_count"] = len(profile["stars"])
    saved = _save_profile(profile)
    return {
        "officer_id": saved["officer_id"],
        "display_name": saved.get("display_name"),
        "star_count": saved["star_count"],
        "latest": entry,
    }


def get_officer_profile(officer_id: str) -> dict[str, Any]:
    profile = _load_profile(officer_id)
    if not profile:
        return {
            "officer_id": officer_id.strip(),
            "enrolled": False,
            "star_count": 0,
            "stars": [],
        }
    return {
        "officer_id": profile["officer_id"],
        "display_name": profile.get("display_name"),
        "enrolled": bool(profile.get("voice_fingerprint")),
        "enrolled_at": profile.get("enrolled_at"),
        "star_count": profile.get("star_count", len(profile.get("stars", []))),
        "stars": profile.get("stars", [])[:10],
    }
