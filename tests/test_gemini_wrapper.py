"""Gemini wrapper tests with a fake client: no network, no API key, no cost."""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.ai.gemini import (
    IMAGE_TAGS_SCHEMA,
    BudgetExceeded,
    CallContext,
    GeminiCallError,
    GeminiVision,
    InvalidOutput,
    RateLimited,
    make_client,
)
from app.ai.pricing import UnknownModelPrice, cost_usd
from app.config import load_settings

ROOT = Path(__file__).resolve().parent.parent
FOX_PATH = ROOT / "data" / "images" / "red_fox_01.jpg"
VALID_JSON = json.dumps({
    "category": "animal", "subject_key": "red_fox", "subject": "red fox",
    "attributes": ["orange fur", "forest"], "caption": "A red fox sitting in a dark forest",
    "confidence": 0.93,
})
CTX = CallContext(purpose="vision_tag", job_id=7, owner_type="image", owner_id=1)


class FakeCostLog:
    def __init__(self, spent: str = "0"):
        self.spent = Decimal(spent)
        self.rows = []

    def total_spent_usd(self) -> Decimal:
        return self.spent

    def record(self, entry) -> None:
        self.rows.append(entry)


class FakeClient:
    """Mimics client.models.generate_content; records every request it receives."""

    def __init__(self, text=VALID_JSON, usage=(1000, 200, 300), raises=None):
        self.requests = []
        self._text, self._usage, self._raises = text, usage, raises
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.requests.append({"model": model, "contents": contents, "config": config})
        if self._raises:
            raise self._raises
        prompt, out, thoughts = self._usage
        usage = SimpleNamespace(
            prompt_token_count=prompt, candidates_token_count=out, thoughts_token_count=thoughts
        )
        return SimpleNamespace(text=self._text, usage_metadata=usage)


def make(client=None, spent="0", model="gemini-3.5-flash-lite", budget=1.0):
    log = FakeCostLog(spent)
    client = client or FakeClient()
    return GeminiVision(client, model, log, budget), client, log


def serialize(request) -> str:
    """Everything that would go over the wire, as one string."""
    parts = [
        c.model_dump_json() if hasattr(c, "model_dump_json") else str(c) for c in request["contents"]
    ]
    return " ".join(parts + [request["config"].model_dump_json()])


# --- The filename never reaches Gemini -----------------------------------------------------------

def test_request_contains_image_bytes_but_no_filename_or_path():
    vision, client, _ = make()
    image_bytes = FOX_PATH.read_bytes()
    vision.tag_image(image_bytes, CTX)

    request = client.requests[0]
    sent = serialize(request)
    assert "red_fox_01" not in sent
    assert ".jpg" not in sent
    assert str(FOX_PATH.parent) not in sent
    image_part = request["contents"][0]
    assert image_part.inline_data.data == image_bytes  # pixels go inline...
    assert image_part.inline_data.display_name is None  # ...without a name attached
    assert image_part.file_data is None  # and not as an uploaded file reference


def test_schema_sent_to_gemini_has_no_refs():
    assert "$ref" not in json.dumps(IMAGE_TAGS_SCHEMA)
    assert "red_fox" in json.dumps(IMAGE_TAGS_SCHEMA)  # enum values were inlined


# --- Successful call + cost ----------------------------------------------------------------------

def test_valid_answer_is_parsed_and_logged_with_cost():
    vision, _, log = make()
    result = vision.tag_image(b"jpeg-bytes", CTX)
    assert result.value.subject_key.value == "red_fox"
    assert result.raw_text == VALID_JSON

    (row,) = log.rows
    assert row.outcome == "ok"
    assert (row.input_tokens, row.output_tokens, row.thinking_tokens) == (1000, 200, 300)
    # 1000 × $0.30/1M + (200 + 300) × $2.50/1M = 0.0003 + 0.00125
    assert row.cost_usd == Decimal("0.00155")
    assert (row.job_id, row.owner_type, row.owner_id, row.purpose) == (7, "image", 1, "vision_tag")
    assert row.response_text == VALID_JSON


def test_cost_formula_counts_thinking_tokens_at_output_price():
    assert cost_usd("gemini-3.5-flash-lite", 0, 0, 1_000_000) == Decimal("2.50")
    assert cost_usd("gemini-3.5-flash-lite", 1_000_000, 0, 0) == Decimal("0.30")


# --- Refusals before any request is sent ---------------------------------------------------------

def test_budget_reached_refuses_without_calling():
    vision, client, log = make(spent="1.00", budget=1.0)
    with pytest.raises(BudgetExceeded):
        vision.tag_image(b"x", CTX)
    assert client.requests == []
    assert log.rows == []


def test_unknown_model_refuses_without_calling():
    vision, client, _ = make(model="gemini-99-ultra")
    with pytest.raises(UnknownModelPrice):
        vision.tag_image(b"x", CTX)
    assert client.requests == []


# --- Failures still produce exactly one cost row --------------------------------------------------

def test_invalid_json_is_logged_and_raised_with_raw_text():
    vision, _, log = make(FakeClient(text="Sure! here you go: {"))
    with pytest.raises(InvalidOutput) as exc:
        vision.tag_image(b"x", CTX)
    assert exc.value.raw_text == "Sure! here you go: {"
    (row,) = log.rows
    assert row.outcome == "invalid_output"
    assert row.cost_usd > 0  # the model still produced (billable) tokens


def test_inconsistent_answer_counts_as_invalid_output():
    bad = json.loads(VALID_JSON) | {"category": "food"}
    vision, _, log = make(FakeClient(text=json.dumps(bad)))
    with pytest.raises(InvalidOutput, match="inconsistent tags"):
        vision.tag_image(b"x", CTX)
    assert log.rows[0].outcome == "invalid_output"


def test_no_text_counts_as_invalid_output():
    vision, _, log = make(FakeClient(text=None))
    with pytest.raises(InvalidOutput):
        vision.tag_image(b"x", CTX)
    assert log.rows[0].outcome == "invalid_output"


def test_429_is_rate_limited_with_server_retry_delay():
    body = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded",
                      "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo",
                                   "retryDelay": "37s"}]}}
    vision, _, log = make(FakeClient(raises=errors.ClientError(429, body)))
    with pytest.raises(RateLimited) as exc:
        vision.tag_image(b"x", CTX)
    assert exc.value.retry_after == 37.0
    (row,) = log.rows
    assert row.outcome == "rate_limited"
    assert row.cost_usd == 0


def test_429_without_retry_info_has_no_delay():
    body = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "slow down"}}
    vision, _, _ = make(FakeClient(raises=errors.ClientError(429, body)))
    with pytest.raises(RateLimited) as exc:
        vision.tag_image(b"x", CTX)
    assert exc.value.retry_after is None


def test_server_error_is_logged_as_error():
    body = {"error": {"code": 500, "status": "INTERNAL", "message": "boom"}}
    vision, _, log = make(FakeClient(raises=errors.ServerError(500, body)))
    with pytest.raises(GeminiCallError):
        vision.tag_image(b"x", CTX)
    assert log.rows[0].outcome == "error"


def test_missing_api_key_fails_clearly():
    settings = load_settings({"DATABASE_URL": "postgresql://u:p@h/db"})
    with pytest.raises(GeminiCallError, match="GEMINI_API_KEY is not set"):
        make_client(settings)


def test_network_error_is_logged_as_error():
    vision, _, log = make(FakeClient(raises=ConnectionError("connection reset")))
    with pytest.raises(GeminiCallError, match="ConnectionError"):
        vision.tag_image(b"x", CTX)
    assert log.rows[0].outcome == "error"
