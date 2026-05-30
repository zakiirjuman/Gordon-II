# Toronto Urban Ops Copilot

Hackathon demo for the **Urban Operations** track — a live ops dashboard that ingests Toronto transportation data, maps active road restrictions, and generates actionable briefings with **local Nemotron** on the ASUS DGX Spark (GX10).

## What it does

1. **Ingests live Toronto data**
   - RODARS current road restriction lines (ArcGIS FeatureServer)
   - Transportation Services construction hubs
   - Recent KSI motor vehicle collisions (City open data, refreshed daily)

2. **Builds an ops snapshot** — counts, top disrupted roads, collision hotspots by ward/street

3. **Runs local AI on Spark** — Nemotron via Ollama generates:
   - Morning ops briefing
   - Natural-language Q&A for transportation staff

4. **Serves a lightweight dashboard** — Leaflet map + stats + copilot panel

## Why this fits judging

- **Urban Operations track:** real-time road restrictions + safety signals for city ops
- **NVIDIA stack:** Nemotron runs locally on 121GB unified memory (no cloud LLM dependency)
- **Spark story:** private, low-latency inference on operational data at the edge

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Open http://localhost:8080

Requires Ollama with `nemotron3:33b` (or change `OLLAMA_MODEL` in `app/config.py`).

## Deploy to GX10

```bash
chmod +x scripts/deploy_gx10.sh
./scripts/deploy_gx10.sh
```

Then open http://gx10-49d1:8080 over Tailscale.

## API

- `GET /api/snapshot` — aggregated ops metrics
- `GET /api/layers/road-restrictions` — GeoJSON restrictions
- `POST /api/briefing` — Nemotron-generated ops briefing
- `POST /api/ask` — `{ "question": "..." }`

## Hardware target

- ASUS GX10 (`gx10-49d1`) over Tailscale
- NVIDIA GB10, ~121 GB unified memory
- Ollama models: `nemotron3:33b`, `gemma4:26b`, etc.
