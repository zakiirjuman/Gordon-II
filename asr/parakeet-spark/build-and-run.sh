#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-gordon-parakeet-asr:latest}"
CONTAINER="${CONTAINER:-gordon-parakeet-asr}"
PORT="${PORT:-8010}"
CACHE_DIR="${CACHE_DIR:-$HOME/.cache/gordon-parakeet}"

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "WARN: this image is intended for DGX Spark ARM64/aarch64." >&2
fi

if ! command -v docker >/dev/null; then
  echo "Docker is required." >&2
  exit 1
fi

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "NGC_API_KEY must be set in this shell to pull nvcr.io/nvidia/pytorch:25.11-py3." >&2
  exit 1
fi

mkdir -p "$CACHE_DIR"

echo "$NGC_API_KEY" | sudo docker login nvcr.io -u '$oauthtoken' --password-stdin
sudo docker build --progress=plain --shm-size=8g -t "$IMAGE" .

sudo docker rm -f "$CONTAINER" 2>/dev/null || true
sudo docker run -d \
  --name "$CONTAINER" \
  --runtime=nvidia \
  --gpus all \
  --shm-size=16GB \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e PARAKEET_MODEL="${PARAKEET_MODEL:-nvidia/parakeet-tdt-0.6b-v3}" \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e NCCL_P2P_DISABLE=1 \
  -p "$PORT:8000" \
  -v "$CACHE_DIR:/cache/huggingface" \
  "$IMAGE"

echo "Started $CONTAINER on http://127.0.0.1:$PORT"
echo "Watch logs: sudo docker logs -f $CONTAINER"
echo "Health: curl http://127.0.0.1:$PORT/health"
