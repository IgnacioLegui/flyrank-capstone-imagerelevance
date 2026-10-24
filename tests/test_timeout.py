"""Request timeout, proven with the REAL google-genai client against a local fake Gemini server.

The fake server can hang (sleep far longer than our timeout) on chosen requests. If the SDK read
our timeout in the wrong unit — e.g. 500 meant "500 seconds" instead of "500 ms" — the call would
wait for the server and these tests would fail on their elapsed-time bounds.
"""

import json
import threading
import time
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image as PILImage
from sqlalchemy import select

from app.ai.gemini import CallContext, GeminiCallError, GeminiVision, make_client, timeout_ms
from app.config import load_settings
from app.db.models import AICall, Image, Job
from app.db.session import session_scope
from app.repositories import jobs as jobs_repo
from app.repositories.ai_calls import DbCostLog
from app.services.ingest import JobInfo, run_ingest_job
from tests.conftest import TEST_URL
from tests.test_gemini_wrapper import FakeCostLog

TIMEOUT_S = 0.5
SERVER_HANG_S = 4.0  # much longer than the timeout: only a working timeout returns early
VALID_ANSWER = json.dumps({
    "category": "animal", "subject_key": "red_fox", "subject": "red fox",
    "attributes": ["orange fur"], "caption": "A red fox in a forest", "confidence": 0.95,
})


class FakeGemini(BaseHTTPRequestHandler):
    """Answers generateContent like Gemini does, except it hangs on the request numbers in `hang_on`."""

    hang_on: set[int] = set()
    count = 0
    lock = threading.Lock()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with FakeGemini.lock:
            FakeGemini.count += 1
            n = FakeGemini.count
        if n in FakeGemini.hang_on:
            time.sleep(SERVER_HANG_S)  # simulate Google never answering in time
        body = json.dumps({
            "candidates": [{"content": {"role": "model", "parts": [{"text": VALID_ANSWER}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 50, "totalTokenCount": 1050},
        }).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # the client already gave up — that's the point

    def log_message(self, *args):  # keep test output quiet
        pass


@pytest.fixture
def fake_gemini():
    FakeGemini.hang_on, FakeGemini.count = set(), 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGemini)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()


def real_client(base_url, **env):
    settings = load_settings({"DATABASE_URL": TEST_URL, "GEMINI_API_KEY": "fake-key-for-local-server",
                              "GEMINI_TIMEOUT_S": str(TIMEOUT_S), **env})
    return make_client(settings, base_url=base_url), settings


def test_setting_in_seconds_becomes_sdk_milliseconds():
    assert timeout_ms(60) == 60_000
    assert timeout_ms(0.5) == 500


def test_default_timeout_is_60_seconds():
    assert load_settings({"DATABASE_URL": TEST_URL}).gemini_timeout_s == 60


def test_fake_server_answers_normally_when_not_hanging(fake_gemini):
    """Sanity check: the real SDK talks to the fake server and gets a valid answer."""
    client, _ = real_client(fake_gemini)
    vision = GeminiVision(client, "gemini-3.5-flash-lite", FakeCostLog(), budget_usd=1.0)
    assert vision.tag_image(b"img", CallContext(purpose="vision_tag")).value.subject_key.value == "red_fox"


def test_hung_request_times_out_and_logs_an_error_row(fake_gemini):
    FakeGemini.hang_on = {1}
    client, _ = real_client(fake_gemini)
    log = FakeCostLog()
    vision = GeminiVision(client, "gemini-3.5-flash-lite", log, budget_usd=1.0)

    started = time.monotonic()
    with pytest.raises(GeminiCallError, match="(?i)timeout|timed out"):
        vision.tag_image(b"img", CallContext(purpose="vision_tag", owner_type="image", owner_id=1))
    elapsed = time.monotonic() - started

    # 0.5 s timeout -> returns after ~0.5 s. If the unit were wrong it would wait the full 4 s hang.
    assert TIMEOUT_S * 0.8 <= elapsed < 2.0, f"took {elapsed:.2f}s"
    (row,) = log.rows
    assert row.outcome == "error"
    assert row.cost_usd == 0
    assert row.latency_ms >= TIMEOUT_S * 800


@pytest.mark.usefixtures("db")
def test_hung_request_uses_one_attempt_and_the_job_keeps_going(fake_gemini, tmp_path):
    """Image 1's first request hangs: it times out (error row), image 1 is retried and tagged,
    image 2 is tagged, and the job succeeds."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for i, color in enumerate(["red", "blue"]):
        PILImage.new("RGB", (16, 16), color).save(images_dir / f"img_{i:02d}.jpg")
    FakeGemini.hang_on = {1}  # the very first request = first attempt for img_00.jpg
    client, settings = real_client(fake_gemini, IMAGES_DIR=str(images_dir))
    with session_scope() as s:
        job, _ = jobs_repo.create_job(s, jobs_repo.INGEST_IMAGES, {})
        info = JobInfo(id=job.id, payload={})

    started = time.monotonic()
    run_ingest_job(info, settings, make_tagger=lambda: GeminiVision(
        client, "gemini-3.5-flash-lite", DbCostLog(), settings.ai_budget_usd))
    assert time.monotonic() - started < 3.0  # never waited out the 4 s hang

    with session_scope() as s:
        assert s.get(Job, info.id).status == "succeeded"
        statuses = dict(s.execute(select(Image.filename, Image.status)).all())
        assert statuses == {"img_00.jpg": "tagged", "img_01.jpg": "tagged"}
        rows = s.execute(
            select(Image.filename, AICall.outcome, AICall.cost_usd, AICall.error)
            .join(Image, Image.id == AICall.owner_id).order_by(AICall.id)
        ).all()
    assert [(f, o) for f, o, _, _ in rows] == [
        ("img_00.jpg", "error"),  # attempt 1: timed out
        ("img_00.jpg", "ok"),     # attempt 2: answered
        ("img_01.jpg", "ok"),
    ]
    assert rows[0].cost_usd == Decimal(0)
    assert "timeout" in rows[0].error.lower() or "timed out" in rows[0].error.lower()
