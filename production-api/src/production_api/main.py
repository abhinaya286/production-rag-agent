import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool

from production_api.agent import ProductionAgent
from production_api.cache import ResponseCache
from production_api.config import get_settings
from production_api.models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
)
from production_api.monitoring import MetricsCollector, RequestTimer, get_logger
from production_api.security import SecurityPipeline

logger = get_logger("production_api")
limiter = Limiter(key_func=get_remote_address)


def require_api_access(authorization: str | None = Header(default=None)) -> None:
    configured_token = get_settings().api_access_token
    if (
        configured_token is None
        or not configured_token.get_secret_value().strip()
    ):
        return

    expected = configured_token.get_secret_value()
    scheme, _, provided = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_rag_configuration()
    os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    app.state.security = SecurityPipeline()
    app.state.cache = ResponseCache(expiration=settings.cache_ttl_seconds)
    app.state.metrics = MetricsCollector()
    app.state.agent = ProductionAgent()
    logger.info(
        "Production RAG API started",
        extra={
            "extra_data": {
                "environment": settings.app_env,
                "model": settings.primary_model,
                "vector_collection": settings.vector_collection_name,
            }
        },
    )
    yield
    logger.info("Production RAG API stopped")


app = FastAPI(
    title="Production RAG API",
    description="Grounded question answering over an ingested document collection.",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, _exc: RateLimitExceeded):
    logger.warning(
        "Request rate limit exceeded",
        extra={
            "extra_data": {
                "path": _request.url.path,
                "limit": str(_exc.detail),
            }
        },
    )
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(require_api_access)],
)
@limiter.limit(get_settings().rate_limit)
async def chat(request: Request, body: ChatRequest):
    with RequestTimer() as timer:
        security = request.app.state.security
        cache = request.app.state.cache
        metrics = request.app.state.metrics
        is_allowed, cleaned_message, notes = security.check_input(body.message)
        if not is_allowed:
            logger.warning(
                "Request blocked by security pipeline",
                extra={"extra_data": notes, "thread_id": body.thread_id},
            )
            metrics.record_request(latency_ms=timer.elapsed_ms, error=True)
            raise HTTPException(status_code=400, detail="Request blocked by security check.")
        if not cleaned_message:
            metrics.record_request(latency_ms=timer.elapsed_ms, error=True)
            raise HTTPException(status_code=400, detail="Message must not be empty.")

        cached = cache.get(cleaned_message)
        if cached is not None:
            metrics.record_request(
                latency_ms=timer.elapsed_ms,
                input_tokens=0,
                output_tokens=0,
                cache_hit=True,
            )
            return ChatResponse(
                response=cached["response"],
                thread_id=body.thread_id,
                model_used=cached["model_used"],
                cached=True,
                sources=cached["sources"],
                processing_time_ms=timer.elapsed_ms,
            )

        try:
            result = await run_in_threadpool(
                request.app.state.agent.invoke,
                cleaned_message,
            )
        except Exception as exc:
            metrics.record_request(latency_ms=timer.elapsed_ms, error=True)
            logger.exception(
                "RAG request failed",
                extra={"extra_data": notes, "thread_id": body.thread_id},
            )
            raise HTTPException(
                status_code=503,
                detail="The RAG service could not complete the request.",
            ) from exc

        safe_response, output_warnings = security.check_output(result["response"])

        response_sources = result["sources"]
        cache_value = {
            "response": safe_response,
            "model_used": result["model_used"],
            "sources": response_sources,
        }
        cache.set(cleaned_message, cache_value)
        metrics.record_request(
            latency_ms=timer.elapsed_ms,
            input_tokens=max(1, int(len(cleaned_message.split()) * 1.3)),
            output_tokens=max(1, int(len(safe_response.split()) * 1.3)),
            cache_hit=False,
        )
        if notes or output_warnings:
            logger.info(
                "Security checks completed with notes",
                extra={
                    "extra_data": notes + output_warnings,
                    "thread_id": body.thread_id,
                },
            )

        return ChatResponse(
            response=safe_response,
            thread_id=body.thread_id,
            model_used=result["model_used"],
            cached=False,
            sources=response_sources,
            processing_time_ms=timer.elapsed_ms,
        )


@app.get("/health", response_model=HealthResponse)
async def health(request: Request):
    settings = get_settings()
    checks = {
        "agent": getattr(request.app.state, "agent", None) is not None,
        "security": getattr(request.app.state, "security", None) is not None,
        "cache": getattr(request.app.state, "cache", None) is not None,
    }
    return HealthResponse(
        status="healthy" if all(checks.values()) else "degraded",
        environment=settings.app_env,
        checks=checks,
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics(request: Request):
    return request.app.state.metrics.get_summary()


@app.get("/cache/stats")
async def cache_stats(request: Request):
    return request.app.state.cache.get_stats()
