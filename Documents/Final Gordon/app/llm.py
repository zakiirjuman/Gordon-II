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


async def evaluate_interaction(
    diarized_transcript: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    law_context = _law_cards_for(snapshot)
    prompt = (
        "You are reviewing a recorded patrol interaction between two speakers.\n"
        "The transcript uses Speaker 1 / Speaker 2 labels from audio clustering (demo-grade, not forensic).\n\n"
        "Tasks:\n"
        "1. Decide which speaker is most likely the police officer.\n"
        "2. Summarize what the officer was trying to accomplish.\n"
        "3. Decide whether the officer earns a private STAR for accountable, de-escalatory, lawful conduct.\n"
        "   - Award a star only for clearly strong work (clear grounds, distance, calm control, documentation, rights advisement).\n"
        "   - Stay silent (star_awarded=false) for mediocre, ambiguous, or poor conduct — do not star bad work.\n"
        "4. Flag danger only if the officer's approach appears to be escalating unsafely.\n\n"
        "Respond with ONLY valid JSON (no markdown) using this schema:\n"
        "{\n"
        '  "officer_speaker": "Speaker 1",\n'
        '  "officer_intent_summary": "...",\n'
        '  "star_awarded": true,\n'
        '  "star_message": "...",\n'
        '  "rationale": "...",\n'
        '  "danger": false,\n'
        '  "danger_message": null\n'
        "}\n\n"
        f"LAW CARDS:\n{law_context}\n\n"
        f"TORONTO DATA SNAPSHOT:\n{_format_snapshot(snapshot)}\n\n"
        f"DIARIZED TRANSCRIPT:\n{diarized_transcript}"
    )
    raw = await _ollama_generate(prompt, num_predict=700)
    return _parse_evaluation_json(raw)


def _parse_evaluation_json(raw: str) -> dict[str, Any]:
    import re

    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {
            "officer_speaker": "Speaker 1",
            "officer_intent_summary": "Could not parse structured evaluation.",
            "star_awarded": False,
            "star_message": None,
            "rationale": raw[:800],
            "danger": False,
            "danger_message": None,
            "parse_error": True,
        }

    return {
        "officer_speaker": data.get("officer_speaker") or "Speaker 1",
        "officer_intent_summary": data.get("officer_intent_summary") or "",
        "star_awarded": bool(data.get("star_awarded")),
        "star_message": data.get("star_message"),
        "rationale": data.get("rationale") or "",
        "danger": bool(data.get("danger")),
        "danger_message": data.get("danger_message"),
    }


async def _ollama_generate(prompt: str, *, num_predict: int = 900) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
