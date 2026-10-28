# Sirius — current handoff

## Published state — 2026-10-28

PR78 merged as `a70efe1369a3db62591548d101ad2780ed7e3fc6`, reviewed head
`9ed27a1c6022fb60a559985cf7e9e286baa6786f`. Four head and merge workflows passed;
independent Codex CLI review clean with pinned runtime. Northflank7384715830 and
Vercel Production7384853568 succeeded at the exact merge. Health live/ready and
frontend200;20 protected anonymous reads401; frontend/PWA at five widths passed.
Source IDs/pages and primary coverage IDs are now constrained on transport.
[PR78](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/78).

## Actual Issue65 state — still unresolved

Saved70-page PDF/checkpoints/history intact. **22/120** attempts, **0/70** inventory
leaves and zero roles validated, minimum known162, queue paused. The protected
pipeline's last pilot passed citation/value checks and then failed exact block
coverage: `inventory_coverage_mismatch`, reference
`8edf31f5-3c71-48ab-b1eb-600f69757a1c`. Do not infer any validated role from it.
No private generated response was retained. Runtime extraction route remains
`groq / openai/gpt-oss-120b`, selected by the existing Northflank setting
`AI_ROUTE_EDITAL_EXTRACT=reasoning`; only this public setting was changed after
owner login. No budget extension, new upload or full queue release.

## Current correction and next action

Branch `codex/edital-total-coverage-65`, no migration. Provider-only inventory
transport has semantic class templates and a total primary-ID→class-index map.
Every primary block is required exactly once; unknown/missing IDs, invalid indexes
and unused templates are rejected. The adapter groups only adjacent explicit
choices into original canonical ranges. It neither fills missing decisions nor
invents/discards semantics. Original InventoryUnit JSON Schema/Pydantic and source
comparison remain mandatory. Duplicate JSON keys are rejected for source-bound
responses. Public/stored contracts and histories remain unchanged. Transport/9
requires a new controlled pilot without resetting attempts.

Finish all four full CI workflows and independent final-SHA Codex review before
merge. Confirm exact deploys and safe production reads, then one saved pilot.
Require validated/consolidated data before claiming recovery. Full queue release
or a budget extension still needs owner confirmation; the free plan has quotas.
No new services, credentials in chat or paid infrastructure.

## Continuity

Preserve phases1–14 and all other modules; no new phase authorized. Do not redo
notificationsPR55/56, deletionPR64 or PDF extractionPR62. Backlog only: OCR,
rectifications, heterogeneous real homologation and workout generation issues.
Safe dev-cache cleanup authorized but automatic approval blocked recursive Babel
cache deletion without a specific reason. Nothing deleted; do not bypass.
Previous handoff preserved in [history](docs/history/HANDOFF_BEFORE_EDITAL_TOTAL_COVERAGE.md).
The [Issue65 ledger](https://github.com/jpedrosampaio/SiriusFrontAndBack/issues/65#issuecomment-6319387161)
contains current delivery receipts and older evidence. Use AGENTS.md and
DEVELOPMENT_CONTEXT.md for permanent gates and targeted context.
