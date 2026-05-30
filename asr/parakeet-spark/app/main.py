from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from typing import Optional

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.transcriber import DEVICE, MODEL_NAME, transcriber


@asynccontextmanager
async def lifespan(app: FastAPI):
    transcriber.load_model()
    yield


app = FastAPI(
    title="Gordon Parakeet ASR",
    description="OpenAI-compatible STT powered by NVIDIA Parakeet on DGX Spark.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    gpu_memory = None
    if torch.cuda.is_available():
        gpu_memory = {
            "allocated_gb": round(torch.cuda.memory_allocated(0) / (1024**3), 2),
            "total_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1),
        }
    return {
        "status": "ready" if transcriber._loaded else "loading",
        "model": MODEL_NAME,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_memory": gpu_memory,
    }


@app.get("/v1/health/ready")
async def ready() -> dict[str, str]:
    if not transcriber._loaded:
        raise HTTPException(status_code=503, detail="Model is still loading.")
    return {"status": "ready"}


@app.get("/v1/models")
async def models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "parakeet-tdt-0.6b-v3",
                "object": "model",
                "owned_by": "nvidia",
            }
        ],
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: Optional[str] = Form(default="parakeet-tdt-0.6b-v3"),
    language: Optional[str] = Form(default=None),
    response_format: Optional[str] = Form(default="json"),
) -> dict:
    if not transcriber._loaded:
        raise HTTPException(status_code=503, detail="Model is still loading.")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio upload was empty.")

    suffix = "." + (file.filename or "audio.wav").split(".")[-1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(payload)
        tmp.flush()
        text, meta = transcriber.transcribe(tmp.name)

    return {
        "text": text,
        "model": model,
        "language": language,
        "response_format": response_format,
        "meta": meta,
    }
