# Design — AI Image Understanding & Content Matching Engine

**Problem.** Given an image library and a set of blog posts, suggest the right image for each post
based on what the images *show*, not filenames or keywords — and, above all, **refuse** when the best
candidate is still wrong (a wolf on a fox post), explaining why.

**How matching works, in plain terms.** An *embedding* is a list of 3072 numbers that encodes the
meaning of a text. Texts with similar meaning get vectors pointing in similar directions, so
"red fox" and "Vulpes vulpes" end up close even though they share no words. *Cosine similarity*
measures that closeness (1.0 = same direction). We embed each image's caption and each post's
text, rank images by cosine similarity to the post, then pass the top candidates through the
**mismatch guard**, which uses the structured tags (not just the similarity score) to accept or reject.

## 1. Metadata schema (Pydantic; invalid model output is never stored as valid)
- `Category` (enum): `animal, food, landscape, vehicle, other`
- `SubjectKey` (enum): `red_fox, gray_wolf, dog, brown_bear, deer, pizza, coffee, mountain, beach, bicycle, car, other`
- `ImageTags`: `category: Category`, `subject_key: SubjectKey`, `subject: str` (free-text, e.g. "red fox"),
  `attributes: list[str]` (1–10), `caption: str` (10–300 chars), `confidence: float` (0–1)
- `PostSubject`: `category: Category`, `subject_key: SubjectKey`, `confidence: float` — extracted from the post by the LLM

The enums give the guard an exact, deterministic comparison; caption/attributes keep the rich detail for embeddings.

## 2. Pipeline (all AI work runs in the background worker, never in a request)
- **`ingest_images` job:** for each new image → `gemini-2.5-flash` vision call → validate as `ImageTags`.
  Invalid → retry (max 3, backoff) → still invalid: image `failed`, raw response kept for inspection.
  Valid but `confidence < MIN_CONFIDENCE` → `flagged` (stored, excluded from matching). Otherwise `tagged`,
  then embed `caption + subject + attributes` with `gemini-embedding-001` (`SEMANTIC_SIMILARITY`).
- **`process_posts` job:** extract `PostSubject` (validated the same way), embed `title + body`.
- **Every** Gemini call writes an `ai_calls` row (tokens, list-price-equivalent USD, latency, success).
  Before each call the worker checks total spend against `AI_BUDGET_USD` and refuses if exceeded.

## 3. Matching + mismatch guard
`GET /posts/{id}/images`: cosine-rank all `tagged` images against the post vector, take top `GUARD_TOP_K` (5),
evaluate each with the guard. Rules run in order; the **first failing rule is the human-readable reason**.

| Rule | Rejects when | Example reason |
|---|---|---|
| G5 *(post-level, checked first)* | post `subject_key = other` or post confidence < `MIN_POST_CONFIDENCE` | "Post topic is outside the image taxonomy — cannot verify any image" |
| G1 | image confidence < `MIN_CONFIDENCE` | "Image classification confidence 0.41 below 0.70" |
| G2 | image category ≠ post category | "Category mismatch: expected animal, detected food" |
| G3 | image subject_key ≠ post subject_key | "Subject mismatch: expected red fox, detected gray wolf" |
| G4 | cosine similarity < `MIN_SIMILARITY` | "Semantic similarity 0.52 below 0.65" |

- **Result:** the highest-ranked candidate that passes all rules is the suggestion. If none passes →
  `no_confident_match` plus every candidate's reason.
- **Fox vs wolf (Probe 3):** the brief calls this a "category mismatch". In our two-level taxonomy fox and
  wolf are both `animal`, so G2 passes and **G3 (subject mismatch) is the rule that rejects the wolf**.
- G5 runs before G3 so an off-taxonomy post gets a meaningful reason instead of "expected other", and so an
  image tagged `other` can never "match" an off-taxonomy post by `other == other`.
- Thresholds are **provisional** (`.env`), calibrated on real score distributions in Phase 3:
  `MIN_CONFIDENCE` (images, 0.70), `MIN_POST_CONFIDENCE` (posts, 0.50 — separate and lower, so a clear post
  is never blocked by a slightly cautious extraction), `MIN_SIMILARITY` (0.65).
- The guard is a pure module (`services/guard.py`): no DB, no AI calls → fully unit-testable.

## 4. Data model (PostgreSQL, SQLAlchemy 2.0 + Alembic migrations)
| Table | Key columns | Constraints / indexes |
|---|---|---|
| `images` | filename, sha256, status (`pending/tagged/flagged/failed`) | UNIQUE(sha256) → re-ingest is idempotent; IDX(status) |
| `image_tags` | image_id, model, category, subject_key, subject, attributes JSONB, caption, confidence, raw_response JSONB | UNIQUE(image_id, model); IDX(category, subject_key) |
| `posts` | slug, title, body, category, subject_key, subject_confidence | UNIQUE(slug) |
| `embeddings` | owner_type (`image/post`), owner_id, model, vector REAL[] | UNIQUE(owner_type, owner_id, model) |
| `suggestions` | post_id, image_id, rank, similarity, verdict (`accepted/rejected`), reasons JSONB, guard_version | UNIQUE(post_id, image_id, guard_version); IDX(post_id, verdict) |
| `reviews` | suggestion_id, decision (`approved/rejected`), note, idempotency_key | UNIQUE(idempotency_key) → retried review applies once |
| `jobs` | type, payload JSONB, status, attempts, max_attempts, run_after, last_error, progress_done/total, idempotency_key | IDX(status, run_after); UNIQUE(idempotency_key) |
| `ai_calls` | job_id, purpose, model, owner_type/id, input/output tokens, cost_usd, latency_ms, success, error | IDX(created_at); IDX(purpose) |

## 5. API surface (FastAPI; all input validated by Pydantic → bad input is a 4xx, never a 500)
- `POST /jobs/ingest-images`, `POST /jobs/process-posts` → **202** + job id · `GET /jobs/{id}` (progress) · `GET /jobs?status=failed`
- `GET /images?status=flagged` · `GET /images/{id}`
- `POST /posts` · `GET /posts/{id}` · `GET /posts/{id}/images?k=5` (ranked + verdicts, or `no_confident_match`)
- `POST /posts/{id}/images/{image_id}/check` — force one image through the guard (Probe 3)
- `POST /suggestions/{id}/approve` · `POST /suggestions/{id}/reject` (`Idempotency-Key` header) · `GET /suggestions/{id}/explain`
- `GET /costs` (totals by purpose/model + entries) · `GET /health`

## 6. Layers
```
 HTTP    app/api/            routers + request/response schemas      (no SQL, no Gemini)
   │
 Logic   app/services/       guard.py (pure) · matching.py · tagging.py
   │            │
 Data    app/repositories/   SQLAlchemy queries ── app/db/ models + Alembic migrations ── Postgres
 AI      app/ai/gemini.py    google-genai wrapper; every call → ai_calls row + budget check
 Jobs    worker/             loop: claim job (SELECT … FOR UPDATE SKIP LOCKED) → run → retry w/ backoff
```

## 7. Non-goal
**No frontend.** Review is done through API endpoints only. (Also out of scope: scaling past ~10k images —
in-Python cosine over all vectors is deliberate at this corpus size.)
