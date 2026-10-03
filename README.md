# AI Image Understanding & Content Matching Engine

FlyRank AI Backend Engineering internship — Capstone.

A backend that looks at an image library, understands what is actually in each image (Gemini vision →
schema-validated tags), and matches images to blog posts by **meaning**, not filenames or keywords.
Its most important feature is refusing a wrong match: a **mismatch guard** rejects candidates like a
wolf photo on a red-fox post, and answers "no confident match" with reasons when nothing is good enough.

> **Status:** Phase 1 (design) — the system is not runnable yet. Run/seed steps, architecture diagram,
> evaluation results and limitations will be added as the build progresses.

- **Design:** [DESIGN.md](DESIGN.md) — schema, guard rules, data model, API surface, layers, non-goal
- **Evidence:** [EVIDENCE.md](EVIDENCE.md) — one proof per requirement (filled in as the build progresses)
- **AI usage log:** [BUILDLOG.md](BUILDLOG.md)

## What exists so far
- The mismatch guard as a pure module with unit tests:
  ```bash
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
  .venv\Scripts\python -m pytest -v
  ```

## Stack
Python 3.11 · FastAPI · PostgreSQL (Docker Compose) · SQLAlchemy + Alembic · Pydantic ·
Gemini `gemini-2.5-flash` (vision) and `gemini-embedding-001` (embeddings) via `google-genai`.

## License
MIT — see [LICENSE](LICENSE).
