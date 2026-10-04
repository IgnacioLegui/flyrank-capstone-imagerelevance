"""Tests for the vision output schema and the category/subject consistency check."""

import pytest
from pydantic import ValidationError

from app.domain.taxonomy import SUBJECT_CATEGORY, Category, SubjectKey
from app.domain.vision import ImageTags
from app.services.guard import PostSubject

VALID = {
    "category": "animal",
    "subject_key": "red_fox",
    "subject": "red fox",
    "attributes": ["orange fur", "forest"],
    "caption": "A red fox standing in a forest",
    "confidence": 0.94,
}


def test_valid_answer_parses():
    tags = ImageTags.model_validate(VALID)
    assert tags.subject_key is SubjectKey.RED_FOX
    assert tags.category is Category.ANIMAL


def test_valid_answer_parses_from_raw_json():
    raw = '{"category":"food","subject_key":"pizza","subject":"pizza","attributes":["cheese"],' \
          '"caption":"A margherita pizza on a table","confidence":0.9}'
    assert ImageTags.model_validate_json(raw).subject_key is SubjectKey.PIZZA


def test_every_known_subject_has_a_category():
    assert set(SUBJECT_CATEGORY) == set(SubjectKey) - {SubjectKey.OTHER}


@pytest.mark.parametrize(
    "category, subject_key",
    [("food", "red_fox"), ("vehicle", "gray_wolf"), ("animal", "pizza"), ("landscape", "car")],
)
def test_inconsistent_category_and_subject_rejected(category, subject_key):
    with pytest.raises(ValidationError, match="inconsistent tags"):
        ImageTags.model_validate(VALID | {"category": category, "subject_key": subject_key})


@pytest.mark.parametrize("category", list(Category))
def test_other_subject_allowed_in_any_category(category):
    assert ImageTags.model_validate(VALID | {"category": category, "subject_key": "other"})


def test_post_subject_gets_the_same_consistency_check():
    with pytest.raises(ValidationError, match="inconsistent tags"):
        PostSubject(category="food", subject_key="red_fox", confidence=0.9)


@pytest.mark.parametrize(
    "bad",
    [
        {"confidence": 1.2},
        {"confidence": -0.1},
        {"subject_key": "vulpes vulpes"},
        {"category": "plant"},
        {"attributes": []},
        {"attributes": [f"a{i}" for i in range(11)]},
        {"caption": "fox"},
        {"subject": ""},
    ],
)
def test_out_of_contract_answers_rejected(bad):
    with pytest.raises(ValidationError):
        ImageTags.model_validate(VALID | bad)


@pytest.mark.parametrize("missing", ["category", "subject_key", "caption", "confidence"])
def test_missing_field_rejected(missing):
    data = {k: v for k, v in VALID.items() if k != missing}
    with pytest.raises(ValidationError):
        ImageTags.model_validate(data)


def test_not_json_rejected():
    with pytest.raises(ValidationError):
        ImageTags.model_validate_json("Sure! Here is the JSON: {")
