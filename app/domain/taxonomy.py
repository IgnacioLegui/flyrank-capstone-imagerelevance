"""Controlled taxonomy shared by the vision schema, post extraction and the mismatch guard.

The vision model and the post-subject extractor must pick from these fixed lists, so the
guard can compare subjects exactly ("red_fox" == "red_fox") instead of fuzzy-matching
free text ("fox" vs "red fox"). Adding a new subject means adding it here.
"""

from enum import StrEnum


class Category(StrEnum):
    ANIMAL = "animal"
    FOOD = "food"
    LANDSCAPE = "landscape"
    VEHICLE = "vehicle"
    OTHER = "other"


class SubjectKey(StrEnum):
    RED_FOX = "red_fox"
    GRAY_WOLF = "gray_wolf"
    DOG = "dog"
    BROWN_BEAR = "brown_bear"
    DEER = "deer"
    PIZZA = "pizza"
    COFFEE = "coffee"
    MOUNTAIN = "mountain"
    BEACH = "beach"
    BICYCLE = "bicycle"
    CAR = "car"
    OTHER = "other"  # the model couldn't place it in the list -> guard can't verify it


# Which category each known subject belongs to. `other` is absent on purpose: an unplaceable
# subject can sit in any category (e.g. a forest is landscape/other, a cat is animal/other).
SUBJECT_CATEGORY: dict[SubjectKey, Category] = {
    SubjectKey.RED_FOX: Category.ANIMAL,
    SubjectKey.GRAY_WOLF: Category.ANIMAL,
    SubjectKey.DOG: Category.ANIMAL,
    SubjectKey.BROWN_BEAR: Category.ANIMAL,
    SubjectKey.DEER: Category.ANIMAL,
    SubjectKey.PIZZA: Category.FOOD,
    SubjectKey.COFFEE: Category.FOOD,
    SubjectKey.MOUNTAIN: Category.LANDSCAPE,
    SubjectKey.BEACH: Category.LANDSCAPE,
    SubjectKey.BICYCLE: Category.VEHICLE,
    SubjectKey.CAR: Category.VEHICLE,
}


def check_consistent(category: Category, subject_key: SubjectKey) -> None:
    """Raise ValueError if a model answer contradicts itself (e.g. category=food, subject=red_fox).

    Used as a Pydantic validator, so an inconsistent answer is treated exactly like invalid JSON:
    rejected and retried, never silently "repaired".
    """
    expected = SUBJECT_CATEGORY.get(subject_key)
    if expected is not None and category != expected:
        raise ValueError(
            f"inconsistent tags: subject '{label(subject_key)}' belongs to category "
            f"'{label(expected)}', got '{label(category)}'"
        )


def label(value: StrEnum) -> str:
    """Human-readable form for explanations: SubjectKey.RED_FOX -> "red fox"."""
    return value.value.replace("_", " ")
