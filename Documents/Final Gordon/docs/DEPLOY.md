# Deploying to the shared GX10 Spark

Guide for **humans and AI agents** deploying hackathon apps to the team ASUS DGX Spark without stepping on each other.

## 1. Overview

| Item | Value |
|------|--------|
| Host | `asus@gx10-49d1` (Tailscale MagicDNS) |
| SSH user | Shared `asus` account on the Spark |
| Network | Tailscale — you must be on the team tailnet to reach the host |
| Deploy mechanism | `rsync` + remote `venv` + `uvicorn` via `scripts/deploy_remote.py` |

The GX10 is **one machine, one Linux user, many projects**. Several teammates may run FastAPI/uvicorn apps at the same time. Our deploy scripts are written to:

- Authenticate with the **NVIDIA Sync SSH key** (no interactive password in CI/agents)
- Restart **only the process listening on your chosen port** (`fuser` / `lsof`), not every uvicorn on the box

**Do not** run `pkill -f uvicorn` or similar global kills — that stops everyone else's demos.

Before first deploy, coordinate **PORT** and **REMOTE_DIR** with the team (Discord). Record your choices in the table below.

## 2. SSH setup

### NVIDIA Sync key (macOS)

After pairing the Spark with **NVIDIA Sync**, the SSH private key is usually:

```text
~/Library/Application Support/NVIDIA/Sync/config/nvsync.key
```

Override with env var `NVSYNC_KEY` if your path differs.

### Optional `~/.ssh/config` (recommended)

Add a host block so `ssh`, `rsync`, and deploy scripts can use the key without repeating `-i`:

```sshconfig
Host gx10-49d1
    HostName gx10-49d1
    User asus
    IdentityFile ~/Library/Application Support/NVIDIA/Sync/config/nvsync.key
    IdentitiesOnly yes
    StrictHostKeyChecking no
```

Then set `DEPLOY_HOST=gx10-49d1` (or keep default `asus@gx10-49d1` — both work if User/HostName match).

### Verify key auth (BatchMode)

This must succeed **without** a password prompt:

```bash
ssh -i "$HOME/Library/Application Support/NVIDIA/Sync/config/nvsync.key" \
  -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
  asus@gx10-49d1 'echo SSH_OK'
```

Expected output: `SSH_OK`

If BatchMode fails, fix Sync pairing or `~/.ssh/config` before deploying. Do not rely on password-based automation (old `pexpect` flows hang when the prompt never appears or rsync uses the wrong key).

**Initial manual access:** If Sync is not set up yet, a teammate with machine access may need to pair NVIDIA Sync once on the Mac. Avoid storing shared passwords in repo docs or scripts.

## 3. Port and directory coordination

Each project needs a **unique TCP port** and **separate remote directory** under `/home/asus/`.

| Project | `REMOTE_DIR` | `PORT` | Notes |
|---------|----------------|--------|--------|
| **urban-ops-copilot** (this repo) | `~/urban-ops-copilot` | `8080` | Default in `scripts/deploy_gx10.sh` |
| *your teammate project* | `~/your-app-name` | *pick unused* | Announce in Discord before first deploy |

### Check what is already in use (on GX10)

```bash
ssh -i "$HOME/Library/Application Support/NVIDIA/Sync/config/nvsync.key" \
  -o BatchMode=yes asus@gx10-49d1 'ss -tlnp | grep -E "808[0-9]|809[0-9]" || true'
```

Pick a port not listed. Suggested hackathon range: **8080–8099** (confirm with team).

## 4. Deploy urban-ops-copilot

From repo root on your Mac (Tailscale connected):

```bash
chmod +x scripts/deploy_gx10.sh   # once
./scripts/deploy_gx10.sh
```

Equivalent — call the Python deployer directly with env vars:

```bash
export DEPLOY_HOST="${DEPLOY_HOST:-asus@gx10-49d1}"
export REMOTE_DIR="${REMOTE_DIR:-~/urban-ops-copilot}"
export PORT="${PORT:-8080}"
export NVSYNC_KEY="${NVSYNC_KEY:-$HOME/Library/Application Support/NVIDIA/Sync/config/nvsync.key}"

python3 scripts/deploy_remote.py
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEPLOY_HOST` | `asus@gx10-49d1` | SSH/rsync target |
| `REMOTE_DIR` | `~/urban-ops-copilot` | Remote app tree (rsync destination) |
| `PORT` | `8080` | uvicorn listen port; only this port is stopped before start |
| `NVSYNC_KEY` | Sync path above | Private key for non-interactive SSH |

