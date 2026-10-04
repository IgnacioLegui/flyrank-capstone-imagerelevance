"""Job queue + ingest job against a real Postgres (test database), with a fake tagger: no Gemini."""

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from PIL import Image as PILImage
from sqlalchemy import func, select

from app.ai.gemini import BudgetExceeded, CallRecord, GeminiCallError, Parsed, RateLimited
from app.config import load_settings
from app.db.models import AICall, Image, ImageTag, Job
from app.db.session import session_scope
from app.domain.vision import ImageTags
from app.repositories import jobs as jobs_repo
from app.repositories.ai_calls import DbCostLog
from app.services.ingest import JobInfo, run_ingest_job
from tests.conftest import TEST_URL

pytestmark = pytest.mark.usefixtures("db")

COLORS = ["red", "green", "blue", "yellow"]


def make_corpus(folder, n=3):
    folder.mkdir(exist_ok=True)
    for i in range(n):
        PILImage.new("RGB", (32, 32), COLORS[i]).save(folder / f"img_{i:02d}.jpg")
    return folder


def settings_for(images_dir):
    return load_settings({"DATABASE_URL": TEST_URL, "IMAGES_DIR": str(images_dir), "MIN_CONFIDENCE": "0.7"})


def answer(confidence=0.9):
    data = {"category": "animal", "subject_key": "red_fox", "subject": "red fox",
            "attributes": ["orange"], "caption": "A red fox in a forest", "confidence": confidence}
    return Parsed(value=ImageTags.model_validate(data), raw_text=json.dumps(data))


class FakeTagger:
    model = "fake-model"

    def __init__(self, *script, default=None):
        self.script = list(script)
        self.default = default or answer()
        self.calls = 0

    def tag_image(self, image_bytes, ctx):
        self.calls += 1
        item = self.script.pop(0) if self.script else self.default
        if isinstance(item, Exception):
            raise item
        return item


def new_job(payload=None):
    with session_scope() as s:
        job, _ = jobs_repo.create_job(s, jobs_repo.INGEST_IMAGES, payload or {})
        return JobInfo(id=job.id, payload=job.payload)


def get_job(job_id):
    with session_scope() as s:
        return s.get(Job, job_id)


def count(model, *where):
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(model).where(*where))


def run(job, settings, tagger, sleeps=None):
    run_ingest_job(job, settings, make_tagger=lambda: tagger, sleep=(sleeps.append if sleeps is not None else lambda s: None))


# --- Ingest job -----------------------------------------------------------------------------------

def test_batch_tags_every_image_flags_low_confidence_and_tracks_progress(tmp_path):
    settings = settings_for(make_corpus(tmp_path / "images", 3))
    job = new_job()
    run(job, settings, FakeTagger(answer(0.9), answer(0.95), answer(0.3)))

    j = get_job(job.id)
    assert (j.status, j.progress_done, j.progress_total) == ("succeeded", 3, 3)
    assert count(Image, Image.status == "tagged") == 2
    assert count(Image, Image.status == "flagged") == 1
    assert count(ImageTag) == 3  # the flagged image keeps its tags for inspection
    with session_scope() as s:
        flagged = s.scalar(select(Image).where(Image.status == "flagged"))
        assert flagged.error == "confidence 0.30 below 0.70"


def test_rerunning_ingest_is_idempotent(tmp_path):
    settings = settings_for(make_corpus(tmp_path / "images", 3))
    tagger = FakeTagger()
    run(new_job(), settings, tagger)
    second = new_job()
    run(second, settings, tagger)

    assert count(Image) == 3  # same files -> same rows (sha256 unique)
    assert tagger.calls == 3  # nothing was re-tagged
    j = get_job(second.id)
    assert (j.status, j.progress_done, j.progress_total) == ("succeeded", 3, 3)


def test_only_processes_the_requested_images(tmp_path):
    settings = settings_for(make_corpus(tmp_path / "images", 3))
    run(new_job({"only": ["img_02.jpg"]}), settings, FakeTagger())
    assert count(Image) == 1
    with session_scope() as s:
        assert s.scalar(select(Image.filename)) == "img_02.jpg"


@pytest.mark.parametrize("case", ["missing", "empty", "unknown_only"])
def test_missing_or_empty_corpus_fails_loudly(tmp_path, caplog, case):
    folder = tmp_path / "images"
    payload = {}
    if case == "empty":
        folder.mkdir()
    elif case == "unknown_only":
        make_corpus(folder, 1)
        payload = {"only": ["nope.jpg"]}
    job = new_job(payload)

    with caplog.at_level(logging.ERROR, logger="worker.ingest"):
        run(job, settings_for(folder), FakeTagger())

    j = get_job(job.id)
    assert j.status == "failed"
    assert j.progress_total == 0
    assert f"ALERT job {job.id} failed" in caplog.text
    assert "IMAGES_DIR" in j.last_error or "not found" in j.last_error


