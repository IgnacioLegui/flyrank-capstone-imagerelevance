"""FastAPI application.  uvicorn app.api.main:app"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.routes import router

log = logging.getLogger("api")

app = FastAPI(
    title="Image Relevance Engine",
    description="Tags an image library with a vision model and matches images to blog posts, "
    "refusing wrong matches. Docs for each endpoint below; GET endpoints also work in a browser.",
)
app.include_router(router)


@app.exception_handler(OperationalError)
def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    # The database being down is a temporary condition, not a bug: 503, not a bare 500
    log.error("database unavailable: %s", exc.orig)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})
