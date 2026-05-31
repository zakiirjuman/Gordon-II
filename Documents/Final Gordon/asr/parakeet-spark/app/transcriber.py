from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

import torch

MODEL_NAME = os.environ.get("PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v3")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class ParakeetTranscriber:
    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._load_ms: int | None = None

    def load_model(self) -> None:
        if self._loaded:
            return
        import nemo.collections.asr as nemo_asr

        started = time.perf_counter()
        model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME)
        model = model.to(DEVICE)
        model.eval()
        self._model = model
        self._loaded = True
        self._load_ms = round((time.perf_counter() - started) * 1000)

    def transcribe(self, audio_path: str | Path) -> tuple[str, dict[str, Any]]:
        self.load_model()
        assert self._model is not None

        started = time.perf_counter()
        suffix = Path(audio_path).suffix or ".audio"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(Path(audio_path).read_bytes())
            tmp.flush()
            with torch.no_grad():
                output = self._model.transcribe([tmp.name], batch_size=1)

        transcript = _extract_text(output)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return transcript, {
            "model": MODEL_NAME,
            "device": DEVICE,
            "asr_ms": elapsed_ms,
            "load_ms": self._load_ms,
        }


def _extract_text(output: Any) -> str:
    if not output:
        return ""
    first = output[0]
    if isinstance(first, str):
        return first.strip()
    if hasattr(first, "text"):
        return str(first.text).strip()
    return str(first).strip()


transcriber = ParakeetTranscriber()
