"""HTTP response shapes. Separate from the DB models so the API contract doesn't change by accident
when a table gains a column (e.g. raw model output is only shown on the single-image endpoint)."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ImageStatus(StrEnum):
    pending = "pending"
    tagged = "tagged"
    flagged = "flagged"
    failed = "failed"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class _FromOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobOut(_FromOrm):
    id: int
    type: str
    status: JobStatus
    progress_done: int
    progress_total: int
    attempts: int
    max_attempts: int
    run_after: datetime
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None
    created_at: datetime


class TagsOut(_FromOrm):
    model: str
    category: str
    subject_key: str
    subject: str
    attributes: list[str]
    caption: str
    confidence: float


class ImageOut(_FromOrm):
    id: int
    filename: str
    status: ImageStatus
    error: str | None  # failed: last error; flagged: why it was flagged
    tags: list[TagsOut]


class CallOut(_FromOrm):
    id: int
    created_at: datetime
    job_id: int | None
    purpose: str
    model: str
    owner_type: str | None
    owner_id: int | None
    outcome: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: Decimal
    latency_ms: int | None
    error: str | None


class CallDetailOut(CallOut):
    response_text: str | None


class TagsDetailOut(TagsOut):
    raw_response: dict[str, Any]


class ImageDetailOut(ImageOut):
    sha256: str
    tags: list[TagsDetailOut]
    calls: list[CallDetailOut]  # every Gemini request made for this image, with raw output


class CostTotal(BaseModel):
    purpose: str
    model: str
    calls: int
    ok: int
    invalid_output: int
    rate_limited: int
    error: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: Decimal


class CostsOut(BaseModel):
    note: str
    total_calls: int
    total_cost_usd: Decimal
    budget_usd: float
    by_purpose_and_model: list[CostTotal]
    calls: list[CallOut]
