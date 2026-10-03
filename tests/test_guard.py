"""Unit tests for the mismatch guard. Pure logic: no database, no Gemini calls.

Thresholds are passed explicitly (not read from .env), so calibrating the real values in
Phase 3 doesn't change what these tests prove.
"""

import pytest
from pydantic import ValidationError

from app.domain.taxonomy import Category, SubjectKey
from app.services.guard import Candidate, GuardRule, PostSubject, Thresholds, decide, evaluate

T = Thresholds(min_confidence=0.70, min_post_confidence=0.50, min_similarity=0.65)

FOX_POST = PostSubject(category=Category.ANIMAL, subject_key=SubjectKey.RED_FOX, confidence=0.95)


def cand(
    image_id: int,
    subject: SubjectKey,
    category: Category = Category.ANIMAL,
    confidence: float = 0.90,
    similarity: float = 0.80,
) -> Candidate:
    return Candidate(
        image_id=image_id,
        category=category,
        subject_key=subject,
        confidence=confidence,
        similarity=similarity,
    )


# --- Single-candidate rules ---------------------------------------------------------------

def test_fox_image_accepted_for_fox_post():
    v = evaluate(FOX_POST, cand(1, SubjectKey.RED_FOX), T)
    assert v.accepted
    assert v.failed_rule is None
    assert "red fox" in v.reason


def test_wolf_rejected_on_fox_post_by_subject_rule():
    """Probe 3: same category (animal), so G2 passes and G3 is what rejects the wolf."""
    v = evaluate(FOX_POST, cand(2, SubjectKey.GRAY_WOLF, similarity=0.85), T)
    assert not v.accepted
    assert v.failed_rule is GuardRule.G3_SUBJECT
    assert v.reason == "Subject mismatch: expected red fox, detected gray wolf"


def test_category_mismatch_rejected_by_g2():
    v = evaluate(FOX_POST, cand(3, SubjectKey.PIZZA, category=Category.FOOD), T)
    assert v.failed_rule is GuardRule.G2_CATEGORY
    assert v.reason == "Category mismatch: expected animal, detected food"


def test_low_image_confidence_rejected_by_g1():
    v = evaluate(FOX_POST, cand(4, SubjectKey.RED_FOX, confidence=0.41), T)
    assert v.failed_rule is GuardRule.G1_IMAGE_CONFIDENCE
    assert v.reason == "Image classification confidence 0.41 below 0.70"


def test_low_similarity_rejected_by_g4():
    v = evaluate(FOX_POST, cand(5, SubjectKey.RED_FOX, similarity=0.52), T)
    assert v.failed_rule is GuardRule.G4_SIMILARITY
    assert v.reason == "Semantic similarity 0.52 below 0.65"


def test_similarity_exactly_at_threshold_passes():
    assert evaluate(FOX_POST, cand(6, SubjectKey.RED_FOX, similarity=0.65), T).accepted


# --- G5: post-level checks ----------------------------------------------------------------

def test_off_taxonomy_post_rejected_by_g5():
    """Probe 4 shape: a penguin post extracts as subject `other`."""
    penguin_post = PostSubject(category=Category.ANIMAL, subject_key=SubjectKey.OTHER, confidence=0.9)
    v = evaluate(penguin_post, cand(7, SubjectKey.RED_FOX), T)
    assert v.failed_rule is GuardRule.G5_POST_UNVERIFIABLE
    assert "outside the image taxonomy" in v.reason


def test_image_tagged_other_cannot_match_off_taxonomy_post():
    """The gap G5-first closes: without it, other == other would pass G3."""
    penguin_post = PostSubject(category=Category.ANIMAL, subject_key=SubjectKey.OTHER, confidence=0.9)
    v = evaluate(penguin_post, cand(8, SubjectKey.OTHER, similarity=0.90), T)
    assert not v.accepted
    assert v.failed_rule is GuardRule.G5_POST_UNVERIFIABLE


