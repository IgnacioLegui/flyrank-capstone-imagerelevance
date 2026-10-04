"""HTTP layer: validates input, calls repositories, shapes output. No SQL and no Gemini calls here.

Every parameter is typed (ints, enums, bounded lengths), so bad input is rejected by FastAPI with
a 422 before any of our code runs; unknown ids give 404. Neither is ever a 500.
"""

from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    CallDetailOut,
    CallOut,
    CostsOut,
    CostTotal,
    ImageDetailOut,
    ImageOut,
    ImageStatus,
    JobOut,
    JobStatus,
)
from app.config import get_settings
from app.db.session import session_scope
from app.repositories import ai_calls as calls_repo
from app.repositories import images as images_repo
from app.repositories import jobs as jobs_repo

router = APIRouter()

Id = Annotated[int, Path(ge=1, le=2_147_483_647)]
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


DB = Annotated[Session, Depends(get_session)]


@router.get("/health", tags=["meta"])
def health(session: DB) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


# --- Jobs -----------------------------------------------------------------------------------------

@router.post(
    "/jobs/ingest-images",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
    summary="Queue the batch job that tags every image in the corpus",
    responses={200: {"description": "A job with this Idempotency-Key already exists; it is returned"}},
)
def create_ingest_job(
    session: DB,
    response: Response,
    idempotency_key: Annotated[
        str | None, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ] = None,
) -> JobOut:
    """Returns immediately (202); the worker does the slow AI work in the background.
    Sending the same Idempotency-Key again returns the original job instead of starting another."""
    job, created = jobs_repo.create_job(session, jobs_repo.INGEST_IMAGES, {}, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return JobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
def get_job(job_id: Id, session: DB) -> JobOut:
    job = jobs_repo.get_job(session, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"job {job_id} not found")
    return JobOut.model_validate(job)


@router.get("/jobs", response_model=list[JobOut], tags=["jobs"])
def list_jobs(session: DB, status: JobStatus | None = None, limit: Limit = 50) -> list[JobOut]:
    return [JobOut.model_validate(j) for j in jobs_repo.list_jobs(session, status, limit)]


# --- Images ---------------------------------------------------------------------------------------

@router.get("/images", response_model=list[ImageOut], tags=["images"])
def list_images(
    session: DB, status: ImageStatus | None = None, limit: Limit = 100, offset: Offset = 0
) -> list[ImageOut]:
    return [ImageOut.model_validate(i) for i in images_repo.list_images(session, status, limit, offset)]


@router.get("/images/{image_id}", response_model=ImageDetailOut, tags=["images"])
def get_image(image_id: Id, session: DB) -> ImageDetailOut:
    """One image with its tags, the raw model JSON, and every Gemini call made for it."""
    image = images_repo.get_image(session, image_id)
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"image {image_id} not found")
    calls = calls_repo.list_calls(session, limit=500, offset=0, owner_type="image", owner_id=image_id)
    return ImageDetailOut.model_validate(
        {
            **ImageOut.model_validate(image).model_dump(),
            "sha256": image.sha256,
            "tags": image.tags,
            "calls": [CallDetailOut.model_validate(c) for c in calls],
        }
    )


# --- Costs ----------------------------------------------------------------------------------------

@router.get("/costs", response_model=CostsOut, tags=["costs"])
def costs(session: DB, limit: Limit = 500, offset: Offset = 0) -> CostsOut:
    totals = [CostTotal.model_validate(t) for t in calls_repo.totals_by_purpose_and_model(session)]
    return CostsOut(
        note="cost_usd is the paid-tier list-price equivalent; this project runs on the free tier",
        total_calls=calls_repo.count_calls(session),
        total_cost_usd=sum((t.cost_usd for t in totals), Decimal(0)),
        budget_usd=get_settings().ai_budget_usd,
        by_purpose_and_model=totals,
        calls=[CallOut.model_validate(c) for c in calls_repo.list_calls(session, limit, offset)],
    )
