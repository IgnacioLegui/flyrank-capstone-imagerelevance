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


def label(value: StrEnum) -> str:
    """Human-readable form for explanations: SubjectKey.RED_FOX -> "red fox"."""
    return value.value.replace("_", " ")
