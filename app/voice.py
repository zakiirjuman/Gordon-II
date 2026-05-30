from __future__ import annotations

import tempfile
import time
from importlib.util import find_spec
from pathlib import Path

from fastapi import UploadFile

from app.config import (
    WHISPER_COMPUTE_TYPE,
    WHISPER_CPU_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL,
)

_model = None
_runtime = {
    "device": WHISPER_DEVICE,
    "compute_type": WHISPER_COMPUTE_TYPE,
    "fallback": False,
}


def whisper_available() -> bool:
    return find_spec("faster_whisper") is not None


def whisper_runtime() -> dict[str, object]:
    return dict(_runtime)


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Voice support requires faster-whisper. Install the Spark extras before using /api/voice/ask."
        ) from exc

    try:
        _model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "CUDA" not in message.upper():
            raise
        _runtime.update(
            {
                "device": "cpu",
                "compute_type": WHISPER_CPU_COMPUTE_TYPE,
                "fallback": True,
                "reason": message,
            }
        )
        _model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type=WHISPER_CPU_COMPUTE_TYPE,
        )
    return _model


async def transcribe_upload(audio: UploadFile) -> tuple[str, int]:
    started = time.perf_counter()
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    payload = await audio.read()
    if not payload:
        raise ValueError("Audio upload was empty.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(payload)
        tmp.flush()
        model = _load_model()
        segments, _info = model.transcribe(
            tmp.name,
            beam_size=1,
            language="en",
            vad_filter=True,
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()

    if not transcript:
        raise ValueError("No speech detected.")

    return transcript, round((time.perf_counter() - started) * 1000)
