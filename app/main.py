from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import APP_NAME, APP_TAGLINE, CORPUS_VERSION, STATIC_DIR
from app.legal_rag import get_corpus, retrieve_law_cards
from app.llm import answer_question, generate_briefing, generate_patrol_brief
from app.toronto_data import (
    build_ops_snapshot,
    fetch_construction_hubs,
    fetch_recent_collisions,
    fetch_road_restrictions,
)

app = FastAPI(
    title=APP_NAME,
    description=f"{APP_TAGLINE} Patrol decision support on DGX Spark with Toronto data + law-grounded RAG.",
    version="0.2.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


async def _load_snapshot() -> dict:
    restrictions = await fetch_road_restrictions()
    hubs = await fetch_construction_hubs()
    collisions = await fetch_recent_collisions(days=365)
    snapshot = build_ops_snapshot(restrictions, hubs, collisions)
    snapshot["product"] = APP_NAME
    snapshot["corpus_version"] = CORPUS_VERSION
    return snapshot


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "product": APP_NAME, "corpus_version": CORPUS_VERSION}


@app.get("/api/snapshot")
async def snapshot() -> dict:
    return await _load_snapshot()


@app.get("/api/layers/road-restrictions")
async def road_restrictions() -> dict:
    return await fetch_road_restrictions()


@app.get("/api/layers/construction-hubs")
async def construction_hubs() -> dict:
    return await fetch_construction_hubs()


@app.get("/api/corpus")
async def corpus_index() -> dict:
    cards = get_corpus()
    return {
        "corpus_version": CORPUS_VERSION,
        "count": len(cards),
        "cards": [
            {
                "id": c.card_id,
                "title": c.title,
                "category": c.category,
                "source": c.source,
                "tags": list(c.tags),
            }
            for c in cards
        ],
    }


@app.post("/api/patrol-brief")
async def patrol_brief() -> dict:
    try:
        snapshot = await _load_snapshot()
        return await generate_patrol_brief(snapshot)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/briefing")
async def briefing() -> dict[str, str]:
    try:
        snapshot = await _load_snapshot()
        text = await generate_briefing(snapshot)
        cards = retrieve_law_cards(snapshot)
        return {"briefing": text, "cards_used": [c.card_id for c in cards]}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/ask")
async def ask(body: AskRequest) -> dict:
    try:
        snapshot = await _load_snapshot()
        return await answer_question(body.question, snapshot)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
