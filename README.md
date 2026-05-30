# NvidiaZakathon

Toronto 311 public services demo for the NVIDIA Spark Hack Series — built to run locally on the ASUS DGX Spark (GX10).

## Stack (planned)

- **Data:** City of Toronto 311 service request open data
- **Backend:** FastAPI on the Spark
- **AI:** Local Nemotron via Ollama for request classification and triage
- **Frontend:** Ward map + trend dashboard

## Hardware target

- ASUS GX10 (`gx10-49d1`) over Tailscale
- 121 GB unified memory, NVIDIA GB10, Ollama with Nemotron models preloaded

## Getting started

```bash
git clone git@github.com:zakiirjuman/NvidiaZakathon.git
cd NvidiaZakathon
```
