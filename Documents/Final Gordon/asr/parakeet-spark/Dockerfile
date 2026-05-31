FROM nvcr.io/nvidia/pytorch:25.11-py3

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PARAKEET_MODEL=nvidia/parakeet-tdt-0.6b-v3 \
    HF_HOME=/cache/huggingface \
    TRANSFORMERS_CACHE=/cache/huggingface \
    CUDA_VISIBLE_DEVICES=0 \
    NCCL_P2P_DISABLE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 libsndfile1-dev sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/parakeet

COPY requirements.txt .
RUN pip install --break-system-packages --no-cache-dir -r requirements.txt

COPY app/ /opt/parakeet/app/

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
