"""Background worker: claims jobs from Postgres and runs them, one at a time.

    python -m worker.main

Slow AI work happens only here, never inside an HTTP request. If a job crashes unexpectedly it is
retried with a growing delay, up to the job's max_attempts; after that it is marked failed and an
ERROR "ALERT" line is logged.
"""

import logging
import time
from datetime import timedelta

from app.ai.gemini import GeminiVision, make_client
from app.ai.pacing import Pacer
from app.config import Settings, get_settings
from app.db.session import session_scope
from app.repositories import jobs as jobs_repo
from app.repositories.ai_calls import DbCostLog
from app.services.ingest import JobInfo, fail_job, run_ingest_job

log = logging.getLogger("worker")

POLL_SECONDS = 2.0


def make_tagger(settings: Settings) -> GeminiVision:
    return GeminiVision(
        client=make_client(settings),
        model=settings.vision_model,
        cost_log=DbCostLog(),
        budget_usd=settings.ai_budget_usd,
        pacer=Pacer(settings.gemini_rpm),
    )


def run_one(settings: Settings) -> bool:
    """Claim and run one due job. Returns False if there was nothing to do."""
    with session_scope() as s:
        job = jobs_repo.claim_next(s)
        if job is None:
            return False
        info = JobInfo(id=job.id, payload=dict(job.payload))
        job_type, attempts, max_attempts = job.type, job.attempts, job.max_attempts
    log.info("claimed job %s (%s), attempt %d of %d", info.id, job_type, attempts + 1, max_attempts)

    try:
        if job_type == jobs_repo.INGEST_IMAGES:
            run_ingest_job(info, settings, make_tagger=lambda: make_tagger(settings))
        else:
            fail_job(info.id, f"unknown job type '{job_type}'")
    except Exception as e:  # unexpected crash: retry later, or give up loudly
        log.exception("job %s crashed", info.id)
        if attempts + 1 < max_attempts:
            delay = timedelta(seconds=60 * (attempts + 1))
            with session_scope() as s:
                jobs_repo.requeue(s, info.id, delay, f"crashed: {e!r}", count_attempt=True)
            log.warning("job %s re-queued, retry in %s", info.id, delay)
        else:
            fail_job(info.id, f"crashed {max_attempts} times, last error: {e!r}")
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    log.info(
        "worker starting: model=%s, rpm=%s, images_dir=%s, api key %s",
        settings.vision_model, settings.gemini_rpm, settings.images_dir,
        "set" if settings.gemini_api_key else "NOT SET",  # never the key itself
    )
    with session_scope() as s:
        orphaned = jobs_repo.requeue_running(s)
    if orphaned:
        log.warning("re-queued %d job(s) left 'running' by a previous worker", orphaned)

    while True:
        if not run_one(settings):
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
