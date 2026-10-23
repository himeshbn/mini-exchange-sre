# Mini Exchange SRE

A learning project for order matching, reliability engineering,
observability, SLOs, fault injection, and blameless post-mortems.

## Architecture

- FastAPI: order submission, order book, health check
- In-memory matching engine: price-time priority
- pytest: automated correctness tests
- Docker Compose: local container runtime

## Prerequisites

- Python 3.12 or compatible environment
- Docker and Docker Compose

## Run locally

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
python -m uvicorn app.main:app --reload --port 8000

API documentation: http://127.0.0.1:8000/docs

## Run with Docker

docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8000/health
docker compose down

## Current limitations

- Orders are held in memory.
- State is lost when the process restarts.
- No authentication, persistence, or exchange-grade guarantees.
- SLOs and monitoring will be added in subsequent phases.
