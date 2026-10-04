from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    thread_id: str = Field(min_length=1, max_length=200)
    timestamp: datetime | None = None


class SourceReference(BaseModel):
    source: str
    page: int | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    model_used: str
    cached: bool
    sources: list[SourceReference] = Field(default_factory=list)
    processing_time_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(BaseModel):
    status: str = "healthy"
    environment: str
    version: str = "1.0.0"
    checks: dict[str, bool] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    total_requests: int = 0
    total_errors: int = 0
    error_rate: str = "0.00%"
    avg_latency_ms: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cache_hit_rate: str = "0.00%"


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None
