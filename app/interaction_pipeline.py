from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from app.interaction_audio import detect_speech_regions, extract_segment, wav_duration_seconds
from app.interaction_gpu import (
    GpuInteractionError,
    analyze_on_gpu,
    gpu_interaction_available,
)
from app.interaction_speakers import assign_speaker_labels, fingerprint_segment
from app.interaction_store import save_session
from app.llm import evaluate_interaction
from app.officer import award_star
from app.voice import _convert_to_wav, transcribe_file


def _format_diarized_transcript(turns: list[dict[str, Any]]) -> str:
    lines = []
    for turn in turns:
        start = turn.get("start_s", 0.0)
        speaker = turn.get("speaker", "Speaker ?")
        text = turn.get("text", "").strip()
        if not text:
            continue
        lines.append(f"[{start:06.1f}s] {speaker}: {text}")
    return "\n".join(lines)


def _officer_turns(turns: list[dict[str, Any]], officer_speaker: str) -> list[dict[str, Any]]:
    return [turn for turn in turns if turn.get("speaker") == officer_speaker and turn.get("text")]


def _build_turns_cpu(wav_path: str) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
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
            text = transcribe_file(segment_path).strip()
            if not text:
                continue
            turns.append(
                {
                    "start_s": round(start_s, 2),
                    "end_s": round(end_s, 2),
                    "text": text,
                    "fingerprint": fingerprint_segment(segment_path),
                }
            )
    finally:
        for segment_path in segment_paths:
            Path(segment_path).unlink(missing_ok=True)

    if not turns:
        raise ValueError("Speech was detected but no transcript was produced.")

    assign_speaker_labels(turns)
    engine = {"clustering": "cpu_fingerprint", "device": "cpu"}
    return duration_s, turns, engine


def _build_turns_gpu(wav_path: str) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
    result = analyze_on_gpu(wav_path)
    turns = result.get("turns") or []
    if not turns:
        raise ValueError("GPU interaction pipeline returned no turns.")
    engine = result.get("engine") or {"clustering": "titanet_cosine", "device": "cuda"}
    timings = result.get("timings_ms") or {}
    engine["gpu_pipeline_ms"] = timings.get("gpu_pipeline")
    return float(result.get("duration_s") or 0), turns, engine


def _build_turns_with_engine(
    wav_path: str,
) -> tuple[float, list[dict[str, Any]], dict[str, Any]]:
    if gpu_interaction_available():
        try:
            return _build_turns_gpu(wav_path)
        except (GpuInteractionError, httpx.HTTPStatusError) as exc:
            logger.warning("GPU interaction analyze unavailable, using CPU fallback: %s", exc)
            duration_s, turns, engine = _build_turns_cpu(wav_path)
            engine["gpu_fallback"] = True
            engine["gpu_fallback_reason"] = str(exc)
            return duration_s, turns, engine
    return _build_turns_cpu(wav_path)


def _prepare_wav(source_path: str) -> tuple[str, bool]:
    if source_path.lower().endswith(".wav"):
        return source_path, False
    tmp = f"{source_path}.converted.wav"
    _convert_to_wav(source_path, tmp)
    return tmp, True


async def process_interaction_recording(
    source_path: str,
    *,
    officer_id: str = "device-officer",
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    import asyncio

    started = time.perf_counter()
    wav_path, cleanup_wav = _prepare_wav(source_path)
    try:
        duration_s, turns, engine = await asyncio.to_thread(_build_turns_with_engine, wav_path)

        diarized = _format_diarized_transcript(turns)
        evaluation = await evaluate_interaction(diarized, snapshot)

        star_record = None
        if evaluation.get("star_awarded"):
            officer_speaker = evaluation.get("officer_speaker") or "Speaker 1"
            officer_lines = _officer_turns(turns, officer_speaker)
            officer_transcript = "\n".join(
                f"[{turn['start_s']}s] {turn['text']}" for turn in officer_lines
            )
            star_record = award_star(
                officer_id,
                message=evaluation.get("star_message") or "Strong interaction.",
                transcript=officer_transcript or diarized[:500],
            )

        elapsed_ms = round((time.perf_counter() - started) * 1000)
        payload = {
            "duration_s": duration_s,
            "turn_count": len(turns),
            "diarized_transcript": diarized,
            "turns": turns,
            "evaluation": evaluation,
            "star": star_record,
            "officer_id": officer_id,
            "diarization_engine": engine,
            "timings_ms": {"total": elapsed_ms, **(engine if isinstance(engine, dict) else {})},
        }
        return save_session(payload)
    finally:
        if cleanup_wav:
            Path(wav_path).unlink(missing_ok=True)
