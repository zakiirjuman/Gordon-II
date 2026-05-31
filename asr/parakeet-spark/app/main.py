from __future__ import annotations

import logging
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

logger = logging.getLogger(__name__)

from app.transcriber import DEVICE, MODEL_NAME, transcriber
from app.embedder import SPEAKER_MODEL, embedder
from app.interaction import analyze_interaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    transcriber.load_model()
    try:
        embedder.load_model()
    except Exception:  # noqa: BLE001
        # Interaction analysis falls back to ASR-only if speaker model fails to load.
        pass
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
        "speaker_model": SPEAKER_MODEL if embedder._loaded else None,
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


@app.post("/v1/interaction/analyze")
async def interaction_analyze(
    file: UploadFile = File(...),
    max_speakers: int = Form(default=2),
) -> dict:
    if not transcriber._loaded:
        raise HTTPException(status_code=503, detail="ASR model is still loading.")
    if not embedder._loaded:
        raise HTTPException(
            status_code=503,
            detail="Speaker embedding model is still loading or failed to load.",
        )
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio upload was empty.")

    suffix = "." + (file.filename or "audio.wav").split(".")[-1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(payload)
        tmp.flush()
        src_path = tmp.name

    wav_path = src_path
    cleanup: list[str] = [src_path]
    if not src_path.lower().endswith(".wav"):
        wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_tmp.close()
        cleanup.append(wav_tmp.name)

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                src_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                wav_tmp.name,
            ],
            check=True,
        )
        wav_path = wav_tmp.name

    try:
        return analyze_interaction(wav_path, max_speakers=max(2, min(max_speakers, 4)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        logger.exception("ffmpeg failed during interaction analyze")
        raise HTTPException(status_code=400, detail="Audio conversion failed.") from exc
    except RuntimeError as exc:
        logger.exception("GPU runtime error during interaction analyze")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during interaction analyze")
        raise HTTPException(
            status_code=500,
            detail=f"Interaction analysis failed: {type(exc).__name__}: {exc}",
        ) from exc
    finally:
        for path in cleanup:
            Path(path).unlink(missing_ok=True)
