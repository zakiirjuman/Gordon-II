from __future__ import annotations

import tempfile
import time
import wave
from importlib.util import find_spec
from pathlib import Path

import httpx
from fastapi import UploadFile

from app.config import (
    ASR_BACKEND,
    NEMO_ASR_MODEL,
    NIM_ASR_MODEL,
    NIM_ASR_URL,
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


def nim_available() -> bool:
    try:
        response = httpx.get(f"{NIM_ASR_URL}/v1/health/ready", timeout=1.0)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


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


def _transcribe_with_nim(path: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as wav:
        _convert_to_wav(path, wav.name)
        duration = _wav_duration_seconds(wav.name)
        with open(wav.name, "rb") as audio:
            response = httpx.post(
                f"{NIM_ASR_URL}/v1/audio/transcriptions",
                files={"file": ("audio.wav", audio, "audio/wav")},
                data={"language": "en-US"},
                timeout=120.0,
            )
    response.raise_for_status()
    data = response.json()
    transcript = (
        data.get("text")
        or data.get("transcript")
        or data.get("transcription")
        or ""
    )
    if not transcript and isinstance(data.get("segments"), list):
        transcript = " ".join(
            str(segment.get("text", "")).strip()
            for segment in data["segments"]
            if isinstance(segment, dict)
        )

    _runtime.update(
        {
            "backend": "nim",
            "model": NIM_ASR_MODEL,
            "device": "cuda",
            "compute_type": "nim",
            "fallback": False,
            "audio_seconds": round(duration, 2),
        }
    )
    return str(transcript).strip()


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
    if ASR_BACKEND == "nim":
        return _transcribe_with_nim(path)
    if ASR_BACKEND == "nemo":
        return _transcribe_with_nemo(path)
    if ASR_BACKEND == "whisper":
        return _transcribe_with_whisper(path)

    fallback_reasons = []
    try:
        return _transcribe_with_nim(path)
    except Exception as exc:  # noqa: BLE001
        fallback_reasons.append(f"NIM unavailable: {type(exc).__name__}: {exc}")

    try:
        return _transcribe_with_nemo(path)
    except Exception as exc:  # noqa: BLE001
        fallback_reasons.append(f"NeMo unavailable: {type(exc).__name__}: {exc}")
        _runtime.update(
            {
                "backend": "whisper",
                "fallback": True,
                "fallback_reason": " | ".join(fallback_reasons),
            }
        )
        return _transcribe_with_whisper(path)


def transcribe_file(path: str) -> str:
    return _transcribe(path)


async def prepare_upload_wav(audio: UploadFile) -> tuple[str, str]:
    """Save upload to a temp wav file. Caller must delete both returned paths."""
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    payload = await audio.read()
    if not payload:
        raise ValueError("Audio upload was empty.")

    src = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        src.write(payload)
        src.flush()
        src.close()
        wav.close()
        _convert_to_wav(src.name, wav.name)
    except Exception:
        Path(src.name).unlink(missing_ok=True)
        Path(wav.name).unlink(missing_ok=True)
        raise
    finally:
        Path(src.name).unlink(missing_ok=True)
    return wav.name, suffix


async def transcribe_wav_file(wav_path: str) -> tuple[str, int]:
    started = time.perf_counter()
    transcript = _transcribe(wav_path)
    if not transcript:
        raise ValueError("No speech detected.")
    return transcript, round((time.perf_counter() - started) * 1000)


async def transcribe_upload(audio: UploadFile) -> tuple[str, int]:
    wav_path, _suffix = await prepare_upload_wav(audio)
    try:
        return await transcribe_wav_file(wav_path)
    finally:
        Path(wav_path).unlink(missing_ok=True)
