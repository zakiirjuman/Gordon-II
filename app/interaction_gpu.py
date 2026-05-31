from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.config import NIM_ASR_URL
from app.voice import _convert_to_wav, nim_available

logger = logging.getLogger(__name__)


class GpuInteractionError(Exception):
    """Raised when the Parakeet GPU interaction endpoint fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def gpu_interaction_available() -> bool:
    if not nim_available():
        return False
    try:
        response = httpx.get(f"{NIM_ASR_URL}/health", timeout=2.0)
        data = response.json()
        return bool(data.get("speaker_model"))
    except Exception:  # noqa: BLE001
        return False


def analyze_on_gpu(source_path: str, *, max_speakers: int = 2) -> dict:
    wav_path = source_path
    cleanup = False
    if not source_path.lower().endswith(".wav"):
        wav_path = f"{source_path}.gpu.wav"
        _convert_to_wav(source_path, wav_path)
        cleanup = True

    try:
        with open(wav_path, "rb") as audio:
            response = httpx.post(
                f"{NIM_ASR_URL}/v1/interaction/analyze",
                files={"file": ("interaction.wav", audio, "audio/wav")},
                data={"max_speakers": str(max_speakers)},
                timeout=600.0,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:300]
            logger.warning(
                "GPU interaction analyze failed (%s): %s",
                status,
                detail,
            )
            if status >= 500 or status in {502, 503, 504}:
                raise GpuInteractionError(
                    f"Parakeet analyze returned HTTP {status}",
                    status_code=status,
                ) from exc
            raise
        return response.json()
    except httpx.RequestError as exc:
        logger.warning("GPU interaction analyze request failed: %s", exc)
        raise GpuInteractionError(f"Parakeet analyze unreachable: {exc}") from exc
    finally:
        if cleanup:
            Path(wav_path).unlink(missing_ok=True)
