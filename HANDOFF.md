# Sirius - current handoff

## Published state

Phases 1-13 are completed and published. Phase 13: [PR47](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/47), functional merge `e155b88e82fa11da9f0c042e22e70041fe10d23e`, validated on 2026-10-13 UTC. Northflank and Vercel Production deployed that exact merge; live/ready/frontend/Command Center assets and unauthenticated route isolation passed read-only production checks. Final CI, clean Codex review and owner-approved migration evidence are in the [Phase 13 publication record](docs/history/PHASE_13_PUBLICATION.md).

Recheck Git/PR/deploy state at session start; the functional publication SHA is a reference, not a live query of main. Documentation publication can follow without changing functional code. Earlier publication evidence remains in the historical archive and PRs.

## Next phase and authorization

Next: **Phase 14 of the original master plan**, awaiting explicit owner authorization. No implementation for Phase 14 is authorized. Phase 13 contracts and operational limits: [COMMAND_CENTER](docs/COMMAND_CENTER.md).

## Migrations and blockers

Published schema head: `f13c8a7b902d`, parent `e47c2b6a901d`. Applied successfully by the [protected workflow](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38450436437), after mandatory owner Environment approval and before PR47 merge. Adds owned business audit and indexes without deleting histories. No pending Phase 13 migration or publication blocker. No production test writes or direct agent production SQL/Alembic. [PRODUCTION_MIGRATIONS](docs/PRODUCTION_MIGRATIONS.md) remains authoritative.

## Decisions and continuity

- Keep the existing single Global Planner, operational study planning, fixed commitments and source histories. Finance forecasts/scenarios use recorded evidence and Decimal; unknown balances/rates stay unknown. Training intelligence is read-only: no automatic load changes or medical diagnoses. Unknown origin/RPE/loads remain unknown; historical sessions without stable day provenance cannot justify numeric progression. See [TRAINING_INTELLIGENCE](docs/TRAINING_INTELLIGENCE.md).
- Permanent development rules: [AGENTS](AGENTS.md). Read relevant module contracts through the [context map](docs/DEVELOPMENT_CONTEXT.md), not the whole historical archive.
- Nutrition uses registered/estimated/unknown evidence and explicitly confirmed targets. Plans and scenarios remain proposals; prices/availability are declared facts. Receipt-backed confirmation preserves histories and avoids duplicate records/XP; no clinical or energy-expenditure inference. See [NUTRITION_INTELLIGENCE](docs/NUTRITION_INTELLIGENCE.md).
- Automation uses canonical facts and durable owned receipts; reports/proposals remain read-only. In-app availability is not confirmed delivery; uncertain Telegram sends require explicit duplicate-risk consent. Stored command-reply recovery never reexecutes financial commands. Runtime flags, owner opt-in, channel policy and quiet hours remain explicit.
- Command Center reuses canonical Life State and the sole Global Planner. Context selections are ownership-verified; explicit memory retains scope/provenance and requires versions/idempotency even on legacy mutations. Undo is limited to intact reversible changes; exports are progressive canonical records, not complete backup/restore. Facts, estimates and unknowns remain distinct. See [COMMAND_CENTER](docs/COMMAND_CENTER.md).
- Integral pre-reorganization history: [HANDOFF through Phase 9](docs/history/HANDOFF_THROUGH_PHASE_9.md); later evidence: [Phase 10 publication](docs/history/PHASE_10_PUBLICATION.md), [Phase 11 publication](docs/history/PHASE_11_PUBLICATION.md), [Phase 12 publication](docs/history/PHASE_12_PUBLICATION.md), [Phase 13 publication](docs/history/PHASE_13_PUBLICATION.md). Historical pending states/commands are superseded, not current instructions. The [context map](docs/DEVELOPMENT_CONTEXT.md#auditoria-e-fontes) records source provenance and hashes.
- Update this file only when current state, authorization, migration/blocker or a material decision changes. Detailed publication/review evidence belongs in the PR/history, not repeated session transcripts here.
