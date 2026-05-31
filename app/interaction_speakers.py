from __future__ import annotations

from typing import Any

from app.config import SPEAKER_CLUSTER_THRESHOLD
from app.officer import cosine_similarity, fingerprint_wav


def _average_fingerprint(left: list[float], right: list[float]) -> list[float]:
    return [(a + b) / 2 for a, b in zip(left, right)]


def assign_speaker_labels(
    turns: list[dict[str, Any]],
    *,
    max_speakers: int = 2,
    threshold: float = SPEAKER_CLUSTER_THRESHOLD,
) -> None:
    centroids: dict[str, list[float]] = {}

    for turn in turns:
        fingerprint = turn["fingerprint"]
        best_label: str | None = None
        best_score = -1.0
        for label, centroid in centroids.items():
            score = cosine_similarity(fingerprint, centroid)
            if score > best_score:
                best_score = score
                best_label = label

        if best_label and best_score >= threshold:
            turn["speaker"] = best_label
            centroids[best_label] = _average_fingerprint(centroids[best_label], fingerprint)
            continue

        if len(centroids) < max_speakers:
            label = f"Speaker {len(centroids) + 1}"
            centroids[label] = fingerprint
            turn["speaker"] = label
            continue

        turn["speaker"] = best_label or "Speaker 1"


def fingerprint_segment(wav_path: str) -> list[float]:
    return fingerprint_wav(wav_path)
