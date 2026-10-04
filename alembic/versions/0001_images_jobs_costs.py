"""Images, vision tags, jobs and the AI cost log (Phase 2).

Posts, embeddings, suggestions and reviews arrive in later migrations (Phases 3-4).

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.CheckConstraint(
            "status IN ('pending', 'tagged', 'flagged', 'failed')", name="status_allowed"
        ),
    )
    op.create_index("ix_images_status", "images", ["status"])
    op.create_index("ix_images_filename", "images", ["filename"])

    op.create_table(
        "image_tags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "image_id", sa.Integer, sa.ForeignKey("images.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("subject_key", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(60), nullable=False),
        sa.Column("attributes", JSONB, nullable=False),
        sa.Column("caption", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("raw_response", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.UniqueConstraint("image_id", "model", name="uq_image_tags_image_model"),
    )
    op.create_index("ix_image_tags_category_subject", "image_tags", ["category", "subject_key"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text),
        sa.Column("progress_done", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(128), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')", name="status_allowed"
        ),
    )
    # The worker's claim query filters on exactly these two columns
    op.create_index("ix_jobs_status_run_after", "jobs", ["status", "run_after"])

    op.create_table(
        "ai_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("owner_type", sa.String(16)),
        sa.Column("owner_id", sa.Integer),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("thinking_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("response_text", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.CheckConstraint(
            "outcome IN ('ok', 'invalid_output', 'rate_limited', 'error')", name="outcome_allowed"
        ),
    )
    op.create_index("ix_ai_calls_created_at", "ai_calls", ["created_at"])
    op.create_index("ix_ai_calls_purpose", "ai_calls", ["purpose"])


def downgrade() -> None:
    op.drop_table("ai_calls")
    op.drop_table("jobs")
    op.drop_table("image_tags")
    op.drop_table("images")
