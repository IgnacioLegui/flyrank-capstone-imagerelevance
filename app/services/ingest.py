"""The `ingest_images` batch job: register the corpus, then tag every pending image.

Resumable by design: progress is recomputed from the database each round (how many images in
this job's scope are no longer 'pending'), so a job that was paused for rate limits — or a worker
that crashed — picks up exactly where it left off, and never re-tags a finished image.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.ai.gemini import BudgetExceeded, CallContext, GeminiCallError, RateLimited
from app.config import Settings
from app.db.models import Image
from app.db.session import session_scope
from app.repositories import images as images_repo
from app.repositories import jobs as jobs_repo
from app.services.tagging import Tagger, tag_one

log = logging.getLogger("worker.ingest")

BACKOFF_SECONDS = (30, 60, 120)  # waits after 1st, 2nd, 3rd+ consecutive 429 without retryDelay
MAX_CONSECUTIVE_429 = 5  # then assume the daily quota is gone and pause the job
DAILY_QUOTA_PAUSE = timedelta(hours=1)


class CorpusError(Exception):
    pass


@dataclass
class JobInfo:
    id: int
    payload: dict[str, Any]


def list_corpus(images_dir: Path, only: list[str] | None) -> list[Path]:
    """The .jpg files this job should process. Missing or empty folder is an error, never a
    silent 'success with 0 images'."""
    if not images_dir.is_dir():
        raise CorpusError(f"IMAGES_DIR does not exist or is not a folder: {images_dir}")
    files = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() == ".jpg")
    if not files:
        raise CorpusError(f"IMAGES_DIR contains no .jpg images: {images_dir}")
    if only:
        names = {p.name for p in files}
        unknown = sorted(set(only) - names)
        if unknown:
            raise CorpusError(f"requested images not found in IMAGES_DIR: {', '.join(unknown)}")
        files = [p for p in files if p.name in set(only)]
    return files


def fail_job(job_id: int, error: str) -> None:
    """The failure alert: job marked failed + an ERROR log line that names the job and the reason."""
    with session_scope() as s:
        jobs_repo.mark_failed(s, job_id, error)
    log.error("ALERT job %s failed: %s", job_id, error)


def run_ingest_job(
    job: JobInfo,
    settings: Settings,
    make_tagger: Callable[[], Tagger],
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    try:
        files = list_corpus(settings.images_dir, job.payload.get("only"))
    except CorpusError as e:
        fail_job(job.id, str(e))
        return

    with session_scope() as s:
        new = images_repo.register_files(s, files)
    log.info("job %s: %d image(s) in scope, %d newly registered", job.id, len(files), new)

    try:
        tagger = make_tagger()
    except GeminiCallError as e:  # e.g. GEMINI_API_KEY missing: retrying can't fix it
        fail_job(job.id, str(e))
        return

    names = [p.name for p in files]
    consecutive_429 = 0
    while True:
        with session_scope() as s:
            scope = images_repo.images_in_scope(s, names)
            pending = [img for img in scope if img.status == "pending"]
            jobs_repo.set_progress(s, job.id, done=len(scope) - len(pending), total=len(scope))
        if not pending:
            break

        image = pending[0]
        ctx = CallContext(purpose="vision_tag", job_id=job.id, owner_type="image", owner_id=image.id)
        image_bytes = (settings.images_dir / image.filename).read_bytes()
        try:
            outcome = tag_one(image_bytes, tagger, ctx, settings.min_confidence)
        except RateLimited as e:
            consecutive_429 += 1
            if consecutive_429 >= MAX_CONSECUTIVE_429:
                with session_scope() as s:
                    jobs_repo.requeue(
                        s, job.id, DAILY_QUOTA_PAUSE,
                        f"{consecutive_429} consecutive 429s, quota likely exhausted; paused",
                        count_attempt=False,
                    )
                log.warning("job %s paused for %s after %d consecutive 429s",
                            job.id, DAILY_QUOTA_PAUSE, consecutive_429)
                return
            wait = e.retry_after or BACKOFF_SECONDS[min(consecutive_429, len(BACKOFF_SECONDS)) - 1]
            log.warning("job %s: 429 on %s, waiting %.0fs (%d in a row)",
                        job.id, image.filename, wait, consecutive_429)
            sleep(wait)
            continue
        except BudgetExceeded as e:
            fail_job(job.id, str(e))
            return

        consecutive_429 = 0
        with session_scope() as s:
            row = s.get(Image, image.id)
            t = outcome.tags
            images_repo.save_outcome(s, row, tagger.model, outcome.status, outcome.error, t, outcome.raw_text)
        log.info(
            "job %s: %s -> %s%s", job.id, image.filename, outcome.status,
            f" ({t.subject_key.value}, confidence {t.confidence:.2f})" if t else f" ({outcome.error})",
        )

    with session_scope() as s:
        jobs_repo.mark_succeeded(s, job.id)
    log.info("job %s succeeded", job.id)
