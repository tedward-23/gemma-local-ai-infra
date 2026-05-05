from time import perf_counter
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from app.config import get_settings

REQUEST_COUNT = Counter(
    "gemma_api_requests_total",
    "Total API requests by path, method, and status.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "gemma_api_request_latency_seconds",
    "API request latency by path and method.",
    ["method", "path"],
)
GENERATED_TOKENS = Counter(
    "gemma_generated_tokens_total",
    "Total generated tokens reported by Ollama.",
    ["model"],
)
GENERATION_LATENCY = Histogram(
    "gemma_generation_latency_seconds",
    "End-to-end model generation latency.",
    ["model"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=12000)
    system: str | None = Field(default=None, max_length=4000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=256, ge=1, le=4096)


class GenerateResponse(BaseModel):
    model: str
    response: str
    total_duration_ms: float | None
    prompt_eval_count: int | None
    eval_count: int | None
    tokens_per_second: float | None


app = FastAPI(
    title="Gemma Local AI Infrastructure API",
    description="Local Gemma model serving API with Docker, Ollama, and Prometheus metrics.",
    version="0.1.0",
)


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    start = perf_counter()
    path = request.url.path
    method = request.method
    try:
        response = await call_next(request)
    except Exception:
        REQUEST_COUNT.labels(method=method, path=path, status="500").inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(perf_counter() - start)
        raise

    REQUEST_COUNT.labels(method=method, path=path, status=str(response.status_code)).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(perf_counter() - start)
    return response


def ollama_timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(settings.request_timeout_seconds)


async def get_ollama_models() -> list[str]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=ollama_timeout()) as client:
        response = await client.get(f"{settings.ollama_base_url}/api/tags")
        response.raise_for_status()
        payload = response.json()

    return sorted(model.get("name", "") for model in payload.get("models", []) if model.get("name"))


@app.get("/health")
async def health() -> JSONResponse:
    settings = get_settings()
    try:
        models = await get_ollama_models()
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "ollama": "unreachable", "error": str(exc)},
        )

    return JSONResponse(
        content={
            "status": "ok",
            "ollama": "reachable",
            "configured_model": settings.ollama_model,
            "model_count": len(models),
        }
    )


@app.get("/ready")
async def ready() -> JSONResponse:
    settings = get_settings()
    try:
        models = await get_ollama_models()
    except httpx.HTTPError as exc:
        return JSONResponse(status_code=503, content={"ready": False, "error": str(exc)})

    model_ready = settings.ollama_model in models
    return JSONResponse(
        status_code=200 if model_ready else 503,
        content={"ready": model_ready, "configured_model": settings.ollama_model, "models": models},
    )


@app.get("/models")
async def models() -> dict[str, list[str]]:
    return {"models": await get_ollama_models()}


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "prompt": request.prompt,
        "stream": False,
        "options": {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        },
    }
    if request.system:
        payload["system"] = request.system

    started = perf_counter()
    async with httpx.AsyncClient(timeout=ollama_timeout()) as client:
        response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
        response.raise_for_status()
        ollama_payload = response.json()

    duration_seconds = perf_counter() - started
    GENERATION_LATENCY.labels(model=settings.ollama_model).observe(duration_seconds)

    eval_count = ollama_payload.get("eval_count")
    eval_duration_ns = ollama_payload.get("eval_duration")
    if isinstance(eval_count, int):
        GENERATED_TOKENS.labels(model=settings.ollama_model).inc(eval_count)

    tokens_per_second = None
    if isinstance(eval_count, int) and isinstance(eval_duration_ns, int) and eval_duration_ns > 0:
        tokens_per_second = eval_count / (eval_duration_ns / 1_000_000_000)

    total_duration_ms = None
    total_duration_ns = ollama_payload.get("total_duration")
    if isinstance(total_duration_ns, int):
        total_duration_ms = total_duration_ns / 1_000_000

    return GenerateResponse(
        model=settings.ollama_model,
        response=ollama_payload.get("response", ""),
        total_duration_ms=total_duration_ms,
        prompt_eval_count=ollama_payload.get("prompt_eval_count"),
        eval_count=eval_count,
        tokens_per_second=tokens_per_second,
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
