# EVIDENCE

One pasted proof per requirement: a test name + its output, a curl transcript, or a log line.
Filled in as each piece is built, from real command output. Empty slot = not proven yet.

---

## Requirements checklist

### AI processing

#### R1. Vision model produces structured output validated against a schema; invalid responses are never trusted.
_Proof (2026-10-24):_ every answer is parsed by our own `ImageTags.model_validate_json` (enums for
category/subject, ranges, lengths, category↔subject consistency). Anything invalid is logged as
`invalid_output`, retried, and after 3 attempts the image is `failed` — never stored as tags.
```
tests/test_vision_schema.py::test_inconsistent_category_and_subject_rejected[food-red_fox] PASSED
tests/test_vision_schema.py::test_inconsistent_category_and_subject_rejected[vehicle-gray_wolf] PASSED
tests/test_vision_schema.py::test_inconsistent_category_and_subject_rejected[animal-pizza] PASSED
tests/test_vision_schema.py::test_inconsistent_category_and_subject_rejected[landscape-car] PASSED
tests/test_vision_schema.py::test_not_json_rejected PASSED
tests/test_gemini_wrapper.py::test_invalid_json_is_logged_and_raised_with_raw_text PASSED
tests/test_gemini_wrapper.py::test_inconsistent_answer_counts_as_invalid_output PASSED
tests/test_tagging.py::test_three_invalid_answers_fail_with_last_error PASSED
```
Real batch (job 2, gemini-3.5-flash-lite): all 50 answers passed validation (`ok=50, invalid_output=0`, see R4).

#### R2. Low-confidence classifications are flagged instead of accepted.
_Proof (2026-10-24):_ `MIN_CONFIDENCE=0.70`. Real batch output:
```
$ curl "localhost:8000/images?status=flagged"
{"id": 2, "filename": "ambiguous_02.jpg", "status": "flagged", "error": "confidence 0.40 below 0.70", "subject_key": "red_fox", "confidence": 0.4, "caption": "A close-up view of dense reddish-orange fur texture."}
{"id": 5, "filename": "ambiguous_01.jpg", "status": "flagged", "error": "confidence 0.10 below 0.70", "subject_key": "other", "confidence": 0.1, "caption": "An abstract, blurry image featuring soft green tones and light refractions."}
```
`tests/test_tagging.py::test_low_confidence_is_flagged_not_guessed PASSED`

#### R3. Images are processed through a batch background job with retries.
_Proof (2026-10-24):_ `POST /jobs/ingest-images` returned `202` immediately; the worker container ran it:
```
$ curl localhost:8000/jobs/2
{"id":2,"type":"ingest_images","status":"succeeded","progress_done":50,"progress_total":50,"attempts":0,"max_attempts":3,"run_after":"2026-10-24T13:30:49.499806Z","started_at":"2026-10-24T13:30:49.879833Z","finished_at":"2026-10-24T13:36:20.663847Z","last_error":null,"created_at":"2026-10-24T13:30:49.499806Z"}
```
Retries (invalid output ×3 per image; 429 backoff and pause; crash re-queue up to `max_attempts`):
```
tests/test_tagging.py::test_three_invalid_answers_fail_with_last_error PASSED
tests/test_worker_db.py::test_429_backs_off_then_continues PASSED
tests/test_worker_db.py::test_five_429s_in_a_row_pause_the_job_instead_of_failing PASSED
tests/test_worker_db.py::test_worker_crash_is_retried_then_failed_with_alert PASSED
tests/test_worker_db.py::test_two_workers_never_claim_the_same_job PASSED
```

#### R4. Vision and embedding costs are tracked per call.
_Proof (2026-10-24, vision; embeddings come in Phase 3):_ one `ai_calls` row per request, list-price
equivalent from `app/ai/pricing.py` (gemini-3.5-flash-lite: $0.30/1M in, $2.50/1M out incl. thinking).
```
$ curl localhost:8000/costs
{"note": "cost_usd is the paid-tier list-price equivalent; this project runs on the free tier", "total_calls": 50, "total_cost_usd": "0.03373330", "budget_usd": 1.0}
{"purpose": "vision_tag", "model": "gemini-3.5-flash-lite", "calls": 50, "ok": 50, "invalid_output": 0, "rate_limited": 0, "error": 0, "input_tokens": 68311, "output_tokens": 5296, "thinking_tokens": 0, "cost_usd": "0.03373330"}
first call: {"id": 2, "job_id": 1, "purpose": "vision_tag", "model": "gemini-3.5-flash-lite", "owner_type": "image", "owner_id": 2, "outcome": "ok", "input_tokens": 1362, "output_tokens": 70, "thinking_tokens": 0, "cost_usd": "0.00058360", "latency_ms": 4124}
last call:  {"id": 51, "job_id": 2, "purpose": "vision_tag", "model": "gemini-3.5-flash-lite", "owner_type": "image", "owner_id": 54, "outcome": "ok", "input_tokens": 1362, "output_tokens": 112, "thinking_tokens": 0, "cost_usd": "0.00068860", "latency_ms": 2502}
```
Check: 1362 × 0.30/1M + 70 × 2.50/1M = 0.0005836. `tests/test_gemini_wrapper.py::test_valid_answer_is_parsed_and_logged_with_cost PASSED`

