from __future__ import annotations

import time

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import (
    APP_NAME,
    APP_TAGLINE,
    CORPUS_VERSION,
    DEFAULT_POINT_RADIUS_M,
    OLLAMA_MODEL,
    STATIC_DIR,
    WHISPER_MODEL,
)
from app.interjection import assess_situation
from app.legal_rag import get_corpus, retrieve_law_cards
from app.llm import answer_question, generate_briefing, generate_patrol_brief
from app.spatial import build_point_snapshot, cudf_available
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


class PointBriefRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=DEFAULT_POINT_RADIUS_M, ge=100, le=5000)


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
async def health() -> dict[str, object]:
    whisper_runtime = {}
    try:
        from app.voice import whisper_available, whisper_runtime as get_whisper_runtime
    except Exception:  # noqa: BLE001
        whisper_ready = False
    else:
        whisper_ready = whisper_available()
        whisper_runtime = get_whisper_runtime()
    return {
        "status": "ok",
        "product": APP_NAME,
        "corpus_version": CORPUS_VERSION,
        "ollama_model": OLLAMA_MODEL,
        "whisper_model": WHISPER_MODEL,
        "whisper_ready": whisper_ready,
        "whisper_runtime": whisper_runtime,
        "cudf_ready": cudf_available(),
    }


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


@app.post("/api/patrol-brief/point")
async def patrol_brief_point(body: PointBriefRequest) -> dict:
    started = time.perf_counter()
    try:
        restrictions = await fetch_road_restrictions()
        hubs = await fetch_construction_hubs()
        collisions = await fetch_recent_collisions(days=365)
        snapshot = build_point_snapshot(
            lat=body.lat,
            lng=body.lng,
            radius_m=body.radius_m,
            restrictions=restrictions,
            hubs=hubs,
            collisions=collisions,
        )
        snapshot["product"] = APP_NAME
        snapshot["corpus_version"] = CORPUS_VERSION
        result = await generate_patrol_brief(snapshot)
        timings = {
            **snapshot.get("timings_ms", {}),
            "total": round((time.perf_counter() - started) * 1000),
        }
        return {**result, "snapshot": snapshot, "timings_ms": timings}
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
        interjection = assess_situation(body.question, snapshot)
        result = await answer_question(body.question, snapshot, interjection=interjection)
        return {**result, "interjection": interjection.to_dict()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/voice/ask")
async def voice_ask(audio: UploadFile = File(...)) -> dict:
    try:
        from app.voice import transcribe_upload

        started = time.perf_counter()
        transcript, stt_ms = await transcribe_upload(audio)
        snapshot = await _load_snapshot()
        interjection = assess_situation(transcript, snapshot)
        result = await answer_question(transcript, snapshot, interjection=interjection)
        timings = {
            "stt": stt_ms,
            "total": round((time.perf_counter() - started) * 1000),
        }
        return {
            "transcript": transcript,
            **result,
            "interjection": interjection.to_dict(),
            "timings_ms": timings,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