Example — **do not** use these for urban-ops unless team reassigns; illustrates a second app:

```bash
REMOTE_DIR=~/other-demo PORT=8081 ./scripts/deploy_gx10.sh
```

### What the script does

1. `rsync` project to `REMOTE_DIR` (excludes `.git`, `__pycache__`, `.venv`)
2. Create remote `.venv` if missing; `pip install -r requirements.txt`
3. Stop listener on **your** `PORT` only (`fuser -k PORT/tcp`, `lsof`)
4. Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT` in background (`urban-ops.log`)
5. Poll `http://127.0.0.1:$PORT/api/health` on the Spark

## 5. What success looks like

Script ends with `SUCCESS` and prints the Tailscale URL.

**Health** (from your Mac):

```bash
curl -s http://gx10-49d1:8080/api/health
# {"status":"ok"}
```

**Snapshot** (first call may take ~30s while CSVs download):

```bash
curl -s http://gx10-49d1:8080/api/snapshot | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['counts'])"
```

**Browser:** [http://gx10-49d1:8080](http://gx10-49d1:8080) (Tailscale)

Briefing endpoints need Ollama (see §8).

## 6. Troubleshooting

### Deploy hangs or times out

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| Stuck at rsync | SSH using wrong key; waiting for password | Use Sync key + `BatchMode=yes` verify command (§2) |
| `rsync` / `ssh: Could not resolve hostname .../nvsync.key` | Spaces in key path not quoted | Use current `scripts/deploy_remote.py` (quotes `-e ssh`) |
| `mkdir: missing operand` | Old pattern: `ssh host bash -lc mkdir ...` split argv | Use latest deploy script (single remote command string) |
| Hang after "Starting uvicorn" | SSH waiting on background job stdio | Fixed via `sh -c '... </dev/null >urban-ops.log 2>&1 &'` |

### App not healthy

On the Spark:

```bash
ssh -i "$HOME/Library/Application Support/NVIDIA/Sync/config/nvsync.key" -o BatchMode=yes \
  asus@gx10-49d1 'tail -40 $HOME/urban-ops-copilot/urban-ops.log'
```

Check port binding:

```bash
ssh ... asus@gx10-49d1 'ss -tlnp | grep 8080'
```

Free **your** port only (if a stale process blocks redeploy):

```bash
ssh ... asus@gx10-49d1 'fuser -k 8080/tcp 2>/dev/null || true'
```

Replace `8080` with your `PORT`.

### Briefing / ask returns errors

- Confirm Ollama is running on GX10: `curl -s http://127.0.0.1:11434/api/tags`
- Model must be pulled: `nemotron3:33b` (see §8)

## 7. Rules for AI agents

1. **Never** `pkill -f uvicorn` or kill all Python/uvicorn on GX10.
2. **Only** stop the process bound to **your** `PORT` (deploy script already does this).
3. **Always** use NVIDIA Sync key or `~/.ssh/config` — not password/`pexpect` deploy paths.
4. **Set and announce** `PORT` + `REMOTE_DIR` in Discord before first deploy; update the coordination table in this doc or team wiki.
5. **Read** `scripts/deploy_remote.py` before changing deploy behavior; keep rsync SSH quoting correct for paths with spaces.
6. **Verify** with `curl` health + snapshot (or project-specific checks) after deploy.
7. **Do not** commit `.venv`, secrets, or shared passwords to the repo.

## 8. Ollama (briefing endpoints)

Urban Ops Copilot calls **local Ollama** on the Spark for:

- `POST /api/briefing` — morning ops briefing
- `POST /api/ask` — natural-language Q&A

Config (`app/config.py`):

- URL: `http://127.0.0.1:11434`
- Model: `nemotron3:33b`

On GX10 (once per machine or after reset):

```bash
ollama pull nemotron3:33b
```

Sanity check:

```bash
curl -s http://gx10-49d1:8080/api/health          # app up
curl -s http://127.0.0.1:11434/api/tags          # run on Spark via SSH
```

Change model via `OLLAMA_MODEL` in `app/config.py` only if the team agrees (memory footprint on 121GB unified memory).

---

**Quick links:** [README](../README.md) · `scripts/deploy_gx10.sh` · `scripts/deploy_remote.py`