def test_low_post_confidence_rejected_by_g5():
    unsure_post = PostSubject(category=Category.ANIMAL, subject_key=SubjectKey.RED_FOX, confidence=0.40)
    v = evaluate(unsure_post, cand(9, SubjectKey.RED_FOX), T)
    assert v.failed_rule is GuardRule.G5_POST_UNVERIFIABLE
    assert v.reason.startswith("Post subject extraction confidence 0.40 below 0.50")


def test_post_confidence_uses_its_own_threshold_not_the_image_one():
    """0.65 is below the image threshold (0.70) but above the post one (0.50): must still match."""
    post = PostSubject(category=Category.ANIMAL, subject_key=SubjectKey.RED_FOX, confidence=0.65)
    assert evaluate(post, cand(10, SubjectKey.RED_FOX), T).accepted


# --- Rule order ---------------------------------------------------------------------------

def test_g5_reported_before_any_image_rule():
    penguin_post = PostSubject(category=Category.ANIMAL, subject_key=SubjectKey.OTHER, confidence=0.9)
    bad_image = cand(11, SubjectKey.PIZZA, category=Category.FOOD, confidence=0.2, similarity=0.1)
    assert evaluate(penguin_post, bad_image, T).failed_rule is GuardRule.G5_POST_UNVERIFIABLE


def test_g1_reported_before_g3():
    low_conf_wolf = cand(12, SubjectKey.GRAY_WOLF, confidence=0.30)
    assert evaluate(FOX_POST, low_conf_wolf, T).failed_rule is GuardRule.G1_IMAGE_CONFIDENCE


# --- decide(): ranking, suggestion, refusal -----------------------------------------------

def test_top_candidate_fails_so_second_is_suggested():
    wolf = cand(20, SubjectKey.GRAY_WOLF, similarity=0.86)
    fox = cand(21, SubjectKey.RED_FOX, similarity=0.81)
    d = decide(FOX_POST, [wolf, fox], T)
    assert d.status == "matched"
    assert d.suggestion.image_id == 21
    assert d.suggestion.rank == 2
    assert d.verdicts[0].image_id == 20
    assert d.verdicts[0].failed_rule is GuardRule.G3_SUBJECT


def test_no_confident_match_explains_every_candidate():
    wolf = cand(30, SubjectKey.GRAY_WOLF, similarity=0.84)
    dog = cand(31, SubjectKey.DOG, similarity=0.79)
    pizza = cand(32, SubjectKey.PIZZA, category=Category.FOOD, similarity=0.30)
    d = decide(FOX_POST, [wolf, dog, pizza], T)
    assert d.status == "no_confident_match"
    assert d.suggestion is None
    assert [v.reason for v in d.verdicts] == [
        "Subject mismatch: expected red fox, detected gray wolf",
        "Subject mismatch: expected red fox, detected dog",
        "Category mismatch: expected animal, detected food",
    ]


def test_decide_ranks_by_similarity_regardless_of_input_order():
    low = cand(40, SubjectKey.RED_FOX, similarity=0.70)
    high = cand(41, SubjectKey.RED_FOX, similarity=0.90)
    d = decide(FOX_POST, [low, high], T)
    assert [v.image_id for v in d.verdicts] == [41, 40]
    assert [v.rank for v in d.verdicts] == [1, 2]
    assert d.suggestion.image_id == 41


def test_no_candidates_is_no_confident_match():
    d = decide(FOX_POST, [], T)
    assert d.status == "no_confident_match"
    assert d.verdicts == []


# --- Input validation ---------------------------------------------------------------------

@pytest.mark.parametrize("bad", [{"confidence": 1.5}, {"confidence": -0.1}, {"similarity": 1.2}])
def test_out_of_range_scores_are_rejected(bad):
    fields = dict(image_id=1, category="animal", subject_key="red_fox", confidence=0.9, similarity=0.8)
    with pytest.raises(ValidationError):
        Candidate(**(fields | bad))


def test_unknown_subject_is_rejected():
    with pytest.raises(ValidationError):
        PostSubject(category="animal", subject_key="vulpes vulpes", confidence=0.9)
