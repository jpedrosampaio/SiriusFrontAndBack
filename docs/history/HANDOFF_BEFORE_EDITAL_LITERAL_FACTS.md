# Sirius — current handoff

## Published state — 2026-10-27

PR75 merged as `4b0ac0963576708c2f573881db1bafdcb1f98bde`, reviewed head
`d9d23cf4f2694518a6403b2d9b64ebb318106c45`. All four head and merge workflows
passed, independent Codex CLI review clean, Northflank deployment7368367874 and
Vercel Production7368392059 succeeded. GET health/live, health/ready and frontend
returned200;20 anonymous protected reads returned401. Public frontend/PWA passed
all five widths. An initial health503 during rollout recovered; retain its log.
[PR75](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/75).

## Active Issue65: real extraction is still not validated

Saved PDF remains intact. Exactly one controlled PR75 pilot moved17→18/120 attempts;
zero of70 inventory leaves and zero roles validated. Groq Qwen3.8-27b now returned
HTTP200 at2026-10-27 16:37:46 São Paulo,1115 input/628 output tokens,1.602s.
The documentary gate rejected the proposal (`evidence_invalid`), reference
`5c0f2d9e-1174-4ccb-84ac-8fb091e089ab`. This proves request acceptance only,
not semantic correctness. The exact documentary rule was discarded by the old
worker; private model output was not retained. Do not guess which rule failed.
Queue remains paused, budget120, minimum forecast158. No new upload or queue release.

## Current work and next action

Branch `codex/edital-evidence-diagnostics-65`: preserve a finite documentary-rule
code through existing diagnostics and distinguish local evidence rejection from
provider outage in the UI. No schema weakening, output repair, migration, paid
service, budget change or retry-policy change. Tests and final-SHA CI/review are
required before merge; exact deploys and production reads before another controlled
pilot. Only one real pilot at a time is authorized; do not release all pending
units or extend budget without owner confirmation.

## Continuity

Phases1–14 and unrelated modules remain preserved. Do not reimplement notifications
PR55/56, deletionPR64 or PDF extractionPR62. Layout improvements are already published.
Backlog only: OCR, rectifications, heterogeneous homologation and workout generation.
Owner authorized safe dev-cache cleanup, but automatic approval blocked recursive
Babel-cache deletion without a specific reason. Nothing deleted; do not bypass.

Previous handoff preserved in
[history](docs/history/HANDOFF_BEFORE_EDITAL_EVIDENCE_DIAGNOSTICS.md), including links
to older intact records. Current detailed evidence stays in
[Issue65 ledger](https://github.com/jpedrosampaio/SiriusFrontAndBack/issues/65#issuecomment-6319387161).
Use AGENTS.md and docs/DEVELOPMENT_CONTEXT.md for permanent gates and targeted context.
