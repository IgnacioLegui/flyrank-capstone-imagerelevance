"""Job queue on top of the `jobs` table.

How a worker takes a job without two workers ever taking the same one:

    SELECT ... FROM jobs
    WHERE status = 'queued' AND run_after <= now()
    ORDER BY run_after, id
    LIMIT 1
    FOR UPDATE SKIP LOCKED

FOR UPDATE locks the chosen row until the transaction ends; SKIP LOCKED makes any other worker
skip rows that are already locked instead of waiting for them. The row is then switched to
'running' in the same transaction, so after commit it no longer matches status = 'queued'.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Job

INGEST_IMAGES = "ingest_images"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_job(
    session: Session, job_type: str, payload: dict[str, Any], idempotency_key: str | None = None
) -> tuple[Job, bool]:
    """Returns (job, created). Same idempotency key twice -> the existing job, created=False."""
    if idempotency_key is not None:
        existing = session.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing is not None:
            return existing, False
    job = Job(type=job_type, payload=payload, idempotency_key=idempotency_key)
    session.add(job)
    session.flush()  # assigns job.id
    return job, True


def claim_next(session: Session) -> Job | None:
    """Lock and mark 'running' the next due job, or return None. Caller commits."""
    job = session.scalar(
        select(Job)
        .where(Job.status == "queued", Job.run_after <= _now())
        .order_by(Job.run_after, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is not None:
        job.status = "running"
        job.started_at = _now()
    return job


def requeue_running(session: Session) -> int:
    """At worker start-up: jobs still 'running' belong to a worker that died mid-job.
    (We run a single worker, so every 'running' job at start-up is orphaned.)"""
    result = session.execute(
        update(Job).where(Job.status == "running").values(status="queued", run_after=_now())
    )
    return result.rowcount


def set_progress(session: Session, job_id: int, done: int, total: int) -> None:
    session.execute(update(Job).where(Job.id == job_id).values(progress_done=done, progress_total=total))


def mark_succeeded(session: Session, job_id: int) -> None:
    session.execute(
        update(Job).where(Job.id == job_id).values(status="succeeded", finished_at=_now(), last_error=None)
    )


def mark_failed(session: Session, job_id: int, error: str) -> None:
    session.execute(
        update(Job).where(Job.id == job_id).values(status="failed", finished_at=_now(), last_error=error)
    )


def requeue(session: Session, job_id: int, delay: timedelta, reason: str, count_attempt: bool) -> None:
    """Put the job back in the queue to run again after `delay`.
    count_attempt=True for crashes (limited by max_attempts); False for rate-limit pauses."""
    values: dict[str, Any] = {"status": "queued", "run_after": _now() + delay, "last_error": reason}
    if count_attempt:
        values["attempts"] = Job.attempts + 1
    session.execute(update(Job).where(Job.id == job_id).values(**values))
