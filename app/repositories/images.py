"""Image rows: registering files from disk and storing tagging outcomes."""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Image, ImageTag
from app.domain.vision import ImageTags


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register_files(session: Session, paths: Iterable[Path]) -> int:
    """Insert one 'pending' row per file. A file whose content (sha256) is already registered is
    skipped by the database itself (ON CONFLICT DO NOTHING), so re-running ingest never duplicates.
    Returns how many new rows were inserted."""
    inserted = 0
    for path in paths:
        result = session.execute(
            insert(Image)
            .values(filename=path.name, sha256=sha256_of(path), status="pending")
            .on_conflict_do_nothing(index_elements=["sha256"])
        )
        inserted += result.rowcount
    return inserted


def images_in_scope(session: Session, filenames: list[str]) -> list[Image]:
    return list(
        session.scalars(select(Image).where(Image.filename.in_(filenames)).order_by(Image.filename))
    )


def save_outcome(
    session: Session,
    image: Image,
    model: str,
    status: str,
    error: str | None,
    tags: ImageTags | None,
    raw_text: str | None,
) -> None:
    image.status = status
    image.error = error
    if tags is None:
        return
    values = {
        "image_id": image.id,
        "model": model,
        "category": tags.category.value,
        "subject_key": tags.subject_key.value,
        "subject": tags.subject,
        "attributes": tags.attributes,
        "caption": tags.caption,
        "confidence": tags.confidence,
        # The model's JSON exactly as received (it already passed validation, so it parses)
        "raw_response": json.loads(raw_text) if raw_text else {},
    }
    # One row per (image, model): re-tagging with the same model replaces the old result
    stmt = insert(ImageTag).values(**values)
    session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_image_tags_image_model",
            set_={k: stmt.excluded[k] for k in values if k not in ("image_id", "model")}
            | {"created_at": func.now()},
        )
    )
