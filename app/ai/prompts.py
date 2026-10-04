"""Prompt sent with every image. The allowed values are generated from the taxonomy enums, so the
prompt can never list a subject the schema would then reject.

Note what is NOT here: no filename, no path, no hint of the expected answer. The model gets
only these instructions and the image's pixels.
"""

from app.domain.taxonomy import Category, SubjectKey


def _values(enum) -> str:
    return ", ".join(member.value for member in enum)


VISION_TAGGING_PROMPT = f"""You are an image tagging system. Look only at what the image actually shows.

Return JSON with these fields:
- category: one of [{_values(Category)}]
- subject_key: one of [{_values(SubjectKey)}]. Pick the main subject of the image.
  Use "other" if the main subject is not in this list, or if you cannot clearly identify it.
- subject: a short free-text name of the main subject (e.g. "red fox", "golden retriever").
- attributes: 1 to 10 short visual attributes (colors, setting, pose, season, ...).
- caption: one factual sentence describing the image (10 to 300 characters).
- confidence: a number from 0 to 1: how certain you are that subject_key is correct.
  Be honest: if the image is blurry, abstract, too close-up, or could plausibly be several
  different subjects, give a low confidence (below 0.5) rather than guessing.

category must agree with subject_key (e.g. red_fox, gray_wolf, dog, brown_bear, deer are animals)."""
