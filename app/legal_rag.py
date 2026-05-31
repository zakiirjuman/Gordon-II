from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import CORPUS_DIR, CORPUS_VERSION

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass(frozen=True)
class LawCard:
    card_id: str
    title: str
    category: str
    source: str
    tags: tuple[str, ...]
    body: str

    def to_context_block(self) -> str:
        return (
            f"[{self.card_id}] {self.title}\n"
            f"Category: {self.category} | Source: {self.source}\n"
            f"{self.body.strip()}"
        )


def _parse_card(path: Path) -> LawCard:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(raw)
    if not match:
        raise ValueError(f"Corpus file missing frontmatter: {path}")

    meta_lines, body = match.group(1), match.group(2)
    meta: dict[str, str] = {}
    for line in meta_lines.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()

    tags = tuple(t.strip() for t in meta.get("tags", "").split(",") if t.strip())
    return LawCard(
        card_id=meta.get("id", path.stem),
        title=meta.get("title", path.stem),
        category=meta.get("category", "authority"),
        source=meta.get("source", "Curated training summary"),
        tags=tags,
        body=body,
    )


def load_corpus() -> list[LawCard]:
    cards: list[LawCard] = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        cards.append(_parse_card(path))
    return cards


_CORPUS_CACHE: list[LawCard] | None = None


def get_corpus() -> list[LawCard]:
    global _CORPUS_CACHE
    if _CORPUS_CACHE is None:
        _CORPUS_CACHE = load_corpus()
    return _CORPUS_CACHE


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z]{3,}", text)}


def _score_card(card: LawCard, query_tokens: set[str]) -> float:
    haystack = " ".join([card.title, card.body, " ".join(card.tags), card.category])
    card_tokens = _tokenize(haystack)
    if not query_tokens:
        return 0.0
    overlap = query_tokens & card_tokens
    return len(overlap) / max(len(query_tokens), 1)


def build_query_from_snapshot(snapshot: dict[str, Any], question: str | None = None) -> str:
    parts: list[str] = [
        "patrol traffic stop detention search pursuit construction collision ward",
        question or "",
    ]
    for key in ("top_restricted_roads", "top_collision_streets_12mo", "top_collision_wards_12mo"):
        for item, _count in snapshot.get(key, [])[:5]:
            parts.append(str(item))
    for row in snapshot.get("sample_restrictions", [])[:6]:
        parts.extend(
            str(row.get(k, ""))
            for k in ("road", "location", "type", "issue", "description")
        )
    location = snapshot.get("location") or {}
    for key in ("label", "road", "neighbourhood", "city", "display_name"):
        value = location.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _corpus_embed_inputs() -> list[tuple[str, str, str, tuple[str, ...]]]:
    return [(c.card_id, c.title, c.body, c.tags) for c in get_corpus()]


def _select_with_guardrails(
    ranked: list[LawCard],
    score_fn,
    *,
    top_k: int,
    skip_zero_after_first: bool,
) -> list[LawCard]:
    selected: list[LawCard] = []
    seen_ids: set[str] = set()
    categories_seen: set[str] = set()

    for card in ranked:
        if card.card_id in seen_ids:
            continue
        if skip_zero_after_first and score_fn(card) <= 0 and categories_seen:
            continue
        selected.append(card)
        seen_ids.add(card.card_id)
        categories_seen.add(card.category)
        if len(selected) >= top_k:
            break

    for required in ("do_not", "authority", "lookout"):
        if required in categories_seen:
            continue
        for card in ranked:
            if card.category == required and card.card_id not in seen_ids:
                selected.append(card)
                seen_ids.add(card.card_id)
                categories_seen.add(card.category)
                break

    return selected[:top_k]


def _retrieve_law_cards_keyword(
    snapshot: dict[str, Any],
    question: str | None,
    *,
    top_k: int,
) -> list[LawCard]:
    query_tokens = _tokenize(build_query_from_snapshot(snapshot, question))
    corpus = get_corpus()
    ranked = sorted(
        corpus,
        key=lambda card: _score_card(card, query_tokens),
        reverse=True,
    )
    return _select_with_guardrails(
        ranked,
        lambda card: _score_card(card, query_tokens),
        top_k=top_k,
        skip_zero_after_first=True,
    )


def _retrieve_law_cards_embeddings(
    snapshot: dict[str, Any],
    question: str | None,
    *,
    top_k: int,
) -> list[LawCard] | None:
    from app.embeddings import get_embed_index, score_cards_by_embedding, set_last_rag_mode

    corpus = get_corpus()
    index = get_embed_index(_corpus_embed_inputs())
    if index is None:
        return None

    query = build_query_from_snapshot(snapshot, question)
    scores = score_cards_by_embedding(query, index)
    if not scores:
        return None

    ranked = sorted(
        corpus,
        key=lambda card: scores.get(card.card_id, 0.0),
        reverse=True,
    )
    selected = _select_with_guardrails(
        ranked,
        lambda card: scores.get(card.card_id, 0.0),
        top_k=top_k,
        skip_zero_after_first=False,
    )
    set_last_rag_mode("embeddings")
    return selected


def retrieve_law_cards(
    snapshot: dict[str, Any],
    question: str | None = None,
    *,
    top_k: int = 6,
    min_per_category: int = 1,
) -> list[LawCard]:
    del min_per_category  # guardrails always ensure category coverage when possible
    from app.config import RAG_MODE
    from app.embeddings import set_last_rag_mode

    if RAG_MODE != "keyword":
        embedded = _retrieve_law_cards_embeddings(snapshot, question, top_k=top_k)
        if embedded is not None:
            return embedded

    cards = _retrieve_law_cards_keyword(snapshot, question, top_k=top_k)
    set_last_rag_mode("keyword")
    return cards


def format_law_context(cards: list[LawCard]) -> str:
    header = f"CORPUS_VERSION: {CORPUS_VERSION}\n"
    if not cards:
        return header + "No law cards retrieved."
    return header + "\n\n---\n\n".join(card.to_context_block() for card in cards)
