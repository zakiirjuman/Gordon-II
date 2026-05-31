# Gordon II

**Lawful Patrol Intelligence & Officer Wellbeing Copilot** — Urban Operations, Toronto Open Data Hackathon.

Named after **Jim Gordon**, not Batman. Decision support for patrol officers: live Toronto operational picture, **law-grounded briefings** with cited policy cards, and **private wellbeing check-ins** — all running **locally on the ASUS DGX Spark** (no cloud LLM for officer conversations).

> Decision support only. Not legal advice. Officers remain accountable.

| | |
|---|---|
| **Live demo** | https://gx10-49d1.tail935b6d.ts.net *(Tailscale HTTPS)* |
| **Repo** | https://github.com/zakiirjuman/Gordon-II |
| **Team** | Zakiir Juman · Leon Lo · Tushar Sroya |

---

## What it does

Three pillars in every patrol brief:

| Pillar | Source | Brief section |
|--------|--------|---------------|
| **Lookout** | Toronto open data (restrictions, construction, KSI, wards, schools, fire stations) + demo simulated units | `## Lookout` |
| **Authority & policy** | Curated law cards + Ollama embedding RAG | `## Authority & policy` |
| **Do not** | Cards tagged `do_not` + prompt guardrails | `## Do not` |

**Officer wellbeing:** after a difficult call, an officer can talk to Gordon (text or voice). Responses are private, local, and judgment-free — no supervisor file. Encounter review can award a **private star** for strong, accountable work.

---

## Quick start (local)

**Prerequisites:** Python 3.9+, [Ollama](https://ollama.com) with `nemotron3:33b` and `nomic-embed-text`.

```bash
git clone https://github.com/zakiirjuman/Gordon-II.git
cd Gordon-II

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

ollama pull nemotron3:33b
ollama pull nomic-embed-text

uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Open http://localhost:8080

Optional overrides: copy [`.env.example`](.env.example) → `.env` (most settings live in [`app/config.py`](app/config.py)).

---

## Deploy to DGX Spark (GX10)

```bash
./scripts/deploy_gx10.sh
# → http://gx10-49d1:8080  (Tailscale)
# → https://gx10-49d1.tail935b6d.ts.net  (HTTPS + microphone)
```

Requires Ollama on the Spark, NVIDIA Sync SSH key, and `ffmpeg` on the host. See **[docs/DEPLOY.md](docs/DEPLOY.md)** for port etiquette and troubleshooting.

**GPU voice (recommended for demo):**

```bash
cd asr/parakeet-spark
export NGC_API_KEY=...   # pull NVIDIA PyTorch base image
./build-and-run.sh       # Parakeet TDT on :8010
```

---

## Tech stack

| Layer | Technology |
|-------|------------|
| **UI** | Leaflet map, Hearth design system, `marked.js` markdown |
| **API** | FastAPI + uvicorn |
| **Reasoning** | Ollama `nemotron3:33b` (local, `think: false` for demo-ready output) |
| **RAG** | Curated markdown law cards + `nomic-embed-text` embeddings (keyword fallback) |
| **ASR (primary)** | NVIDIA Parakeet TDT 0.6B via NeMo on GB10 CUDA (`:8010`) |
| **ASR (fallback)** | faster-whisper `distil-large-v3` (CPU on ARM64) |
| **Diarization** | GPU speaker embedding + clustering for encounter review |
| **Spatial** | Python haversine point-radius joins (cuDF scaffolded) |
| **Geocode** | Nominatim reverse geocode (cached) for map-click labels |
| **Hardware** | ASUS DGX Spark (`gx10-49d1`), 121GB unified memory, Tailscale Serve |

---

## Architecture

```text
Browser (HTTPS via Tailscale Serve)
    │
    ▼
Gordon II :8080 ── FastAPI
    ├── Toronto open data (ArcGIS + CKAN GeoJSON/CSV)
    ├── Spatial joins + geocode cache
    ├── Law corpus RAG (Ollama embeddings)
    ├── Nemotron patrol briefs / Q&A / encounter rubric
    └── POST audio ──► Parakeet ASR :8010 (Docker, CUDA)
                              │
                              └── NeMo parakeet-tdt-0.6b-v3 on GB10
```

---

## Toronto datasets

| Dataset | Source | Used for |
|---------|--------|----------|
| Active road restrictions | [Toronto ArcGIS](https://gis.toronto.ca/) layer 77 | Map lines, brief counts |
| Construction hubs | ArcGIS layer 71 | Map markers |
| City wards | ArcGIS layer 0 | Ward name in point briefs |
| Fire stations | [Open Toronto GeoJSON](https://open.toronto.ca/) | Map + nearest hall in brief |
| Schools | Open Toronto GeoJSON | Map + school proximity |
| KSI collisions (12 mo) | Open Toronto CSV | Hotspot layer + brief |
| Simulated backup/EMS | Generated locally | **Demo only — not live CAD** |

Law/policy context: curated cards in [`app/corpus/`](app/corpus/) (not a live statute database).

---

## API (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Status, corpus version, RAG/ASR readiness |
| GET | `/api/snapshot` | Toronto ops counts + hot corridors |
| POST | `/api/patrol-brief` | City-wide patrol brief |
| POST | `/api/patrol-brief/point` | 500 m radius brief + geocoded location |
| POST | `/api/ask` | Text Q&A with law cards |
| POST | `/api/voice/ask` | Mic → Parakeet → Nemotron |
| POST | `/api/interaction/evaluate` | Encounter recording → diarization → star |

Full reference: **[docs/GORDON_II.md](docs/GORDON_II.md)**

---

## Demo script (4 min)

See **[docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md)** and team submission doc for the judged walkthrough: map → point brief → Ask/voice → Spark privacy story.

**Rehearsal beats:**

1. Map click near a ward → brief with **Lookout / Authority / Do not**
2. Ask Gordon a traffic-stop question → cited answer
3. Tap to speak (HTTPS URL required for mic)
4. Optional: encounter recording → private star

---

## Limitations (honest)

- Law cards are **curated training summaries**, not live statute or service policy.
- Simulated backup/EMS markers are **demo-only**, not live CAD or dispatch.
- Map-click labels use **Nominatim** (OpenStreetMap); spatial joins are local Python haversine.
- RAG prefers Ollama embeddings; keyword overlap is the fallback.
- cuDF spatial joins are scaffolded; Python path is live today.
- Whisper CPU fallback exists for resilience, not the primary GPU demo path.

Judges' technical reference: **[docs/JUDGING.md](docs/JUDGING.md)**

---

## Docs

| Doc | Purpose |
|-----|---------|
| [docs/GORDON_II.md](docs/GORDON_II.md) | Product pillars, API, corpus |
| [docs/JUDGING.md](docs/JUDGING.md) | Models, Spark deploy, demo beats |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Shared GX10 deploy etiquette |
| [docs/ENCOUNTER_TEST_SCRIPT.md](docs/ENCOUNTER_TEST_SCRIPT.md) | Encounter + star rehearsal |
| [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md) | May 31 submission tasks |

---

## Team

| Name | Role |
|------|------|
| Zakiir Juman | Lead Engineer |
| Leon Lo | Product & Business Impact |
| Tushar Roya | Design & Product |
