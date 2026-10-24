# BUILDLOG — AI usage log

Honest record of where the AI assistant (Claude Code) helped, where it was wrong,
and what I (Ignacio) changed or decided. Updated as the work happens, not afterwards.

---

## 2026-10-03 — Phase 1 (Design), session 1

### Reading the brief
- Claude Code read the project brief PDF. Its built-in PDF reader **failed** (needs
  `poppler`, not installed on this Windows machine); it extracted the text with a different
  file-reading tool instead.
- Because of that, I asked it to restate all 4 phases (hours + gates) and all 6 acceptance
  probes from memory, and checked them against the original brief myself. They matched.
- It noticed the brief calls the fox/wolf rejection a "category mismatch", while in our
  two-level taxonomy fox and wolf are both `animal`. Agreed: the wolf is rejected by the
  **subject** rule (G3), and DESIGN.md says so explicitly.

### Design decisions — Claude Code proposed options, I chose
| Decision | Options it offered | My choice |
|---|---|---|
| Embedding storage | `REAL[]` + cosine in Python **vs** pgvector | `REAL[]` + numpy cosine (most explainable at ~50 images) |
| Post's "expected subject" for the guard | LLM-extracted (schema-validated) **vs** hand-written field | LLM-extracted |
| Background jobs | Postgres jobs table + worker container **vs** FastAPI BackgroundTasks **vs** Procrastinate | Jobs table + worker container (`FOR UPDATE SKIP LOCKED`) |
| Image corpus | I download from a shot list **vs** Pexels API script **vs** AI downloads via browser | I download from a shot list |
| Subject comparison in the guard | Controlled taxonomy (Enums) **vs** free text + embedding similarity | Controlled taxonomy |
| Guard thresholds | Provisional now + calibrate on real scores in Phase 3 **vs** fix now | Provisional, calibrate in Phase 3 (I approve final numbers) |
| Migrations | SQLAlchemy 2.0 + Alembic **vs** raw `.sql` files | SQLAlchemy + Alembic |

### Changes I asked for on the AI's plan
- The plan originally left the mismatch guard in Phase 3 (following the phase table) and
  offered to ask me later. I overrode that: the brief says to build the guard **first** as
  its own module, so `guard.py` + unit tests are written in Phase 1, right after DESIGN.md.
- Commits: I am the sole author — no AI co-author trailers. AI help is recorded here instead.
- At one point I had it revert its own edits to the plan file; afterwards I had it re-check
  that none of the agreed points (guard first, sole authorship, G3-for-Probe-3) were lost,
  and put them back into the plan explicitly.

### DESIGN.md review — where the AI deviated from the approved plan
- **Unapproved change, caught by me:** in the DESIGN.md draft Claude Code changed the guard so that
  G5 runs *first* and also fires on low post-extraction confidence (reusing `MIN_CONFIDENCE`). The
  plan I approved had G1→G5 in order with G5 = "post subject is `other`" only. It flagged the change
  when presenting the draft, but it should have asked before writing it.
- I asked whether that was the only deviation. It re-audited and admitted it had also silently filled
  in schema details the plan didn't specify (indexes on `images.status` and
  `image_tags(category, subject_key)`; extra columns on `suggestions`, `reviews`, `jobs`, `ai_calls`).
  Additive only, no behaviour change — accepted.
- I had it walk through Probe 3 and Probe 4 under the new order. Outcome unchanged for both, and the
  new order closes a gap (an image tagged `other` could have matched an off-taxonomy post via
  `other == other`). But it also surfaced a risk *it had introduced*: with G5 reusing the 0.70 image
  threshold, a fox post extracted at e.g. 0.65 confidence would be refused entirely, breaking Probe 2.
- **My decision:** approve G5-first, but with its own threshold `MIN_POST_CONFIDENCE` (provisional
  0.50) instead of reusing `MIN_CONFIDENCE`. Applied to DESIGN.md, `.env.example`, and the guard's
  `Thresholds` model.
