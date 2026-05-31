from __future__ import annotations

import math
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from app.embedder import SPEAKER_MODEL, embedder
from app.transcriber import transcriber


def wav_duration_seconds(path: str | Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def detect_speech_regions(
    wav_path: str | Path,
    *,
    silence_db: float = -35.0,
    min_silence_s: float = 0.45,
    min_speech_s: float = 0.35,
) -> list[tuple[float, float]]:
    duration = wav_duration_seconds(wav_path)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(wav_path),
            "-af",
            f"silencedetect=noise={silence_db}dB:d={min_silence_s}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stderr or "") + (proc.stdout or "")
    silence_starts = [
        float(match.group(1))
        for match in re.finditer(r"silence_start:\s*([0-9.]+)", output)
    ]
    silence_ends = [
        float(match.group(1))
        for match in re.finditer(r"silence_end:\s*([0-9.]+)", output)
    ]

    speech_regions: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in zip(silence_starts, silence_ends):
        if start - cursor >= min_speech_s:
            speech_regions.append((cursor, start))
        cursor = end
    if duration - cursor >= min_speech_s:
        speech_regions.append((cursor, duration))
    if not speech_regions and duration >= min_speech_s:
        speech_regions.append((0.0, duration))
    return speech_regions


def extract_segment(wav_path: str | Path, start_s: float, end_s: float) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-ss",
            f"{start_s:.3f}",
            "-to",
            f"{end_s:.3f}",
            "-ac",
            "1",
            "-ar",
            "16000",
            tmp.name,
        ],
        check=True,
        capture_output=True,
    )
    return tmp.name


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _average_vector(left: list[float], right: list[float]) -> list[float]:
    return [(a + b) / 2 for a, b in zip(left, right)]


def assign_speakers(
    turns: list[dict[str, Any]],
    *,
    max_speakers: int = 2,
    threshold: float = 0.75,
) -> None:
    centroids: dict[str, list[float]] = {}
    for turn in turns:
        embedding = turn["embedding"]
        best_label = None
        best_score = -1.0
        for label, centroid in centroids.items():
            score = _cosine_similarity(embedding, centroid)
            if score > best_score:
                best_score = score
                best_label = label

        if best_label and best_score >= threshold:
            turn["speaker"] = best_label
            centroids[best_label] = _average_vector(centroids[best_label], embedding)
            continue

        if len(centroids) < max_speakers:
            label = f"Speaker {len(centroids) + 1}"
            centroids[label] = embedding
            turn["speaker"] = label
            continue

        turn["speaker"] = best_label or "Speaker 1"


def analyze_interaction(
    wav_path: str,
    *,
    max_speakers: int = 2,
) -> dict[str, Any]:
    import time

    started = time.perf_counter()
    transcriber.load_model()
    embedder.load_model()

    duration_s = round(wav_duration_seconds(wav_path), 2)
    regions = detect_speech_regions(wav_path)
    if not regions:
        raise ValueError("No speech detected in this recording.")

    turns: list[dict[str, Any]] = []
    segment_paths: list[str] = []
    try:
        for start_s, end_s in regions:
            segment_path = extract_segment(wav_path, start_s, end_s)
            segment_paths.append(segment_path)
            text, _meta = transcriber.transcribe(segment_path)
            text = text.strip()
            if not text:
                continue
            embedding = embedder.embed(segment_path)
            turns.append(
                {
                    "start_s": round(start_s, 2),
                    "end_s": round(end_s, 2),
                    "text": text,
                    "embedding_dims": len(embedding),
                }
            )
            turns[-1]["embedding"] = embedding
    finally:
        for segment_path in segment_paths:
            Path(segment_path).unlink(missing_ok=True)

    if not turns:
        raise ValueError("Speech was detected but no transcript was produced.")

    assign_speakers(turns, max_speakers=max_speakers)
    lines = [
        f"[{turn['start_s']:06.1f}s] {turn['speaker']}: {turn['text']}"
        for turn in turns
    ]
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    return {
        "duration_s": duration_s,
        "turn_count": len(turns),
        "diarized_transcript": "\n".join(lines),
        "turns": [
            {
                "start_s": turn["start_s"],
                "end_s": turn["end_s"],
                "speaker": turn["speaker"],
                "text": turn["text"],
            }
            for turn in turns
        ],
        "engine": {
            "asr_model": transcriber._model is not None,
            "speaker_model": SPEAKER_MODEL if embedder._loaded else None,
            "device": "cuda",
            "clustering": "titanet_cosine",
            "max_speakers": max_speakers,
        },
        "timings_ms": {"gpu_pipeline": elapsed_ms},
    }
