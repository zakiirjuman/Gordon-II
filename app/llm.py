from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import OLLAMA_MODEL, OLLAMA_URL

SYSTEM_PROMPT = """You are Toronto Urban Ops Copilot, an assistant for city transportation operations staff.
You analyze live Toronto road restrictions, construction hubs, and recent KSI collision patterns.
Be concise, actionable, and specific. Prioritize operational decisions: routing, crew dispatch, and safety hotspots.
If data is sparse, say so. Never invent closures or collisions not present in the provided snapshot."""


def _format_snapshot(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, indent=2)


async def generate_briefing(snapshot: dict[str, Any]) -> str:
    prompt = (
        "Create a morning operations briefing for Toronto Transportation Services.\n"
        "Include: (1) headline stats, (2) top disruption corridors, "
        "(3) safety hotspots from recent KSI collisions, (4) 3 recommended actions for today.\n\n"
        f"DATA SNAPSHOT:\n{_format_snapshot(snapshot)}"
    )
    return await _ollama_generate(prompt)


async def answer_question(question: str, snapshot: dict[str, Any]) -> str:
    prompt = (
        f"QUESTION: {question}\n\n"
        "Answer using only the snapshot below. Mention specific roads or wards when possible.\n\n"
        f"DATA SNAPSHOT:\n{_format_snapshot(snapshot)}"
    )
    return await _ollama_generate(prompt)


async def _ollama_generate(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 700,
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
