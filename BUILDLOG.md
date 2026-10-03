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

### Commits this session
- `.gitignore` + MIT license — committed first so `.env` can never be committed.
