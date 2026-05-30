from __future__ import annotations

import json
from typing import Any

import httpx

from app.interjection import Interjection, prompt_overlay
from app.config import APP_NAME, APP_TAGLINE, OLLAMA_MODEL, OLLAMA_URL
from app.legal_rag import format_law_context, retrieve_law_cards

SYSTEM_PROMPT = f"""You are {APP_NAME}, a lawful patrol decision-support copilot for Toronto-area officers.
Tagline: {APP_TAGLINE}

You are NOT Batman: no vigilantism, no precrime, no profiling, no automation of arrests or charges.
You help officers see: (1) situational lookout from Toronto data, (2) authority/policy considerations with citations,
(3) explicit "do not" boundaries to prevent overreach.

Rules:
- Use ONLY facts from the Toronto data snapshot and the LAW CARDS provided.
- Cite law cards by [card_id] when stating legal or policy points.
- If uncertain, say what is missing and recommend supervisor/policy verification.
- Never invent closures, collisions, statutes, or case law not in the provided context.
- Tone: calm, professional, checklist-oriented."""


def _format_snapshot(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, indent=2)


def _law_cards_for(snapshot: dict[str, Any], question: str | None = None) -> str:
    cards = retrieve_law_cards(snapshot, question)
    return format_law_context(cards)


async def generate_patrol_brief(
    snapshot: dict[str, Any],
    *,
    interjection: Interjection | None = None,
) -> dict[str, Any]:
    law_context = _law_cards_for(snapshot)
    prompt = (
        "Create a PATROL BRIEF for a Toronto officer starting a shift.\n"
        "Use EXACTLY these markdown section headers in order:\n\n"
        "## Lookout\n"
        "## Authority & policy\n"
        "## Do not\n\n"
        "Lookout: factual situational awareness from Toronto data (roads, KSI patterns, construction).\n"
        "Authority & policy: what officers may consider, with [card_id] citations from LAW CARDS.\n"
        "Do not: explicit overreach warnings with [card_id] citations.\n\n"
        f"{prompt_overlay(interjection)}\n"
        f"TORONTO DATA SNAPSHOT:\n{_format_snapshot(snapshot)}\n\n"
        f"LAW CARDS:\n{law_context}"
    )
    text = await _ollama_generate(prompt)
    return {"briefing": text, "law_context": law_context}


async def generate_briefing(snapshot: dict[str, Any]) -> str:
    """Legacy ops-style briefing (transportation framing)."""
    result = await generate_patrol_brief(snapshot)
    return result["briefing"]


async def answer_question(
    question: str,
    snapshot: dict[str, Any],
    *,
    interjection: Interjection | None = None,
) -> dict[str, Any]:
    law_context = _law_cards_for(snapshot, question)
    prompt = (
        f"OFFICER QUESTION: {question}\n\n"
        "Answer with the same three sections when helpful:\n"
        "## Lookout\n## Authority & policy\n## Do not\n\n"
        "Cite law cards as [card_id]. Do not exceed provided context.\n\n"
        f"{prompt_overlay(interjection)}\n"
        f"TORONTO DATA SNAPSHOT:\n{_format_snapshot(snapshot)}\n\n"
        f"LAW CARDS:\n{law_context}"
    )
    text = await _ollama_generate(prompt)
    return {"answer": text, "law_context": law_context}


async def _ollama_generate(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 900,
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
