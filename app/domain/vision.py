"""Schema for what the vision model must return for each image.

The model's JSON is parsed and validated against `ImageTags` by our own code. Anything that
doesn't validate (bad JSON, unknown subject, out-of-range confidence, category contradicting
the subject) counts as invalid output and is retried or marked failed, never stored as valid.
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.domain.taxonomy import Category, SubjectKey, check_consistent

Attribute = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class ImageTags(BaseModel):
    category: Category
    subject_key: SubjectKey
    subject: str = Field(min_length=1, max_length=60, description='Free-text name, e.g. "red fox"')
    attributes: list[Attribute] = Field(min_length=1, max_length=10)
    caption: str = Field(min_length=10, max_length=300)
    confidence: float = Field(ge=0, le=1, description="How sure the model is about subject_key")

    @model_validator(mode="after")
    def _category_matches_subject(self) -> "ImageTags":
        check_consistent(self.category, self.subject_key)
        return self
