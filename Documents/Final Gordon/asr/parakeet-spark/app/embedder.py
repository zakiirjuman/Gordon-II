from __future__ import annotations

import logging
import os
import time
from typing import Any

import torch

logger = logging.getLogger(__name__)

SPEAKER_MODEL = os.environ.get("SPEAKER_MODEL", "titanet_small")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class SpeakerEmbedder:
    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._load_ms: int | None = None

    def load_model(self) -> None:
        if self._loaded:
            return
        import nemo.collections.asr as nemo_asr

        started = time.perf_counter()
        model = nemo_asr.models.EncDecSpeakerLabelModel.from_pretrained(
            model_name=SPEAKER_MODEL
        )
        model = model.to(DEVICE)
        model.eval()
        self._model = model
        self._loaded = True
        self._load_ms = round((time.perf_counter() - started) * 1000)

    def _to_vector(self, embedding: Any) -> list[float]:
        if embedding is None:
            raise RuntimeError("Speaker model returned no embedding.")
        if isinstance(embedding, (list, tuple)):
            if len(embedding) == 1:
                return self._to_vector(embedding[0])
            return [float(value) for value in embedding]
        if hasattr(embedding, "detach"):
            embedding = embedding.detach()
        if hasattr(embedding, "cpu"):
            embedding = embedding.cpu()
        if hasattr(embedding, "numpy"):
            vector = embedding.numpy().reshape(-1)
        elif hasattr(embedding, "flatten"):
            vector = embedding.flatten()
        else:
            vector = list(embedding)
        values = [float(value) for value in vector]
        if not values:
            raise RuntimeError("Speaker model returned an empty embedding.")
        return values

    def embed(self, audio_path: str) -> list[float]:
        self.load_model()
        assert self._model is not None
        try:
            with torch.no_grad():
                embedding = self._model.get_embedding(audio_path)
            return self._to_vector(embedding)
        except Exception as exc:
            logger.exception("Failed to embed audio segment %s", audio_path)
            raise RuntimeError(f"Speaker embedding failed: {exc}") from exc


embedder = SpeakerEmbedder()
