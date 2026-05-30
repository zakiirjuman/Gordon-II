from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import STATIC_DIR
from app.llm import answer_question, generate_briefing
from app.toronto_data import (
    build_ops_snapshot,
    fetch_construction_hubs,
    fetch_recent_collisions,
    fetch_road_restrictions,
)

app = FastAPI(
    title="Toronto Urban Ops Copilot",
    description="Live Toronto transportation ops dashboard powered by local Nemotron on DGX Spark.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


async def _load_snapshot() -> dict:
    restrictions = await fetch_road_restrictions()
    hubs = await fetch_construction_hubs()
    collisions = await fetch_recent_collisions(days=365)
    return build_ops_snapshot(restrictions, hubs, collisions)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/snapshot")
async def snapshot() -> dict:
    return await _load_snapshot()


@app.get("/api/layers/road-restrictions")
async def road_restrictions() -> dict:
    return await fetch_road_restrictions()


@app.get("/api/layers/construction-hubs")
async def construction_hubs() -> dict:
    return await fetch_construction_hubs()


@app.post("/api/briefing")
async def briefing() -> dict[str, str]:
    try:
        snapshot = await _load_snapshot()
        text = await generate_briefing(snapshot)
        return {"briefing": text}
    except Exception as exc:  # noqa: BLE001 - surface upstream errors to UI
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/ask")
async def ask(body: AskRequest) -> dict[str, str]:
    try:
        snapshot = await _load_snapshot()
        text = await answer_question(body.question, snapshot)
        return {"answer": text}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
