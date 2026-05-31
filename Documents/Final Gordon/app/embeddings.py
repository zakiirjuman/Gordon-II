from __future__ import annotations

import json
import logging
import math
from typing import Any

import httpx

from app.config import (
    CORPUS_VERSION,
    EMBED_INDEX_PATH,
    OLLAMA_EMBED_MODEL,
    OLLAMA_URL,
    RAG_MODE,
)

logger = logging.getLogger(__name__)

_INDEX_CACHE: dict[str, Any] | None = None
_EMBED_MODEL_READY: bool | None = None
_LAST_RAG_MODE: str = "keyword"


def card_embed_text(
    card_id: str,
    title: str,
    body: str,
    tags: tuple[str, ...],
) -> str:
    tag_text = ", ".join(tags)
    return f"{card_id} {title} {tag_text} {body}".strip()


def embed_text(text: str, *, timeout: float = 30.0) -> list[float] | None:
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            return None
        return [float(x) for x in embedding]
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Ollama embed failed: %s", exc)
        return None


def probe_embed_model(*, timeout: float = 3.0) -> bool:
    global _EMBED_MODEL_READY
    if _EMBED_MODEL_READY is not None:
        return _EMBED_MODEL_READY
    _EMBED_MODEL_READY = embed_text("health check", timeout=timeout) is not None
    return _EMBED_MODEL_READY


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _load_index_file() -> dict[str, Any] | None:
    if not EMBED_INDEX_PATH.is_file():
        return None
    try:
        data = json.loads(EMBED_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read embed index: %s", exc)
        return None
    if data.get("corpus_version") != CORPUS_VERSION:
        return None
    if data.get("embed_model") != OLLAMA_EMBED_MODEL:
        return None
    cards = data.get("cards")
    if not isinstance(cards, list) or not cards:
        return None
    return data


def _save_index_file(index: dict[str, Any]) -> None:
    EMBED_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMBED_INDEX_PATH.write_text(json.dumps(index), encoding="utf-8")


def build_embed_index(
    cards: list[tuple[str, str, str, tuple[str, ...]]],
) -> dict[str, Any] | None:
    entries: list[dict[str, Any]] = []
    for card_id, title, body, tags in cards:
        vector = embed_text(card_embed_text(card_id, title, body, tags))
        if vector is None:
            return None
        entries.append({"card_id": card_id, "embedding": vector})
    index = {
        "corpus_version": CORPUS_VERSION,
        "embed_model": OLLAMA_EMBED_MODEL,
        "cards": entries,
    }
    try:
        _save_index_file(index)
    except OSError as exc:
        logger.warning("Could not write embed index: %s", exc)
    return index


def get_embed_index(
    cards: list[tuple[str, str, str, tuple[str, ...]]],
    *,
    force_rebuild: bool = False,
) -> dict[str, Any] | None:
    global _INDEX_CACHE
    if RAG_MODE == "keyword":
        return None
    if not force_rebuild and _INDEX_CACHE is not None:
        return _INDEX_CACHE
    if not force_rebuild:
        cached = _load_index_file()
        if cached is not None:
            _INDEX_CACHE = cached
            return _INDEX_CACHE
    if not probe_embed_model():
        return None
    index = build_embed_index(cards)
    if index is not None:
        _INDEX_CACHE = index
    return _INDEX_CACHE


def score_cards_by_embedding(
    query: str,
    index: dict[str, Any],
) -> dict[str, float]:
    query_vector = embed_text(query)
    if query_vector is None:
        return {}
    scores: dict[str, float] = {}
    for entry in index.get("cards", []):
        card_id = entry.get("card_id")
        vector = entry.get("embedding")
        if not isinstance(card_id, str) or not isinstance(vector, list):
            continue
        scores[card_id] = _cosine(query_vector, vector)
    return scores


def set_last_rag_mode(mode: str) -> None:
    global _LAST_RAG_MODE
    _LAST_RAG_MODE = mode


def rag_status() -> dict[str, object]:
    embed_index_cached = _load_index_file() is not None
    embed_model_ready = probe_embed_model() if RAG_MODE != "keyword" else False

    if RAG_MODE == "keyword":
        rag_mode = "keyword"
    elif RAG_MODE == "embeddings":
        rag_mode = "embeddings" if embed_model_ready else "keyword"
    elif embed_model_ready:
        rag_mode = "embeddings"
    else:
        rag_mode = "keyword"

    return {
        "rag_mode": rag_mode,
        "last_rag_mode": _LAST_RAG_MODE,
        "embed_model": OLLAMA_EMBED_MODEL,
        "embed_model_ready": embed_model_ready,
        "embed_index_cached": embed_index_cached,
    }