- Small fix while applying it: the G5 example reason named the topic ("penguin"), but `PostSubject`
  has no free-text subject field, so the guard can't know that word. Example reworded.

### Commits this session
- `.gitignore` + MIT license — committed first so `.env` can never be committed.
- BUILDLOG started; `.env.example` added.
- DESIGN.md (Phase 1 gate) + `MIN_POST_CONFIDENCE` in `.env.example`.

### Guard built first (my call, overriding the phase table)
- `app/domain/taxonomy.py` — `Category`/`SubjectKey` as `StrEnum`s plus a `label()` helper
  (`red_fox` → "red fox") used in explanations. Claude Code wrote it; small enough to read in full.
- `app/services/guard.py` — pure module. `evaluate()` runs G5 → G1 → G2 → G3 → G4, first failure is
  the reason; `decide()` sorts candidates by similarity itself (so "highest-ranked" can't depend on
  the caller's order), evaluates all of them, suggests the first accepted one. Accepted verdicts also
  carry a reason ("Subject red fox matches the post, similarity …") for the "inspect why" endpoint later.
- Not added (to avoid another unapproved deviation): a subject→category consistency check
  (e.g. rejecting a vision answer `category=food, subject=red_fox`). Worth proposing in Phase 2.
- `tests/test_guard.py` — 20 tests incl. the wolf-on-fox G3 rejection with the exact reason string,
  `other == other` gap closed by G5, and a post at 0.65 confidence still matching (proves G5 uses
  `MIN_POST_CONFIDENCE`, not the image threshold). All 20 passed on the first run.
- Since passing on the first try proves little, it ran the suite against a scratch copy of the guard
  with G3 disabled: 3 tests failed (wolf-on-fox, second-candidate-suggested, no-confident-match),
  so the tests really do protect that rule.

### README stub + EVIDENCE skeleton
- README is a stub: purpose, Phase 1 status, links to DESIGN/EVIDENCE/BUILDLOG, how to run the guard tests.
- EVIDENCE.md has an empty slot for all 13 Section 9 checklist boxes (R1–R13), the 7 shared
  requirements from 9.1 (S1–S7, also part of Section 9) and the 6 acceptance probes (P1–P6).
  Left empty on purpose — the guard unit tests prove the *logic* of R7/R8, but the probes need the
  real system, so proofs get pasted when they come from real runs.

### Shot list + resize script (I asked for numbered entries, search queries, exact filenames, CREDITS template)
- `data/SHOTLIST.md`: 50 numbered rows, each with filename, what to look for, and a search query.
  Every row is a distinct scene (fox in snow, fox cub, …) so Phase 4 eval posts can each have one
  correct image. Wolves and fox-coloured dogs (Shiba, red Husky, Corgi) are deliberate look-alikes.
- Filenames: I gave `fox_01.jpg` as an example; Claude Code used the taxonomy key instead
  (`red_fox_01.jpg`, `gray_wolf_01.jpg`) so filename prefix ↔ `SubjectKey` is 1:1 for labeling, and the
  script checks every prefix exists in the taxonomy. The pipeline must never use filenames for matching
  (the brief forbids it) — noted in the shot list.
- `scripts/resize_images.py` reads the expected names *from SHOTLIST.md* (no second copy of the list),
  resizes to 1024 px / JPEG q80, strips EXIF after applying its rotation, reports missing/unexpected
  files, and creates/extends `data/images/CREDITS.md` without overwriting rows I've filled in.
- Tested on synthetic images in a scratch folder (4000×3000 JPEG, transparent PNG, EXIF-rotated photo,
  a stray `red_fox_01 (1).jpg`, and a re-run after filling in one credit) — all behaved as intended.
- AI slip: the shot-list commit went in without its BUILDLOG entry; this entry covers it.

## 2026-10-04 — Phase 1, session 2: corpus

- I downloaded all 50 images from Unsplash into `data/raw/` (gitignored), ran the resize script, and
  filled 8 credits rows by hand (`red_fox_01–06`, `ambiguous_01–02`). The other 42 I put in a
  `credits.txt` (filename | URL | photographer) and had Claude Code merge it.
- Merge rule I set: never overwrite a row I filled by hand. It filled only empty rows (42), found no
  conflicts and no unknown filenames, then deleted `credits.txt` (never committed).
- It found two of my hand-filled rows (`red_fox_01`, `red_fox_03`) wrapped onto two lines, which breaks
  the markdown table, and re-joined them — values unchanged, shown to me as a before/after diff.
- Its completeness check first reported 49/50 rows complete; the "missing" one was `red_fox_05`, which
  is complete but has irregular spacing. Its regex was too strict, not my row wrong — left as-is.
- It looked at 5 images whose credit titles didn't obviously match the shot list or that Probe 1
  depends on: `red_fox_01` (Unsplash title says "illustration" but it's a real photo), `dog_05` (dog in
  snow ✓), `pizza_04` (overhead ✓), `ambiguous_01` (abstract green blur ✓), `ambiguous_02` (orange fur
  macro ✓, actually a cat's — good fox/dog/cat ambiguity).
- Verified: 50/50 images match the shot list (no missing, no extras), 5.52 MB total, largest 256 KB,
  none over 1024 px, no EXIF left, `data/raw/` ignored by git.
- Phase 1 gate confirmed by me; I had it push the 12 commits to GitHub.

---

## 2026-10-04 — Phase 2 (Image understanding pipeline), session 1

### Checking the official docs before hardcoding anything (I asked for this)
- **Vision model:** Google's models page now says access to the 2.5 models is limited to projects that
  used them before; new projects should use 3.5 Flash-Lite or 3.8 Flash. The brief says
  `gemini-2.5-flash`. Claude Code's plan kept 2.5-flash as default "per my choice" with a fallback;
  I corrected that: the 2.5 choice came from my own outdated brief, and with a new key 2.5-flash can
  appear in `models.list` and still 404 on `generateContent`. **Decision: default
  `gemini-3.5-flash-lite`**, configurable via `VISION_MODEL`, priced from its own pricing-page row.
- **Rate limits:** free-tier numbers are no longer published in the docs, only in my AI Studio
  dashboard (per project; 429 when exceeded). So the worker paces requests and backs off on 429,
  and pauses/resumes the job if the daily quota runs out instead of failing.
- **Structured output:** docs say output is syntactically valid JSON but values must still be
  validated — we validate everything with our own Pydantic models.
- **Embedding price:** `gemini-embedding-001` is no longer on the pricing page; $0.15/1M comes from
  Google's GA announcement. Used in Phase 3.

### Design rules I set for Phase 2
- The **filename must never reach Gemini** — `red_fox_01.jpg` literally contains the expected label,
  so sending it would let the model "cheat". Images are sent as inline bytes (no Files API upload,
  which carries a name), and a test will check the request contains no filename.
- The 3-image smoke test must use specific images, without adding an API parameter just for that →
  a CLI script creates that job.
- Worker must fail loudly if the image folder is missing or empty; images mounted read-only.
- The 20 existing guard tests must pass **unedited** after adding the consistency check.

### Step 1 — category/subject consistency check (deferred from Phase 1)
- `SUBJECT_CATEGORY` mapping in `taxonomy.py` (`other` deliberately unmapped: can be any category)
  and `check_consistent()`, used as a Pydantic validator on the new `ImageTags` vision schema and on
  the guard's `PostSubject`. An answer like `category=food, subject=red_fox` is *invalid output*
  (retried), not auto-corrected — correcting it would hide that the model was confused.
- Ran the unedited `test_guard.py` first (`git diff -- tests/` empty): 20/20 pass. Then added
  `test_vision_schema.py` (26 tests). Total 46 passing.

### Step 2 — settings + dependencies
- `app/config.py`: settings from env/.env (python-dotenv), validated by Pydantic so a bad value like
  `MIN_CONFIDENCE=0,7` fails at startup. `GEMINI_API_KEY` is a `SecretStr`; a test checks a fake key
  never appears in `repr`/`str`/JSON of the settings. `.env.example` gained `VISION_MODEL`
  (default `gemini-3.5-flash-lite`), `GEMINI_RPM`, `IMAGES_DIR`.
- `google-genai` is now on **major version 2.x** (2.28); the brief's snippets were written for 1.x.
  Claude Code noted it will check the real 2.x API before writing the Gemini wrapper (step 5).
- **Environment problem:** Windows Application Control on my machine blocked SQLAlchemy 2.1's compiled
  Cython modules (`DLL load failed … _cache_key_cy`). Claude Code did not touch the security policy;
  it installed SQLAlchemy's official pure-Python wheel (same version, `has_compiled_ext() == False`)
  into the local venv only. Docker/Linux is unaffected. Documented in README for evaluators on Windows.
  (psycopg's binary build also failed the very first import, then imported fine — likely the policy
  evaluating a brand-new file; noted, no action needed.)

### Step 3 — Docker Compose (Postgres) + DB session
- `docker-compose.yml` with `db` (postgres:16-alpine, healthcheck with `pg_isready`, named volume).
  `api` and `worker` services come in step 8, once there's code for them to run.
- `Dockerfile` written now (python:3.11-slim) but first built in step 8 — it copies folders
  (`alembic/`, `worker/`) that steps 4 and 7 create. `.dockerignore` excludes `.env`, so the key can
  never be baked into an image; compose passes env vars at runtime.
- `app/db/session.py`: engine + `session_scope()` (commit on success, rollback on exception).
  Rewrites `postgresql://` to `postgresql+psycopg://` so the `.env.example` URL works with psycopg 3.
- Docker Desktop wasn't running; Claude Code started it. Verified: db container healthy,
  `session_scope()` connects from the host (PostgreSQL 16.15, driver psycopg).

### Step 4 — models + first Alembic migration
- `app/db/models.py` (images, image_tags, jobs, ai_calls) and a **hand-written** migration
  `0001_images_jobs_costs.py` (not autogenerated, so every line is deliberate and readable).
  Posts/embeddings/suggestions/reviews get their own migrations in Phases 3–4.
- Status columns are strings + CHECK constraints instead of Postgres ENUM types (DB still rejects
  unknown values; adding a value later is a one-line constraint change). Verified: inserting
  `status='maybe'` fails with `violates check constraint "status_allowed"`.
- `cost_usd` is `NUMERIC(12,8)`, not float, so summed costs are exact.
- Verified: `alembic upgrade head` → `alembic check` reports "No new upgrade operations detected"
  (models and migration agree) → `downgrade base` → `upgrade head` again, clean both ways.
- Additions beyond the approved plan, both small: `ai_calls.thinking_tokens` (thinking tokens are billed
  at the output price, so I keep them in their own column to make the cost formula checkable row by
  row) and an index on `images.filename` (the smoke-test script looks images up by filename).

### Step 5 — pricing + Gemini wrapper
- Re-fetched the pricing page before writing `pricing.py`. `gemini-3.5-flash-lite` row, verbatim:
  input "$0.30 (text / image / video / audio)", output "$2.50" "including thinking tokens".
  Each price records its source URL and check date; a model without a price can't be called.
- Checked the real **google-genai 2.28** API instead of trusting the brief's 1.x snippets:
  `models.generate_content`, `types.Part.from_bytes`, `response_json_schema` and
  `usage_metadata.thoughts_token_count` all exist. Read the SDK source: with no retry options it
  never retries; the wrapper sets `attempts=1` explicitly anyway — a hidden SDK retry would be a
  billable request with no cost row.
- **Filename never reaches Gemini:** `tag_image()` takes only `bytes`, sends them with
  `Part.from_bytes` (no Files API, no display name), and the prompt contains no file info. Test
  `test_request_contains_image_bytes_but_no_filename_or_path` serializes the whole request built from
  the real `red_fox_01.jpg` and asserts no "red_fox_01", ".jpg" or path appears in it.
- One cost row per request, whatever happens: `ok`, `invalid_output` (bad JSON, inconsistent
  category/subject, no text — tokens still billed), `rate_limited` (429; server's `retryDelay`
  parsed), `error`. Budget checked before every request.
- Pydantic's schema puts enums in `$defs` + `$ref`; Gemini's JSON-schema support is partial, so
  `inline_refs()` substitutes them before sending. Whether Gemini accepts it is confirmed only in the
  real smoke test.
- `DbCostLog` (ai_calls repository) commits each cost row in its own transaction, so a call is never
  "un-logged" by a later rollback. Smoke-checked against Postgres. 68 tests passing.

### Step 6 — tagging service
- `app/services/tagging.py::tag_one()`: up to 3 attempts; invalid output or server/network error uses
  an attempt; valid + confidence < `MIN_CONFIDENCE` → **flagged** (kept, never matched); valid and
  confident → **tagged**; out of attempts → **failed** with the last error. 429 and budget-exceeded
  are passed up to the worker without using an attempt (being too fast isn't a wrong answer).
- Small change to the step-5 wrapper: it now returns `Parsed(value, raw_text)` so
  `image_tags.raw_response` stores the model's JSON exactly as received, not our re-serialized copy.
- 8 tests with a scripted fake tagger. 76 tests passing.

### Step 7 — job queue + worker
- `app/repositories/jobs.py`: `claim_next()` uses `SELECT … FOR UPDATE SKIP LOCKED` so two workers
  can never take the same job; idempotent `create_job()` by key; `requeue_running()` at start-up for
  jobs orphaned by a dead worker (valid because we run a single worker — noted in the code).
- `app/services/ingest.py`: the batch job. Fails loudly (job `failed` + `ERROR "ALERT job N failed"`)
  if `IMAGES_DIR` is missing, empty, or a requested `only` file doesn't exist — my requirement.
  Registers files with `ON CONFLICT (sha256) DO NOTHING`, then tags pending images one by one.
  Progress is recomputed from the DB each round, so a paused/crashed job resumes without re-tagging.
- 429 handling: server `retryDelay` if given, else 30/60/120 s; after 5 consecutive 429s the job
  is re-queued 1 h later (not failed, attempts not counted). Budget exceeded → job failed + alert.
- `app/ai/pacing.py`: `Pacer` spaces requests ≥ 60/GEMINI_RPM s apart; plugged into `GeminiVision`
  so retries are paced too. Tested with a fake clock.
- `worker/main.py`: poll loop; an unexpected crash re-queues the job with a growing delay, and after
  `max_attempts` (3) marks it failed with the alert. Logs whether the key is set — never the key.
- Tests run against a separate `imagerelevance_test` database (auto-created + migrated; skipped if
  Postgres is down): 17 integration tests incl. the SKIP LOCKED claim with two open sessions,
  idempotent re-ingest (tagger called 3 times for 2 jobs over 3 images), missing/empty corpus alerts,
  the 5×429 pause, and crash → retry → fail. **95 tests passing.**
- Two bugs caught while writing this step: (1) the repository first imported a type from the
  services layer (wrong direction for the layered design) — changed to plain arguments;
  (2) Alembic's `fileConfig()` by default *disables existing loggers*, which would have silenced the
  worker's `ALERT` log line whenever migrations run in the same process — fixed with
  `disable_existing_loggers=False`.

### Step 8 — API + compose services + smoke-test script
- Endpoints: `/health`, `POST /jobs/ingest-images` (202; same `Idempotency-Key` → same job, 200),
  `GET /jobs/{id}`, `GET /jobs?status=`, `GET /images?status=`, `GET /images/{id}` (tags + raw
  model JSON + every Gemini call for that image), `GET /costs` (totals per purpose/model + one entry
  per call). Typed params (ints, enums, bounded lengths) → bad input is a 422; unknown id → 404;
  database down → 503 via an exception handler, not a bare 500.
- Idempotency race handled: two simultaneous POSTs with the same key → the UNIQUE constraint lets one
  insert win (inside a savepoint) and the other returns that job instead of a 500.
- `scripts/enqueue_ingest.py --only …` creates the `{"only": [...]}` job through the same repository;
  the API has no such parameter (test: a body sent to the API is ignored, payload stays `{}`).
- Compose: `api` runs `alembic upgrade head` then uvicorn; `worker` starts only after the API is
  healthy (= migrations done), with `./data/images` mounted **read-only**. `.env` is optional
  (`required: false`). Extra I added: the `api` container gets `GEMINI_API_KEY=""` — it never calls
  Gemini, so it shouldn't hold the key (least privilege).
- Verified in containers: worker sees 50 images; `touch` on the mount → "Read-only file system";
  no `.env` inside the image; key length 0 in `api`, present in `worker` (checked without printing
  it); `/health` ok, `/docs` 200, `/costs` empty, `?status=maybe` → 422, `alembic current` → 0001.
- 22 API tests. **117 tests passing.** (One harmless warning: Starlette suggests `httpx2` for its
  test client; left visible rather than hidden.)
- Stopped here: step 9 (smoke test with real Gemini calls) waits for my RPM/RPD numbers.

### Step 9 — 3-image smoke test (first real Gemini calls)
- AI Studio shows RPM 15 / RPD 500 for `gemini-3.5-flash-lite` on my project. I set `GEMINI_RPM=10`
  (headroom under 15). Worker recreated (a plain restart doesn't re-read `.env`); log confirms `rpm=10.0`.
- Job 1 via `scripts/enqueue_ingest.py --only red_fox_01.jpg gray_wolf_01.jpg ambiguous_02.jpg`:
  succeeded 3/3, requests ~6 s apart (pacing works), 1 HTTP request and 1 `ai_calls` row per image.
  - `red_fox_01` → tagged `red_fox`, confidence 0.98
  - `gray_wolf_01` → tagged `gray_wolf`, confidence 0.95
  - `ambiguous_02` (orange cat-fur macro) → **flagged**: `subject_key=red_fox`, subject "red fox fur",
    confidence 0.40. Low confidence → excluded from matching. Note: the prompt says to use `other`
    when unsure, but the model still picked `red_fox` (with a low score) — the confidence threshold,
    not the label, is what saved it.
- Gemini accepted our inlined JSON schema (no 400). `thoughts_token_count` was 0 for all 3 calls
  (Flash-Lite didn't think). ~1,370 input tokens per image. Cost check by hand for call 2:
  1362 × $0.30/1M + 70 × $2.50/1M = $0.0005836 = stored `0.00058360`. Total for 3 calls: $0.0019244.
- Security check: grepped the worker logs for the key value → 0 matches. The logged request URL has
  no key (the SDK sends it as a header).
- Noticed: the SDK logs "AFC is enabled with max remote calls: 10" (automatic function calling).
  It only acts when tools are passed — we pass none, and the logs show exactly 1 request per call.
  Proposed disabling it explicitly as a safeguard; waiting for my go.
- Explained a gap: image/ai_call ids start at 2 — the CHECK-constraint test insert in step 4 and the
  cost-log smoke check in step 5 consumed sequence values (Postgres sequences don't roll back).
  Real DB contains only the smoke-test data; tests use the separate `imagerelevance_test` DB.

## 2026-10-24 — Phase 2, session 2: full batch

- I said "go + disable AFC" and asked the final report to also list every image whose `subject_key`
  differs from its filename prefix — read-only, no label/threshold/image changes.
- AFC disabled explicitly: `automatic_function_calling=AutomaticFunctionCallingConfig(disable=True)`
  on the vision request, plus test `test_automatic_function_calling_is_disabled`. 118 tests passing.
- Environment hiccup: Docker Desktop had stopped again; Claude Code started it, the engine took
  ~4 minutes to come up. Meanwhile the DB tests were *skipped* (not failed) as designed — but each
  one waited for a connection timeout, so that run took 4m23s instead of ~5 s.

### Step 10 — full batch (job 2, started through `POST /jobs/ingest-images`)
- Succeeded 50/50 in 5 min 31 s; the 3 smoke-test images were skipped (already done), 47 new calls.
  50 calls total, all `ok`: 0 invalid output, 0 rate-limited (10 RPM under my 15), 0 errors, 0 retries.
- **Flagged (2):** `ambiguous_01` (abstract blur) → `other`, 0.10; `ambiguous_02` (orange fur macro)
  → `red_fox`, 0.40. No failed images.
- **Confidence distribution:** extremely bimodal — 48 images at ≥ 0.95 (0.95 ×8, 0.98 ×17,
  0.99 ×16, 1.00 ×7), 2 images below 0.5, nothing between 0.5 and 0.95. Any `MIN_CONFIDENCE`
  between 0.41 and 0.95 gives exactly the same result — worth knowing for Phase 3 calibration:
  the model's self-reported confidence separates "clear" from "unclear" images but barely ranks
  within the clear ones.
- **`subject_key` vs filename prefix:** every non-ambiguous image matches its prefix (48/48),
  including the fox-coloured dogs (Shiba Inu, red Husky, Corgi → `dog`, 0.95–1.00) and all 5 wolves
  (`gray_wolf`, 0.95–0.98). Only differences: the two `ambiguous_*` images (prefix isn't a subject).
- Cost: $0.0337 list-price equivalent (free tier → $0 actual); ~1,366 input tokens per image;
  0 thinking tokens. Median latency 4.5 s, max 33.2 s.
- **Issue found during the run:** I asked for a status check when the log went quiet; it was a
  single 33 s response from Gemini (`mountain_02`), not a hang. But it showed the Gemini request has
  **no timeout** — a request that never returned would leave the job `running` forever. Not changed
  mid-batch; proposed as a fix (needs my approval).
- Image ids run 2–54 for 50 images: `ON CONFLICT DO NOTHING` still consumes a sequence value for
  each skipped duplicate (the 3 smoke-test files re-registered by job 2) — harmless, explained.
- Secrets check: the only "AIza…" string in the whole git history is the fake key in
  `tests/test_config.py`; 0 log lines contain the real key; the api container has no key.
- EVIDENCE.md filled for R1–R4, S6, P1, P6 with the real output above.
- Phase 2 gate verified by me.

### Gemini request timeout (approved by me after the gate)
- `GEMINI_TIMEOUT_S` (default 60, configurable). I asked Claude Code to check the unit instead of
  assuming: in the installed google-genai 2.28, `HttpOptions.timeout` is **milliseconds (int)** —
  its docs say so and `get_timeout_in_seconds()` divides by 1000 before calling httpx. Conversion
  lives in one function, `timeout_ms()`.
- Proof uses the **real SDK client** against a local fake Gemini server (`tests/test_timeout.py`)
  that hangs 4 s on chosen requests: with a 0.5 s timeout the call gives up after ~0.5 s with an
  `error` cost row ($0); in a 2-image job the first image's first try times out, it is retried and
  tagged, the second image is tagged, the job succeeds — rows: error, ok, ok.
- Checked the tests can fail: with the conversion made 1000× too long, the two hung-request tests
  fail (they wait out the hang); 1000× too short, the timing test fails (it gives up too early).
  Honest limitation: the "too short" case is caught only by that timing bound — a 1 ms timeout still
  happens to succeed against a local server, so the other tests don't notice it.
