# EVIDENCE

One pasted proof per requirement: a test name + its output, a curl transcript, or a log line.
Filled in as each piece is built, from real command output. Empty slot = not proven yet.

---

## Requirements checklist

### AI processing

#### R1. Vision model produces structured output validated against a schema; invalid responses are never trusted.
_Proof:_

#### R2. Low-confidence classifications are flagged instead of accepted.
_Proof:_

#### R3. Images are processed through a batch background job with retries.
_Proof:_

#### R4. Vision and embedding costs are tracked per call.
_Proof:_

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
_Proof:_

#### S7. Cost tracked (AI is used) — per call, attributed, with a budget guard.
_Proof:_

---

## Acceptance probes

#### P1. Batch job on the corpus → every image gains schema-valid tags; at least one low-confidence image is flagged, not guessed.
_Proof:_

#### P2. "Red fox" article → the fox image ranks first; wolf and dog rank clearly lower.
_Proof:_

#### P3. Wolf forced as a candidate for the fox post → guard rejects it with a mismatch explanation (rule G3, subject mismatch — see DESIGN.md §3).
_Proof:_

#### P4. Post with no suitable image → "no confident match" + reasons.
_Proof:_

#### P5. Eval script → top-1 precision reported on the labeled set, matching the README.
_Proof:_

#### P6. Cost log → every vision/embedding call attributed with a cost entry.
_Proof:_
