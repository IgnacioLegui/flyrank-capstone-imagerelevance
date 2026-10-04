"""Mismatch guard: decides whether a ranked image candidate is good enough for a post.

Pure logic on purpose: no database, no AI calls, no environment reads. Callers pass in the
post's extracted subject, the candidates (already tagged, with their cosine similarity to
the post) and the thresholds. That keeps every decision reproducible and unit-testable.

Rules run in a fixed order and the first one that fails becomes the human-readable reason:
  G5  post-level: post subject is `other` or extracted with low confidence (checked first)
  G1  image classification confidence too low
  G2  category mismatch   (e.g. animal vs food)
  G3  subject mismatch    (e.g. red fox vs gray wolf: both animals, so G2 passes and G3 rejects)
  G4  semantic similarity too low
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.taxonomy import Category, SubjectKey, check_consistent, label


class GuardRule(StrEnum):
    G1_IMAGE_CONFIDENCE = "G1"
    G2_CATEGORY = "G2"
    G3_SUBJECT = "G3"
    G4_SIMILARITY = "G4"
    G5_POST_UNVERIFIABLE = "G5"


class Thresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_confidence: float = Field(ge=0, le=1)       # image vision confidence (G1)
    min_post_confidence: float = Field(ge=0, le=1)  # post subject extraction confidence (G5)
    min_similarity: float = Field(ge=-1, le=1)      # cosine similarity post vs image (G4)


class PostSubject(BaseModel):
    category: Category
    subject_key: SubjectKey
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _category_matches_subject(self) -> "PostSubject":
        check_consistent(self.category, self.subject_key)
        return self


class Candidate(BaseModel):
    image_id: int
    category: Category
    subject_key: SubjectKey
    confidence: float = Field(ge=0, le=1)
    similarity: float = Field(ge=-1, le=1)


class Verdict(BaseModel):
    image_id: int
    rank: int | None = None  # 1 = most similar; None when a single image is checked directly
    similarity: float
    accepted: bool
    failed_rule: GuardRule | None  # None when accepted
    reason: str                    # why it was rejected, or why it passed


class Decision(BaseModel):
    status: Literal["matched", "no_confident_match"]
    suggestion: Verdict | None  # highest-ranked accepted candidate, if any
    verdicts: list[Verdict]     # every evaluated candidate, in rank order, with its reason


def _reject(candidate: Candidate, rule: GuardRule, reason: str) -> Verdict:
    return Verdict(
        image_id=candidate.image_id,
        similarity=candidate.similarity,
        accepted=False,
        failed_rule=rule,
        reason=reason,
    )


def evaluate(post: PostSubject, candidate: Candidate, thresholds: Thresholds) -> Verdict:
    """Run G5, G1, G2, G3, G4 in that order; the first failure is returned as the reason."""
    # G5 first: if we can't trust what the post is about, no image can be verified against it.
    # Running it before G3 also avoids nonsense like "expected other", and stops an image
    # tagged `other` from "matching" an off-taxonomy post via other == other.
    if post.subject_key is SubjectKey.OTHER:
        return _reject(
            candidate,
            GuardRule.G5_POST_UNVERIFIABLE,
            "Post topic is outside the image taxonomy — cannot verify any image",
        )
    if post.confidence < thresholds.min_post_confidence:
        return _reject(
            candidate,
            GuardRule.G5_POST_UNVERIFIABLE,
            f"Post subject extraction confidence {post.confidence:.2f} below "
            f"{thresholds.min_post_confidence:.2f} — cannot verify any image",
        )

    if candidate.confidence < thresholds.min_confidence:
        return _reject(
            candidate,
            GuardRule.G1_IMAGE_CONFIDENCE,
            f"Image classification confidence {candidate.confidence:.2f} below "
            f"{thresholds.min_confidence:.2f}",
        )

    if candidate.category != post.category:
        return _reject(
            candidate,
            GuardRule.G2_CATEGORY,
            f"Category mismatch: expected {label(post.category)}, "
            f"detected {label(candidate.category)}",
        )

    if candidate.subject_key != post.subject_key:
        return _reject(
            candidate,
            GuardRule.G3_SUBJECT,
            f"Subject mismatch: expected {label(post.subject_key)}, "
            f"detected {label(candidate.subject_key)}",
        )

    if candidate.similarity < thresholds.min_similarity:
        return _reject(
            candidate,
            GuardRule.G4_SIMILARITY,
            f"Semantic similarity {candidate.similarity:.2f} below {thresholds.min_similarity:.2f}",
        )

    return Verdict(
        image_id=candidate.image_id,
        similarity=candidate.similarity,
        accepted=True,
        failed_rule=None,
        reason=(
            f"Subject {label(candidate.subject_key)} matches the post, "
            f"similarity {candidate.similarity:.2f} ≥ {thresholds.min_similarity:.2f}, "
            f"image confidence {candidate.confidence:.2f}"
        ),
    )


def decide(post: PostSubject, candidates: list[Candidate], thresholds: Thresholds) -> Decision:
    """Evaluate every candidate; suggest the most similar one that passes all rules.

    Candidates are sorted by similarity here (highest first), so "highest-ranked" always
    means "most similar", whatever order the caller passed them in. Every candidate gets a
    verdict, so a refusal can explain why each option was turned down.
    """
    ranked = sorted(candidates, key=lambda c: c.similarity, reverse=True)
    verdicts = [
        evaluate(post, candidate, thresholds).model_copy(update={"rank": rank})
        for rank, candidate in enumerate(ranked, start=1)
    ]
    suggestion = next((v for v in verdicts if v.accepted), None)
    return Decision(
        status="matched" if suggestion else "no_confident_match",
        suggestion=suggestion,
        verdicts=verdicts,
    )
