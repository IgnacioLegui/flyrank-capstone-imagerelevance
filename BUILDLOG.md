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
