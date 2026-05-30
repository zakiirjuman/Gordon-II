from __future__ import annotations

import tempfile
import time
import wave
from importlib.util import find_spec
from pathlib import Path

from fastapi import UploadFile

from app.config import (
    ASR_BACKEND,
    NEMO_ASR_MODEL,
    WHISPER_COMPUTE_TYPE,
    WHISPER_CPU_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL,
)

_nemo_model = None
_whisper_model = None
_runtime: dict[str, object] = {
    "backend": "unloaded",
    "model": None,
    "device": None,
    "compute_type": None,
    "fallback": False,
}


def whisper_available() -> bool:
    return find_spec("faster_whisper") is not None


def nemo_available() -> bool:
    return find_spec("nemo") is not None and find_spec("torch") is not None


def asr_runtime() -> dict[str, object]:
    return dict(_runtime)


def _load_nemo_model():
    global _nemo_model
    if _nemo_model is not None:
        return _nemo_model

    try:
        import torch
        import nemo.collections.asr as nemo_asr
    except ImportError as exc:
        raise RuntimeError("NeMo ASR dependencies are not installed.") from exc

    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch CUDA is not available for NeMo ASR.")

    _nemo_model = nemo_asr.models.ASRModel.from_pretrained(NEMO_ASR_MODEL)
    _nemo_model = _nemo_model.to("cuda")
    _nemo_model.eval()
    _runtime.update(
        {
            "backend": "nemo",
            "model": NEMO_ASR_MODEL,
            "device": "cuda",
            "compute_type": "torch",
            "fallback": False,
        }
    )
    return _nemo_model


def _load_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Voice support requires faster-whisper. Install the Spark extras before using /api/voice/ask."
        ) from exc

    try:
        _whisper_model = WhisperModel(
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
                "backend": "whisper",
                "model": WHISPER_MODEL,
                "fallback": True,
                "reason": message,
            }
        )
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type=WHISPER_CPU_COMPUTE_TYPE,
        )
    else:
        _runtime.update(
            {
                "backend": "whisper",
                "model": WHISPER_MODEL,
                "device": WHISPER_DEVICE,
                "compute_type": WHISPER_COMPUTE_TYPE,
                "fallback": ASR_BACKEND == "auto",
            }
        )
    return _whisper_model


def _convert_to_wav(src: str, dst: str) -> None:
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-ac",
            "1",
            "-ar",
            "16000",
            dst,
        ],
        check=True,
        capture_output=True,
    )


def _wav_duration_seconds(path: str) -> float:
    with wave.open(path) as wav:
        return wav.getnframes() / float(wav.getframerate())


def _transcribe_with_nemo(path: str) -> str:
    model = _load_nemo_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as wav:
        _convert_to_wav(path, wav.name)
        duration = _wav_duration_seconds(wav.name)
        output = model.transcribe([wav.name], batch_size=1)

    if not output:
        return ""
    first = output[0]
    if isinstance(first, str):
        transcript = first
    elif hasattr(first, "text"):
        transcript = first.text
    else:
        transcript = str(first)

    _runtime["audio_seconds"] = round(duration, 2)
    return transcript.strip()


def _transcribe_with_whisper(path: str) -> str:
    model = _load_whisper_model()
    segments, _info = model.transcribe(
        path,
        beam_size=1,
        language="en",
        vad_filter=True,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def _transcribe(path: str) -> str:
    if ASR_BACKEND == "nemo":
        return _transcribe_with_nemo(path)
    if ASR_BACKEND == "whisper":
        return _transcribe_with_whisper(path)

    try:
        return _transcribe_with_nemo(path)
    except Exception as exc:  # noqa: BLE001
        _runtime.update(
            {
                "backend": "whisper",
                "fallback": True,
                "fallback_reason": f"NeMo unavailable: {type(exc).__name__}: {exc}",
            }
        )
        return _transcribe_with_whisper(path)


async def transcribe_upload(audio: UploadFile) -> tuple[str, int]:
    started = time.perf_counter()
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    payload = await audio.read()
    if not payload:
        raise ValueError("Audio upload was empty.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(payload)
        tmp.flush()
        transcript = _transcribe(tmp.name)

    if not transcript:
        raise ValueError("No speech detected.")

    return transcript, round((time.perf_counter() - started) * 1000)
