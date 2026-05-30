# Gordon II

**Lawful patrol intelligence for Toronto** — named after Jim Gordon, not Batman.

Live map of road restrictions, construction, and KSI collision patterns, fused with **law-grounded RAG** and **local Nemotron** briefings on the ASUS DGX Spark (GX10).

> Decision support only. Not legal advice. See [docs/GORDON_II.md](docs/GORDON_II.md) for product vision, API, and agent handoff.

## What it does

1. **Lookout** — Toronto ArcGIS restrictions + construction + KSI hotspots  
2. **Authority & policy** — retrieved corpus cards with `[card_id]` citations  
3. **Do not** — explicit overreach warnings for field decisions  

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Open http://localhost:8080

## Deploy to GX10

```bash
./scripts/deploy_gx10.sh
```

Teammates: read **[docs/DEPLOY.md](docs/DEPLOY.md)** (shared Spark etiquette, NVIDIA Sync SSH).

## Docs

| Doc | Audience |
|-----|----------|
| [docs/GORDON_II.md](docs/GORDON_II.md) | Product, API, corpus, next steps for agents |
| [docs/DEPLOY.md](docs/DEPLOY.md) | GX10 deploy for humans + agents |

## Hardware

- ASUS GX10 (`gx10-49d1`) over Tailscale  
- Ollama: `nemotron3:33b` (configurable in `app/config.py`)