def test_missing_api_key_fails_job(tmp_path, caplog):
    settings = settings_for(make_corpus(tmp_path / "images", 1))
    job = new_job()

    def no_key():
        raise GeminiCallError("GEMINI_API_KEY is not set (add it to .env)")

    with caplog.at_level(logging.ERROR, logger="worker.ingest"):
        run_ingest_job(job, settings, make_tagger=no_key)
    assert get_job(job.id).status == "failed"
    assert "GEMINI_API_KEY is not set" in caplog.text


# --- Rate limits and budget -----------------------------------------------------------------------

def test_429_backs_off_then_continues(tmp_path):
    settings = settings_for(make_corpus(tmp_path / "images", 1))
    sleeps = []
    job = new_job()
    run(job, settings, FakeTagger(RateLimited(None, "429"), RateLimited(None, "429")), sleeps)
    assert sleeps == [30, 60]  # exponential backoff, no server hint
    assert get_job(job.id).status == "succeeded"


def test_429_uses_server_retry_delay(tmp_path):
    settings = settings_for(make_corpus(tmp_path / "images", 1))
    sleeps = []
    run(new_job(), settings, FakeTagger(RateLimited(37.0, "429")), sleeps)
    assert sleeps == [37.0]


def test_five_429s_in_a_row_pause_the_job_instead_of_failing(tmp_path):
    settings = settings_for(make_corpus(tmp_path / "images", 2))
    sleeps = []
    job = new_job()
    run(job, settings, FakeTagger(*[RateLimited(None, "429")] * 5), sleeps)

    j = get_job(job.id)
    assert j.status == "queued"  # paused, will resume
    assert j.run_after > datetime.now(timezone.utc) + timedelta(minutes=50)
    assert j.attempts == 0  # a rate limit is not a crash
    assert len(sleeps) == 4
    assert count(Image, Image.status == "pending") == 2


def test_budget_exceeded_fails_the_job(tmp_path, caplog):
    settings = settings_for(make_corpus(tmp_path / "images", 2))
    job = new_job()
    with caplog.at_level(logging.ERROR, logger="worker.ingest"):
        run(job, settings, FakeTagger(BudgetExceeded("AI budget reached")))
    assert get_job(job.id).status == "failed"
    assert "AI budget reached" in caplog.text


# --- Queue mechanics ------------------------------------------------------------------------------

def test_two_workers_never_claim_the_same_job():
    for _ in range(2):
        new_job()
    with session_scope() as a, session_scope() as b:
        job_a = jobs_repo.claim_next(a)  # row locked until `a` commits
        job_b = jobs_repo.claim_next(b)  # SKIP LOCKED -> takes the other job
        assert {job_a.id, job_b.id} == {1, 2}
        with session_scope() as c:
            assert jobs_repo.claim_next(c) is None  # nothing left that isn't locked
    assert count(Job, Job.status == "running") == 2


def test_future_job_is_not_claimed_yet():
    job = new_job()
    with session_scope() as s:
        jobs_repo.requeue(s, job.id, timedelta(hours=1), "paused", count_attempt=False)
    with session_scope() as s:
        assert jobs_repo.claim_next(s) is None


def test_same_idempotency_key_returns_the_same_job():
    with session_scope() as s:
        first, created1 = jobs_repo.create_job(s, jobs_repo.INGEST_IMAGES, {}, "key-123")
    with session_scope() as s:
        second, created2 = jobs_repo.create_job(s, jobs_repo.INGEST_IMAGES, {}, "key-123")
    assert first.id == second.id
    assert (created1, created2) == (True, False)
    assert count(Job) == 1


def test_orphaned_running_jobs_are_requeued_at_startup():
    new_job()
    with session_scope() as s:
        jobs_repo.claim_next(s)
    with session_scope() as s:
        assert jobs_repo.requeue_running(s) == 1
    assert count(Job, Job.status == "queued") == 1


def test_worker_crash_is_retried_then_failed_with_alert(monkeypatch, caplog):
    import worker.main as worker_main

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(worker_main, "run_ingest_job", boom)
    settings = load_settings({"DATABASE_URL": TEST_URL})
    job = new_job()

    for attempt in range(1, 4):
        with session_scope() as s:  # make the requeued job due again right away
            s.get(Job, job.id).run_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        with caplog.at_level(logging.ERROR):
            assert worker_main.run_one(settings) is True
        j = get_job(job.id)
        if attempt < 3:
            assert (j.status, j.attempts) == ("queued", attempt)
    assert j.status == "failed"
    assert "crashed 3 times" in j.last_error
    assert f"ALERT job {job.id} failed" in caplog.text


# --- Cost log -------------------------------------------------------------------------------------

def test_db_cost_log_records_and_sums():
    log = DbCostLog()
    for cost in ("0.00155", "0.00045"):
        log.record(CallRecord(purpose="vision_tag", model="m", outcome="ok", cost_usd=Decimal(cost)))
    assert log.total_spent_usd() == Decimal("0.002")
    assert count(AICall) == 2
