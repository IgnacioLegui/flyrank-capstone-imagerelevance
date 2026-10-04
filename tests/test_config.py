"""Settings parsing, and the guarantee that the API key never shows up when settings are printed."""

import pytest
from pydantic import ValidationError

from app.config import load_settings

FAKE_KEY = "AIza-FAKE-TEST-KEY-1234567890"
BASE_ENV = {"DATABASE_URL": "postgresql://u:p@localhost:5432/db"}


def test_api_key_is_never_printed():
    s = load_settings(BASE_ENV | {"GEMINI_API_KEY": FAKE_KEY})
    assert FAKE_KEY not in repr(s)
    assert FAKE_KEY not in str(s)
    assert FAKE_KEY not in s.model_dump_json()
    assert s.gemini_api_key.get_secret_value() == FAKE_KEY  # still usable where it's needed


def test_defaults_when_unset():
    s = load_settings(BASE_ENV)
    assert s.gemini_api_key is None
    assert s.vision_model == "gemini-3.5-flash-lite"
    assert (s.min_confidence, s.min_post_confidence, s.min_similarity) == (0.70, 0.50, 0.65)


def test_env_values_override_defaults():
    s = load_settings(BASE_ENV | {"MIN_CONFIDENCE": "0.8", "GEMINI_RPM": "10", "VISION_MODEL": "x"})
    assert s.min_confidence == 0.8
    assert s.gemini_rpm == 10
    assert s.vision_model == "x"


@pytest.mark.parametrize("bad", [{"MIN_CONFIDENCE": "0,7"}, {"MIN_CONFIDENCE": "1.5"}, {"GEMINI_RPM": "0"}])
def test_invalid_values_fail_fast(bad):
    with pytest.raises(ValidationError):
        load_settings(BASE_ENV | bad)


def test_relative_images_dir_resolves_from_repo_root():
    s = load_settings(BASE_ENV | {"IMAGES_DIR": "data/images"})
    assert s.images_dir.is_absolute()
    assert (s.images_dir / "red_fox_01.jpg").exists()


def test_database_url_is_required():
    with pytest.raises(ValidationError):
        load_settings({})
