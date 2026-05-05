# Gemma Local AI Infrastructure Lab

Local Gemma model serving with a small production-style platform around it: a FastAPI inference gateway, Ollama model runtime, Prometheus metrics, Grafana, readiness checks, and a benchmark script.

This is meant to show practical AI infrastructure work, not only a notebook. It demonstrates how a model can be packaged behind an API, observed, tested locally, and later moved to Kubernetes or a cloud GPU/CPU target.

## Architecture

```text
Client / benchmark script
        |
        v
FastAPI inference API  --->  Prometheus / Grafana
        |
        v
Ollama runtime
        |
        v
Gemma model
```

## What This Shows

- Local LLM serving with Ollama and Gemma.
- A reusable inference API instead of direct terminal prompts.
- Health and readiness endpoints for deployment environments.
- Prometheus metrics for request volume, latency, and generated tokens.
- A repeatable Docker Compose setup that can evolve into Kubernetes, Terraform, and cloud deployment.

## Run Locally

Copy the example environment file:

```sh
cp .env.example .env
```

Start the stack:

```sh
docker compose up --build -d
```

Pull the default Gemma model:

```sh
docker compose run --rm ollama-model-init
```

The default model is [`gemma3:1b`](https://ollama.com/library/gemma3), which Ollama lists as an 815 MB text model with a 32K context window. That keeps the first local demo MacBook-friendly. To use a larger model, change `OLLAMA_MODEL` in `.env`.

## Test The API

Check service health:

```sh
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Generate text:

```sh
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain local AI model serving in three concise bullets.","max_tokens":128}'
```

Run a small benchmark:

```sh
python3 scripts/benchmark.py --requests 10 --concurrency 2
```

## Local URLs

- API docs: http://localhost:8000/docs
- API metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana login defaults to `admin` / `admin` unless `GRAFANA_ADMIN_PASSWORD` is changed.

## Portfolio Framing

This project is a good replacement for a basic learning-notes repository because it has an actual runnable system. It connects DevOps experience with AI infrastructure: model serving, container orchestration, observability, benchmarking, and deployment readiness.

## Next Improvements

- Add Kubernetes manifests or a Helm chart.
- Add Terraform for cloud deployment.
- Add OpenTelemetry traces.
- Add model evaluation prompts and regression tests.
- Add a GitHub Actions pipeline for lint, build, and container scan.
- Add GPU profile support for cloud or local acceleration.
