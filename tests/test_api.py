"""HTTP API against the test database: happy paths, and bad input -> clean 4xx (never a 500)."""

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import CallRecord
from app.api.main import app
from app.db.models import Image, Job
from app.db.session import session_scope
from app.domain.vision import ImageTags
from app.repositories import images as images_repo
from app.repositories.ai_calls import DbCostLog
from scripts.enqueue_ingest import enqueue_only

pytestmark = pytest.mark.usefixtures("db")

client = TestClient(app, raise_server_exceptions=False)  # surface 500s as responses, so we can assert on them


def seed_image(filename="red_fox_01.jpg", status="tagged", confidence=0.93):
    data = {"category": "animal", "subject_key": "red_fox", "subject": "red fox",
            "attributes": ["orange fur"], "caption": "A red fox in a forest", "confidence": confidence}
    with session_scope() as s:
        image = Image(filename=filename, sha256=filename.ljust(64, "0"), status="pending")
        s.add(image)
        s.flush()
        error = None if status == "tagged" else f"confidence {confidence:.2f} below 0.70"
        images_repo.save_outcome(s, image, "gemini-3.5-flash-lite", status, error,
                                 ImageTags.model_validate(data), json.dumps(data))
        image_id = image.id
    DbCostLog().record(CallRecord(purpose="vision_tag", model="gemini-3.5-flash-lite", outcome="ok",
                                  owner_type="image", owner_id=image_id, input_tokens=1000,
                                  output_tokens=60, cost_usd=Decimal("0.00045"),
                                  response_text=json.dumps(data)))
    return image_id


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_post_ingest_queues_a_job_and_returns_202():
    r = client.post("/jobs/ingest-images")
    assert r.status_code == 202
    body = r.json()
    assert (body["status"], body["type"], body["progress_done"]) == ("queued", "ingest_images", 0)


def test_same_idempotency_key_returns_same_job_with_200():
    first = client.post("/jobs/ingest-images", headers={"Idempotency-Key": "abc-1"})
    again = client.post("/jobs/ingest-images", headers={"Idempotency-Key": "abc-1"})
    assert (first.status_code, again.status_code) == (202, 200)
    assert first.json()["id"] == again.json()["id"]


def test_api_cannot_set_an_only_filter():
    """The 'only' selection is CLI-only; a body sent to the API is ignored."""
    r = client.post("/jobs/ingest-images", json={"only": ["red_fox_01.jpg"]})
    with session_scope() as s:
        assert s.get(Job, r.json()["id"]).payload == {}


@pytest.mark.parametrize(
    "method, url, kwargs",
    [
        ("get", "/jobs/abc", {}),
        ("get", "/jobs/0", {}),
        ("get", "/jobs?status=bogus", {}),
        ("get", "/jobs?limit=0", {}),
        ("get", "/images?status=maybe", {}),
        ("get", "/images?limit=100000", {}),
        ("get", "/images?offset=-1", {}),
        ("get", "/images/99999999999", {}),
        ("get", "/costs?limit=-5", {}),
        ("post", "/jobs/ingest-images", {"headers": {"Idempotency-Key": "x" * 129}}),
        ("post", "/jobs/ingest-images", {"headers": {"Idempotency-Key": "has spaces!"}}),
    ],
)
def test_bad_input_is_a_422(method, url, kwargs):
    assert getattr(client, method)(url, **kwargs).status_code == 422


@pytest.mark.parametrize("url", ["/jobs/12345", "/images/12345"])
def test_unknown_id_is_a_404(url):
    assert client.get(url).status_code == 404


def test_list_images_filters_by_status():
    seed_image("red_fox_01.jpg", "tagged", 0.93)
    seed_image("ambiguous_02.jpg", "flagged", 0.41)
    r = client.get("/images?status=flagged")
    assert r.status_code == 200
    (img,) = r.json()
    assert img["filename"] == "ambiguous_02.jpg"
    assert img["error"] == "confidence 0.41 below 0.70"
    assert img["tags"][0]["confidence"] == 0.41


def test_image_detail_shows_raw_output_and_its_calls():
    image_id = seed_image()
    r = client.get(f"/images/{image_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["tags"][0]["raw_response"]["subject_key"] == "red_fox"
    assert body["calls"][0]["outcome"] == "ok"
    assert "red fox" in body["calls"][0]["response_text"]


def test_costs_lists_every_call_with_totals():
    seed_image("a.jpg")
    seed_image("b.jpg")
    body = client.get("/costs").json()
    assert body["total_calls"] == 2
    assert Decimal(body["total_cost_usd"]) == Decimal("0.0009")
    (total,) = body["by_purpose_and_model"]
    assert (total["purpose"], total["model"], total["calls"], total["ok"]) == (
        "vision_tag", "gemini-3.5-flash-lite", 2, 2)
    assert len(body["calls"]) == 2
    assert "list-price equivalent" in body["note"]


def test_enqueue_script_creates_an_only_job(tmp_path):
    for name in ("red_fox_01.jpg", "gray_wolf_01.jpg"):
        (tmp_path / name).write_bytes(b"x")
    job_id = enqueue_only(["red_fox_01.jpg", "gray_wolf_01.jpg"], tmp_path)
    with session_scope() as s:
        assert s.get(Job, job_id).payload == {"only": ["gray_wolf_01.jpg", "red_fox_01.jpg"]}


def test_enqueue_script_rejects_unknown_files(tmp_path):
    with pytest.raises(SystemExit, match="Not found"):
        enqueue_only(["nope.jpg"], tmp_path)
