# Questions Intelligence — phase 4 audit

Base: main ba42fc7 after PR28. Owner confirmed Neon revision 6f12b8e4a903; Vercel Production and Northflank deployed that exact merge. Read-only live/ready/frontend checks returned200 and radar/version routes are present. No authenticated production writes were performed.

Reuse Question/QuestionAttempt, existing exam/quiz generation, owned notebook/topic scopes, activity locks and idempotency receipts. Existing source/provenance and attempt evidence JSON can carry typed provenance, optional confidence/skipped/answer-change metadata. Existing error causes remain readable and map to the new taxonomy without rewriting history.

Provider contracts must distinguish user-created, imported, official and AI-generated questions. Official provenance requires verified source evidence, never a user-provided label. Future external providers remain unavailable until an authorized integration exists; no Tec/QConcursos scraping.

Error-bank recovery requires a later individual answer to the same scoped question identity, not an unrelated correct answer in the topic. Clusters are heuristic suggestions over distinct questions with evidence IDs, not diagnoses or changed answer facts. Generated questions need bounded context and deterministic validation; AI validation, when used, is a separate bounded call, not unlimited regeneration or a claimed guarantee of correctness.

## Implementation

Provider-neutral serialization labels each question as official, imported, user_created, ai_generated or unknown. The manual, import, official and generated contracts share this serializer; an external provider is explicitly unavailable. AI wins over conflicting official metadata; official requires server-verified evidence. Existing imported questions retain their imported label, which does not assert that extracted/inferred answer sheets are verified. Exam and error screens show provenance; legacy unverified origins stay unknown. Blueprint assembly preserves the original source, AI flag and validation context rather than replacing them with the assembly method.

Optional confidence (`guess`, `uncertain`, `confident`), answer changes, time and skipped evidence are stored on canonical attempts. Manual practice can skip and redo the exact owned question identity without rewriting its statement. Exam submission accepts the same optional metadata and preserves blank answers as skipped facts. Skips do not contribute to mastery, adaptive review, notebook totals, question statistics, progress history, learning summaries or practice-only streaks or the assistant topic summary. Legacy aggregate evidence without an answered flag remains counted. Whole-exam weighted grading continues to include every exam question in its denominator. The expanded error taxonomy retains readable historical causes.

The error bank groups by scoped question identity, counts recurrences and uses only a later correct answer to that same question for recovery. Related topic reviews and evidence IDs remain inspectable. Forensics requires three distinct normalized question texts in the same owned topic/cause, stores at most50 heuristic suggestions and never changes original answers. User dismissal persists across recomputation. Active suggestions whose grouping no longer exists are hidden. Terms and cause are evidence of recurrence, not confirmed concept diagnoses; analysis does not call an LLM.

The topic laboratory lets the user choose target difficulty and uses syllabus/selected canonical topic, up to3 owned notes, or up to20 wrong attempts (bounded500-attempt source sample within the selected topic). Context is bounded12000 characters; the selected topic precedes any truncation. A batch is capped20 questions. Structural validation checks bounded text/explanation, distinct options, coherent option labels and an answer matching exactly one option. Textual multiple-choice answers are converted to the letter submitted by the UI; true/false answers retain their option text. Accepted laboratory questions are renumbered sequentially after discards. A separate free-first validation task checks coherence and context support; low confidence or malformed validations are discarded before saving. This is a check, not a guarantee of correctness. Legacy generation remains marked `legacy_generation`, never falsely claiming the new validation ran.

Generation uses a durable reservation in existing activity receipts, committed in a short per-user transaction before provider calls. An in-progress same-key request returns a typed409; the UI retains its key for retry. Completed retries return the saved result without provider calls. No transaction, database connection or user lock is held across generation/validation; real credential and usage operations remain safe on the small connection pool. A crashed reservation expires after15 minutes; a replaced lease fences the old worker from saving or deleting a newer result. Saving questions, XP and the completed receipt is atomic. Normal failures release only their own reservation and may consume provider quota; deliberate retries after failure can call the provider again. Text laboratory calls also allow Groq-only configuration through the shared router; PDF import still requires Gemini. There is no regeneration loop, paid fallback or real provider call in tests.

## Migration gate

`b73a16ce9024`, parent `6f12b8e4a903`, adds only owned `question_insights` with unique fingerprint, status constraint and owner/program/status index. It does not backfill or alter questions/attempts. Downgrade removes suggestions only. Local round-trip testing verifies canonical question/attempt facts survive.

MIGRATION REQUIRED

```text
revision: b73a16ce9024
down_revision: 6f12b8e4a903
comando: python -m alembic upgrade head
working directory: backend
database: Neon via DATABASE_URL_DIRECT
```

Use `feat/questions-intelligence` containing this revision, not the old main checkout. No production migration or merge is performed automatically. Await owner confirmation of `alembic current` returning this new head. The current readiness check requires exact migration heads, so applying it before deploying matching code may temporarily return503 from readiness; live remains independent. After confirmation, merge and verify both exact-SHA deployments and health checks before phase5.
