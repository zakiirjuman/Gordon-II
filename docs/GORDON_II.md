# Gordon II — Agent & teammate handoff

> **Gordon II** (after Jim Gordon): lawful patrol decision support — *not Batman.*  
> Decision support only. Not legal advice. Officers remain accountable.

## What this product is

| Pillar | Source | Output section |
|--------|--------|----------------|
| **Lookout** | Toronto open data (ArcGIS restrictions, construction, KSI collisions) | `## Lookout` |
| **Authority & policy** | Curated law cards in `app/corpus/*.md` (RAG) | `## Authority & policy` |
| **Do not** | Cards tagged `do_not` + prompt guardrails | `## Do not` |

Runs on **ASUS DGX Spark** (`gx10-49d1`): FastAPI + **Ollama Nemotron** locally. No cloud LLM required for demos.

## Repo map

```
app/
  main.py           # FastAPI routes
  config.py         # APP_NAME, corpus version, GIS URLs, Ollama model
  toronto_data.py   # Ingest + snapshot aggregation
  legal_rag.py      # Load corpus, keyword retrieval (hackathon RAG v1)
  llm.py            # Nemotron prompts (three-section patrol brief)
  corpus/*.md       # Law/policy cards (frontmatter + body)
  static/index.html # Leaflet UI
docs/
  GORDON_II.md      # This file
  DEPLOY.md         # Shared GX10 deploy (ports, Sync SSH, teammates)
scripts/
  deploy_gx10.sh
  deploy_remote.py
```

## API (quick reference)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | `product`, `corpus_version` |
| GET | `/api/snapshot` | Toronto ops snapshot JSON |
| GET | `/api/corpus` | List law cards (debug) |
| POST | `/api/patrol-brief` | Full brief + `law_context` |
| POST | `/api/briefing` | Alias (patrol brief text + `cards_used`) |
| POST | `/api/ask` | `{ "question": "..." }` → `answer`, `law_context` |

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Requires Ollama with `nemotron3:33b` (see `app/config.py` → `OLLAMA_MODEL`).

## Deploy to Spark

See **[DEPLOY.md](./DEPLOY.md)**. Default: `~/urban-ops-copilot` on port **8080**.

```bash
./scripts/deploy_gx10.sh
# http://gx10-49d1:8080
```

**Release RAM when done:** `fuser -k 8080/tcp` on the Spark (port-scoped only).

## Law corpus (RAG v1)

- Cards live in `app/corpus/*.md` with YAML frontmatter (`id`, `title`, `category`, `source`, `tags`).
- Categories: `lookout`, `authority`, `do_not`.
- Retrieval: `app/legal_rag.py` — keyword overlap + ensure at least one `do_not` and `authority` card when possible.
- Bump `CORPUS_VERSION` in `app/config.py` when cards change.

### Add a new card

1. Create `app/corpus/my-topic.md` with frontmatter + body (educational summary, cite source).
2. Bump `CORPUS_VERSION`.
3. Test: `GET /api/corpus` and `POST /api/patrol-brief`.

### RAG v2 (next agent — suggested)

- [ ] Ollama embedding model + vector store on Spark
- [ ] NeMo Retriever or NVIDIA NIM embeddings
- [ ] Point-on-map brief: click → reverse geocode → spatial join
- [ ] cuDF aggregation for KSI × restriction joins at scale

### Voice ASR decision (demo)

- Preferred hackathon path: **NVIDIA NeMo / Parakeet ASR on PyTorch CUDA**.
- Riva / Speech NIM is the stronger production packaging story, but it adds NGC credentials and container orchestration during the hackathon.
- `faster-whisper` remains a fallback. On the current GX10 ARM64 environment, its CTranslate2 backend reports no CUDA support, so it may fall back to CPU.
- Judge framing: voice stays local to Spark either way; NeMo/Parakeet is the practical NVIDIA-native GPU path for the live demo.

## Prompt contract

`app/llm.py` forces three markdown sections. Do not remove headers without updating the UI copy.

System rules baked in:

- No precrime / profiling / automated charges
- Cite cards as `[card_id]`
- Only use snapshot + law cards provided

## Hackathon narrative

- **Track:** Urban Operations + public safety angle  
- **Toronto data:** ArcGIS RODARS layer 77, construction 71, KSI CSV (12mo window in code)  
- **NVIDIA:** Local Nemotron on 121GB unified memory; corpus RAG on Spark; room to add cuDF / NIM  

**Elevator pitch:** *Gordon II helps officers see the street clearly and stay inside the law — cited, local, on the DGX Spark.*

## Git / branches

- `master` — merged Urban Ops Copilot + deploy docs  
- `cursor/gordon-ii` — Gordon II rebrand + law RAG (active development)

## Known limitations (honest for demos)

- Law cards are **curated training summaries**, not a live statute database.
- KSI CSV may lag; not all collisions are last 90 days (see `fetch_recent_collisions(days=365)`).
- Keyword RAG is simple; legal retrieval quality improves with embeddings.
- `/api/briefing` vs `/api/patrol-brief` — prefer patrol-brief for full `law_context`.

## For the next agent — first message template

```
Continue Gordon II on branch cursor/gordon-ii.
Read docs/GORDON_II.md and docs/DEPLOY.md.
Product: lawful patrol copilot (Lookout / Authority / Do not), not vigilante AI.
Next task: [your task].
```

## Ethics checklist before shipping features

- [ ] No facial recognition or individual risk scores  
- [ ] No automated arrest/charge recommendations  
- [ ] Citations to corpus cards for legal-ish claims  
- [ ] Disclaimer visible in UI  
- [ ] Port-scoped deploy; no `pkill -f uvicorn` on shared Spark  
