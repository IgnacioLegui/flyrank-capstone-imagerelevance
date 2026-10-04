"""Turn one image into a decision: tagged, flagged, or failed.

    for attempt in 1..max_attempts:
        ask the model  -> answer fails validation?  try again (it's logged as invalid_output)
                       -> server/network error?     try again (logged as error)
                       -> valid, confidence < min?  FLAGGED (stored, but never used as a match)
                       -> valid, confident          TAGGED
    out of attempts                                 FAILED, with the last error kept

Two things deliberately do NOT use up an attempt and are passed up to the worker instead:
- RateLimited (429): the answer wasn't wrong, we were just too fast -> the worker waits.
- BudgetExceeded: retrying can't help -> the worker stops the job and raises the alert.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.ai.gemini import CallContext, GeminiCallError, InvalidOutput, Parsed
from app.domain.vision import ImageTags


class Tagger(Protocol):
    model: str  # stored with each result, so tags from different models never get mixed up

    def tag_image(self, image_bytes: bytes, ctx: CallContext) -> Parsed[ImageTags]: ...


@dataclass
class TagOutcome:
    status: Literal["tagged", "flagged", "failed"]
    attempts: int
    tags: ImageTags | None = None
    raw_text: str | None = None
    error: str | None = None  # failed: last error; flagged: why it was flagged


def tag_one(
    image_bytes: bytes,
    tagger: Tagger,
    ctx: CallContext,
    min_confidence: float,
    max_attempts: int = 3,
) -> TagOutcome:
    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        try:
            result = tagger.tag_image(image_bytes, ctx)
        except InvalidOutput as e:
            last_error = f"attempt {attempt}: invalid output: {e}"
            continue
        except GeminiCallError as e:
            last_error = f"attempt {attempt}: call failed: {e}"
            continue

        tags = result.value
        if tags.confidence < min_confidence:
            return TagOutcome(
                status="flagged",
                attempts=attempt,
                tags=tags,
                raw_text=result.raw_text,
                error=f"confidence {tags.confidence:.2f} below {min_confidence:.2f}",
            )
        return TagOutcome(status="tagged", attempts=attempt, tags=tags, raw_text=result.raw_text)

    return TagOutcome(status="failed", attempts=max_attempts, error=last_error)
