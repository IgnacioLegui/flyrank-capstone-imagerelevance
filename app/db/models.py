"""SQLAlchemy models. The schema itself is created by Alembic migrations (alembic/versions/),
never by `create_all`, so every change is versioned. `alembic check` verifies the two agree.

Status-like columns are plain strings guarded by CHECK constraints rather than Postgres ENUM
types: same safety (the DB rejects unknown values), simpler migrations when a value is added.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

IMAGE_STATUSES = ("pending", "tagged", "flagged", "failed")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")
CALL_OUTCOMES = ("ok", "invalid_output", "rate_limited", "error")


def _check_in(column: str, values: tuple[str, ...]) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_allowed")


class Base(DeclarativeBase):
    pass


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        _check_in("status", IMAGE_STATUSES),
        Index("ix_images_status", "status"),
        Index("ix_images_filename", "filename"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    # Content hash: the same file registered twice is the same row -> re-running ingest is idempotent
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    error: Mapped[str | None] = mapped_column(Text)  # why it failed, when status = failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tags: Mapped[list["ImageTag"]] = relationship(back_populates="image")


class ImageTag(Base):
    """One validated vision result per image per model."""

    __tablename__ = "image_tags"
    __table_args__ = (
        UniqueConstraint("image_id", "model", name="uq_image_tags_image_model"),
        Index("ix_image_tags_category_subject", "category", "subject_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    subject_key: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(60))
    attributes: Mapped[list[str]] = mapped_column(JSONB)
    caption: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB)  # the model's JSON, as received
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    image: Mapped[Image] = relationship(back_populates="tags")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        _check_in("status", JOB_STATUSES),
        Index("ix_jobs_status_run_after", "status", "run_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    progress_done: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    progress_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Same key twice -> same job, so a retried POST doesn't start a second batch
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AICall(Base):
    """Cost log: one row per Gemini request, successful or not."""

    __tablename__ = "ai_calls"
    __table_args__ = (
        _check_in("outcome", CALL_OUTCOMES),
        Index("ix_ai_calls_created_at", "created_at"),
        Index("ix_ai_calls_purpose", "purpose"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    purpose: Mapped[str] = mapped_column(String(32))  # vision_tag, embed_image, embed_post, ...
    model: Mapped[str] = mapped_column(String(64))
    owner_type: Mapped[str | None] = mapped_column(String(16))  # image / post
    owner_id: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    thinking_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Paid-tier list-price equivalent (we use the free tier). Numeric, not float: money adds exactly.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=0, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    response_text: Mapped[str | None] = mapped_column(Text)  # raw model output, for inspection
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
