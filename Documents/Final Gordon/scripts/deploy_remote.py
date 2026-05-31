#!/usr/bin/env python3
"""Deploy urban-ops-copilot to GX10 over SSH (NVIDIA Sync key preferred)."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOST = os.environ.get("DEPLOY_HOST", "asus@gx10-49d1")
_REMOTE_DIR_RAW = os.environ.get("REMOTE_DIR", "~/urban-ops-copilot")
PORT = int(os.environ.get("PORT", "8080"))


def _expand_remote_dir(path: str) -> str:
    if path.startswith("~/"):
        return f"$HOME/{path[2:]}"
    return path


REMOTE_DIR = _expand_remote_dir(_REMOTE_DIR_RAW)

NVSYNC_KEY = Path(
    os.environ.get(
        "NVSYNC_KEY",
        os.path.expanduser(
            "~/Library/Application Support/NVIDIA/Sync/config/nvsync.key"
        ),
    )
)

SSH_BASE = [
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "ConnectTimeout=15",
]
if NVSYNC_KEY.is_file():
    SSH_BASE.extend(["-i", str(NVSYNC_KEY), "-o", "BatchMode=yes"])
else:
    print(f"WARN: NVIDIA Sync key not found at {NVSYNC_KEY}; SSH may prompt for a password", file=sys.stderr)


def ssh_cmd(remote_command: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    # One remote command string — do not pass bash -lc as separate argv (ssh splits them).
    return subprocess.run(
        ["ssh", *SSH_BASE, HOST, remote_command],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def rsync_tree() -> None:
    ssh_for_rsync = " ".join(shlex.quote(x) for x in ["ssh", *SSH_BASE])
    cmd = [
        "rsync",
        "-avz",
        "--delete",
        "-e",
        ssh_for_rsync,
        "--exclude",
        ".git",
        "--exclude",
        "__pycache__",
        "--exclude",
        ".venv",
        f"{ROOT}/",
        f"{HOST}:{_REMOTE_DIR_RAW}/",
    ]
    print("RUN:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(f"rsync failed (exit {result.returncode})")


def stop_port_listener() -> None:
    # Kill only whatever is bound to this app's port (not all uvicorn processes).
    stop = (
        f"fuser -k {PORT}/tcp 2>/dev/null || true; "
        f"command -v lsof >/dev/null && lsof -ti :{PORT} | xargs -r kill -9 2>/dev/null || true"
    )
    ssh_cmd(stop, timeout=30)


def main() -> int:
    print(f"Deploy target: {HOST}:{REMOTE_DIR} (port {PORT})")
    if NVSYNC_KEY.is_file():
        print(f"SSH key: {NVSYNC_KEY}")
    else:
        print("SSH key: (default agent / ~/.ssh/config)")

    try:
        print(f"Syncing {ROOT} -> {HOST}:{REMOTE_DIR}")
        rsync_tree()
    except subprocess.TimeoutExpired:
        print("FAIL: rsync timed out (often stuck waiting for SSH password — use NVIDIA Sync key)", file=sys.stderr)
        return 1
    except SystemExit as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    steps = [
        (f"mkdir -p {REMOTE_DIR}", 30),
        (f"cd {REMOTE_DIR} && test -d .venv || python3 -m venv .venv", 120),
        (f"cd {REMOTE_DIR} && .venv/bin/pip install -q -r requirements.txt", 300),
    ]
    for step, timeout in steps:
        print(f"RUN: {step}")
        proc = ssh_cmd(step, timeout=timeout)
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.returncode != 0:
            print(f"FAIL: remote step exited {proc.returncode}", file=sys.stderr)
            if proc.stderr.strip():
                print(proc.stderr.strip(), file=sys.stderr)
            return 1

    print(f"Stopping listener on port {PORT} only...")
    stop_port_listener()

    start = (
        f"sh -c 'cd {REMOTE_DIR} && "
        f"nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port {PORT} "
        f"</dev/null >urban-ops.log 2>&1 &'"
    )
    print(f"RUN: {start}")
    proc = ssh_cmd(start, timeout=60)
    if proc.returncode != 0:
        print(f"FAIL: could not start uvicorn (exit {proc.returncode})", file=sys.stderr)
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        return 1

    health_url = f"http://127.0.0.1:{PORT}/api/health"
    print(f"Waiting for {health_url} ...")
    healthy = False
    for attempt in range(1, 13):
        time.sleep(2)
        proc = ssh_cmd(f"curl -s --max-time 5 {health_url} || true", timeout=20)
        body = (proc.stdout or "").strip()
        if "ok" in body:
            print(f"Health OK (attempt {attempt}): {body}")
            healthy = True
            break
    if not healthy:
        log = ssh_cmd(f"tail -40 {REMOTE_DIR}/urban-ops.log || true", timeout=20)
        print("FAIL: health check did not return ok", file=sys.stderr)
        print(log.stdout or "(no log output)", file=sys.stderr)
        return 1

    print("Fetching snapshot counts (may take ~30s on first CSV download)...")
    snap = ssh_cmd(
        f"curl -s --max-time 120 http://127.0.0.1:{PORT}/api/snapshot | "
        "python3 -c \"import sys,json; print(json.load(sys.stdin)['counts'])\"",
        timeout=150,
    )
    if snap.returncode != 0 or not snap.stdout.strip():
        print("WARN: snapshot fetch failed", file=sys.stderr)
        if snap.stderr.strip():
            print(snap.stderr.strip(), file=sys.stderr)
    else:
        print("Snapshot counts:", snap.stdout.strip())

    proc = ssh_cmd(f"ss -tlnp | grep ':{PORT}' || true; pgrep -af 'port {PORT}' || true", timeout=20)
    if proc.stdout.strip():
        print("Listener:", proc.stdout.strip())

    public_url = f"http://gx10-49d1:{PORT}"
    print(f"\nSUCCESS: deployed to {HOST}:{REMOTE_DIR}")
    print(f"Open {public_url} over Tailscale")
    return 0


if __name__ == "__main__":
    sys.exit(main())
