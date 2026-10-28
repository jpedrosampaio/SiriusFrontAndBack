# Sirius — current handoff

## Published state — 2026-10-28

PR76 merged as `65b4924806d629abde2df8e1bcaa6158c5414c37`, reviewed head
`a38e8ae1fb665950fe30c1b5f195127d89814551`. All four head workflows and independent
Codex CLI review passed. Northflank7382750360 and Vercel Production7382773650
succeeded at the exact merge. Health/live, health/ready, frontend200;20 protected
anonymous reads401; frontend/PWA at all five widths passed. Merge CI remains
tracked in [PR76](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/76).
A supplementary asset verifier initially failed due to JS escaping/encoding;
UTF-8 and JS literal decoding fixed the verifier, with the same assertions passing.

## Active Issue65: actual documentary rejection identified

Saved70-page PDF, checkpoints and history remain intact. One PR76 pilot moved
18→19/120 attempts; zero of70 inventory leaves and zero roles validated. New
finite diagnostic: `value_not_supported_by_excerpt`, reference
`525d214b-1b99-451b-acd9-acf580ee787b`, Groq Qwen3.8-27b. A proposed value was not
literally supported by its own cited excerpts. The exact private field/value was
not captured. Prior PR75 provider HTTP200 proved acceptance only, not valid data.
Queue is paused; budget120, minimum forecast159. No upload or full queue release.

## Current correction and next action

Branch `codex/edital-literal-facts-65`: tell the model explicitly to copy each
non-null value from its own quote, preserving wording, numeric separators, dates
and units. Keep original evidence/Pydantic gates, no output repair or omission of
available facts. Transport/7 requires a new pilot without resetting history/budget.
Directed regression also proved that numeric token parts ('1' from '1.000') could
pass the old boundary check; reject such parts while preserving full numbers and
ordinary sentence punctuation. This separate numeric bug was reproduced with
synthetic data, not asserted as the observed private model value.

Obtain four complete CI workflows and final independent Codex review before merge.
No migration or paid service. After exact deploys/read-only checks, run one controlled
pilot using the saved analysis. Require validated and consolidated documentary data
before claiming recovery. Never release all units or extend budget without owner
confirmation. Chrome reconnected and working as browser4 during this session.

## Continuity

Preserve phases1–14 and all other modules. No new phase authorized. Do not repeat
notificationsPR55/56, deletionPR64 or PDF extractionPR62. Backlog only: OCR,
rectifications, heterogeneous real homologation and workout generation issues.
Safe dev-cache cleanup authorized, but automatic approval blocked recursive Babel
cache deletion without a specific reason. Nothing deleted; do not bypass.
Previous handoff preserved in [history](docs/history/HANDOFF_BEFORE_EDITAL_LITERAL_FACTS.md),
including older intact records. Current delivery evidence stays in the
[Issue65 ledger](https://github.com/jpedrosampaio/SiriusFrontAndBack/issues/65#issuecomment-6319387161).
Use AGENTS.md and docs/DEVELOPMENT_CONTEXT.md for permanent gates and targeted reads.
