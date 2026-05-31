# Gordon II — models & deployment (for judges)

Short reference for **why we chose these models**, **how they run on DGX Spark**, and **what the demo proves**.

## What Gordon II demonstrates

Gordon II is a **local, officer-facing patrol copilot** on the ASUS DGX Spark (`gx10-49d1`). It combines live Toronto operational data, curated law/policy cards, and voice Q&A — all without sending officer questions to a cloud LLM.

The hardware story: **fast, on-device inference** for both language and speech on unified GPU memory.

---

## Model choices

| Role | Model | Why this choice |
|------|--------|-----------------|
| **Reasoning / answers** | `nemotron3:33b` via **Ollama** | Strong local LLM on Spark’s 121GB unified memory; structured patrol briefs with cited law cards. We disable internal “thinking” output (`think: false`) so responses are demo-ready. |
| **Speech-to-text (preferred)** | **`nvidia/parakeet-tdt-0.6b-v3`** via **NeMo** | NVIDIA Parakeet TDT is built for interactive voice (better latency/accuracy tradeoff than CTC for live commands). Runs on **GB10 CUDA** in a native ARM64 container. |
| **Law / policy context** | Curated markdown **law cards** + **Ollama embedding RAG** (`app/legal_rag.py`, `app/embeddings.py`) | Semantic top-k via `nomic-embed-text` with keyword fallback; cards tagged `lookout`, `authority`, `do_not` and cited as `[card_id]`. |
| **Situation awareness** | Rule-based **interjection** (`app/interjection.py`) | Detects stress/escalation language and snapshot hazards; adapts tone (praise, calm guidance, backup ETA) without an officer toggling “de-escalation mode.” |
| **ASR fallback** | `distil-large-v3` via **faster-whisper** (CPU) | Safety net if GPU ASR is down. On ARM64 Spark, CTranslate2 has **no CUDA build**, so Whisper is CPU-only — not our primary demo path. |

### Why not the off-the-shelf Speech NIM container?

We tried pulling NVIDIA Speech NIM images (e.g. `parakeet-ctc-1.1b-asr`). On GX10:

- The accessible image targets **`linux/amd64`**, while Spark is **`linux/arm64`**.
- Emulated x86 containers would not deliver the native GB10 GPU story.

**Our solution:** build a **Spark-native ASR microservice** (`asr/parakeet-spark/`) on NVIDIA’s ARM64 PyTorch base image `nvcr.io/nvidia/pytorch:25.11-py3`, install NeMo inside, and serve Parakeet TDT with an OpenAI-compatible HTTP API. Same model family, **correct architecture**.

Model weights are portable; the **runtime** (PyTorch + CUDA for ARM64/GB10) must match the hardware — that is what the NVIDIA PyTorch container provides.

---

## Runtime architecture (two services, one box)

```text
Browser (HTTPS via Tailscale Serve)
    │
    ▼
Gordon II  :8080   FastAPI + Ollama Nemotron + map + interjection
    │                 │
    │                 └── POST audio → Parakeet ASR :8010
    ▼
Parakeet ASR :8010   Docker: pytorch:25.11-py3 + NeMo + Parakeet on CUDA
```

| Service | Port | Stack |
|---------|------|--------|
| Gordon II app | **8080** | Python venv, `uvicorn`, Ollama at `11434` |
| Parakeet ASR | **8010** | Docker `gordon-parakeet-asr`, GPU via `--runtime=nvidia` |

Gordon converts browser `webm` → `wav` with **`ffmpeg` on the host**, then POSTs to `http://127.0.0.1:8010/v1/audio/transcriptions`. Parakeet returns text; Gordon sends it to Nemotron with law-card context.

**Verify health:**

```bash
curl http://127.0.0.1:8010/health          # Parakeet: device=cuda, gpu=NVIDIA GB10
curl http://127.0.0.1:8080/api/health    # Gordon: nim_ready=true, rag_mode=embeddings, asr_runtime.backend=nim
```

---

## Deploy steps (Spark)

### 1. Gordon II app

```bash
./scripts/deploy_gx10.sh
# Remote: ~/urban-ops-copilot on port 8080
```

Requires Ollama with `nemotron3:33b` and **`nomic-embed-text`** (embedding RAG) and **host `ffmpeg`** (`sudo apt install ffmpeg`).

```bash
ollama pull nomic-embed-text   # if not already present
```

### 2. GPU ASR service

```bash
cd asr/parakeet-spark
export NGC_API_KEY=...    # pull nvcr.io/nvidia/pytorch base image
./build-and-run.sh        # builds gordon-parakeet-asr, listens on 8010
```

First start downloads Parakeet weights (~few minutes). Check: `sudo docker logs -f gordon-parakeet-asr`.

### 3. HTTPS for microphone (Safari / remote clients)

Browsers require a secure context for mic access. We use **Tailscale Serve** on the Spark:

```bash
sudo tailscale serve --bg 8080
# e.g. https://gx10-49d1.<tailnet>.ts.net/
```

---

## Demo beats (what to show judges)

1. **Map click** → reverse-geocoded point brief (500 m haversine join + Nemotron + cited law cards).
2. **Voice command** → GPU Parakeet transcript → cited answer with interjection policy.
3. **Health / latency** → `/api/health` shows `nim_ready`, `rag_mode`, CUDA ASR; UI shows STT + total timings.
4. **Local & cited** → answers reference law cards and Toronto snapshot data, not cloud LLMs for reasoning.
5. **Encounter review** → record a two-speaker exchange → GPU diarization + Nemotron rubric → optional **star** with rationale (see [ENCOUNTER_TEST_SCRIPT.md](./ENCOUNTER_TEST_SCRIPT.md)).

---

## Honest limitations

- Law cards are **curated summaries**, not a live statute database.
- Map click uses **Nominatim** (OpenStreetMap) for a human-readable location label; spatial joins remain local Python haversine.
- RAG prefers **Ollama embeddings**; keyword overlap is the fallback when the embed model or index is unavailable.
- cuDF spatial joins are scaffolded (`app/spatial.py`); Python haversine path is live today.
- Whisper CPU fallback exists for resilience, not for the primary GPU narrative.

---

## Further reading

- [GORDON_II.md](./GORDON_II.md) — product pillars, API, corpus
- [DEPLOY.md](./DEPLOY.md) — shared Spark deploy etiquette (ports, SSH, teammates)
