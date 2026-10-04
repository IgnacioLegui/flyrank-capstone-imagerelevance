FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code only. Images are mounted at runtime (read-only); .env is never copied into the image
# (see .dockerignore) — compose passes the variables in at runtime instead.
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY worker ./worker
COPY scripts ./scripts
