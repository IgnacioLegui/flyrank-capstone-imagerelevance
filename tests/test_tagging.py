"""Tagging decisions (tagged / flagged / failed) with a scripted fake tagger: no network."""

import json

import pytest

from app.ai.gemini import BudgetExceeded, CallContext, GeminiCallError, InvalidOutput, Parsed, RateLimited
from app.domain.vision import ImageTags
from app.services.tagging import tag_one

CTX = CallContext(purpose="vision_tag", owner_type="image", owner_id=1)


def answer(confidence: float = 0.9, **overrides) -> Parsed[ImageTags]:
    data = {
        "category": "animal", "subject_key": "red_fox", "subject": "red fox",
        "attributes": ["orange fur"], "caption": "A red fox in the snow", "confidence": confidence,
    } | overrides
    return Parsed(value=ImageTags.model_validate(data), raw_text=json.dumps(data))


class ScriptedTagger:
    """Returns (or raises) the scripted items in order, one per call."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0

    def tag_image(self, image_bytes, ctx):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_confident_answer_is_tagged_first_try():
    out = tag_one(b"img", ScriptedTagger(answer(0.93)), CTX, min_confidence=0.70)
    assert (out.status, out.attempts) == ("tagged", 1)
    assert out.tags.subject_key.value == "red_fox"
    assert out.raw_text is not None


def test_low_confidence_is_flagged_not_guessed():
    out = tag_one(b"img", ScriptedTagger(answer(0.41, subject_key="other")), CTX, min_confidence=0.70)
    assert out.status == "flagged"
    assert out.error == "confidence 0.41 below 0.70"
    assert out.tags is not None  # kept for inspection, but excluded from matching downstream


def test_confidence_exactly_at_threshold_is_tagged():
    assert tag_one(b"img", ScriptedTagger(answer(0.70)), CTX, min_confidence=0.70).status == "tagged"


def test_invalid_then_valid_is_tagged_on_second_attempt():
    tagger = ScriptedTagger(InvalidOutput("{bad", "invalid json"), answer(0.9))
    out = tag_one(b"img", tagger, CTX, min_confidence=0.70)
    assert (out.status, out.attempts, tagger.calls) == ("tagged", 2, 2)


def test_three_invalid_answers_fail_with_last_error():
    tagger = ScriptedTagger(*[InvalidOutput("x", f"bad {i}") for i in range(3)])
    out = tag_one(b"img", tagger, CTX, min_confidence=0.70)
    assert (out.status, out.attempts, tagger.calls) == ("failed", 3, 3)
    assert out.error == "attempt 3: invalid output: bad 2"
    assert out.tags is None


def test_server_errors_also_use_attempts():
    tagger = ScriptedTagger(GeminiCallError("500"), GeminiCallError("500"), answer(0.8))
    assert tag_one(b"img", tagger, CTX, min_confidence=0.70).attempts == 3


@pytest.mark.parametrize("exc", [RateLimited(30, "429"), BudgetExceeded("spent")])
def test_rate_limit_and_budget_go_up_to_the_worker(exc):
    tagger = ScriptedTagger(exc, answer())
    with pytest.raises(type(exc)):
        tag_one(b"img", tagger, CTX, min_confidence=0.70)
    assert tagger.calls == 1  # not retried here, and no attempt was "spent" on it