### Matching system

#### R5. Image and post embeddings are stored; posts return ranked image suggestions.
_Proof:_

#### R6. Semantic matching works for equivalent concepts — "red fox" matches "Vulpes vulpes".
_Proof:_

### Safety layer

#### R7. The mismatch guard rejects incorrect recommendations — the wolf-on-a-fox-post scenario provably fails.
_Proof:_

#### R8. Rejections include a human-readable explanation.
_Proof:_

#### R9. When no image clears the bar, the system answers "no confident match" with reasons.
_Proof:_

### Backend

#### R10. Database models for images, tags, embeddings, posts, suggestions, approvals/rejections — with the required indexes.
_Proof:_

#### R11. API endpoints validated; the review workflow (approve / reject / inspect why) exists.
_Proof:_

### Quality & documentation

#### R12. A small labeled evaluation dataset measures top-1 precision — the number is in the README.
_Proof:_

#### R13. README with architecture explanation and diagram; the required files present.
_Proof:_

---

## Shared requirements (every capstone)

#### S1. Layered architecture — data / logic / HTTP separated.
_Proof:_

#### S2. Validation at the boundary — bad input → clean 4xx, never a 500.
_Proof:_

#### S3. ≥1 background job — slow/bulk work off the request path, retries + failure alert.
_Proof:_

#### S4. Real persistence — schema as migrations, right indexes.
_Proof:_

#### S5. Idempotency where it matters — a retried action happens once.
_Proof:_

#### S6. Secrets clean — env only, never logged, never committed.
_Proof (2026-10-24):_ key lives only in `.env` (gitignored, excluded from the Docker build context);
loaded as a `SecretStr`; only the worker container receives it.
```
$ git check-ignore .env
.env
$ git ls-files | grep -c "^.env$"
0
$ git log --all -p | grep -o "AIza[0-9A-Za-z_-]\{20,\}" | sort -u     # Google keys start with "AIza"
AIza-FAKE-TEST-KEY-1234567890                                       # the fake key used by the test below
# worker logs after the 50-image batch: lines containing the real key value
0
# api container: length of GEMINI_API_KEY (api never calls Gemini)
0
# .env present inside the built image
0
tests/test_config.py::test_api_key_is_never_printed PASSED
tests/test_gemini_wrapper.py::test_request_contains_image_bytes_but_no_filename_or_path PASSED
```

#### S7. Cost tracked (AI is used) — per call, attributed, with a budget guard.
_Proof:_

---

## Acceptance probes

#### P1. Batch job on the corpus → every image gains schema-valid tags; at least one low-confidence image is flagged, not guessed.
_Proof (2026-10-24, job 1 = 3-image smoke test, job 2 = full corpus via `POST /jobs/ingest-images`):_
```
images in DB: 50  by status: {'flagged': 2, 'tagged': 48}        # 0 failed, 0 pending
vision_tag/gemini-3.5-flash-lite: calls=50 ok=50 invalid=0 rate_limited=0 error=0
flagged: ambiguous_02.jpg  subject_key=red_fox  conf=0.40  "A close-up view of dense reddish-orange fur texture."
flagged: ambiguous_01.jpg  subject_key=other    conf=0.10  "An abstract, blurry image featuring soft green tones and light refractions."
```
Every one of the 50 images has exactly one validated `image_tags` row; the 2 deliberately ambiguous
images are the only flagged ones (full list via `GET /images?status=flagged`, see R2).

#### P2. "Red fox" article → the fox image ranks first; wolf and dog rank clearly lower.
_Proof:_

#### P3. Wolf forced as a candidate for the fox post → guard rejects it with a mismatch explanation (rule G3, subject mismatch — see DESIGN.md §3).
_Proof:_

#### P4. Post with no suitable image → "no confident match" + reasons.
_Proof:_

#### P5. Eval script → top-1 precision reported on the labeled set, matching the README.
_Proof:_

#### P6. Cost log → every vision/embedding call attributed with a cost entry.
_Proof (2026-10-24, vision calls; embeddings from Phase 3):_ 50 images → 50 requests → 50 `ai_calls`
rows, each with `job_id`, `owner_type=image`, `owner_id`, tokens and `cost_usd` (see R4 for rows).
```
total_calls=50 total_cost_usd=0.03373330 budget=1.0
images with >1 call: none
calls without job/owner attribution: 0
```
One request = one row is enforced in code: SDK retries off (`attempts=1`) and automatic function
calling off — `tests/test_gemini_wrapper.py::test_automatic_function_calling_is_disabled PASSED`.
