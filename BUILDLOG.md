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
