# Sirius - current handoff

## Published state

Phases 1-12 are completed and published. Phase 12: [PR44](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/44), functional merge `b0c013baba383d4dabcdde4a8a15d22800c183f6`, validated on 2026-10-13 UTC. Northflank and Vercel Production deployed that exact merge; live/ready/frontend/automation assets and unauthenticated route isolation passed read-only production checks. Final CI, clean Codex review and owner-approved migration evidence are in the [Phase 12 publication record](docs/history/PHASE_12_PUBLICATION.md).

Recheck Git/PR/deploy state at session start; the functional publication SHA is a reference, not a live query of main. Documentation publication can follow without changing functional code. Earlier publication evidence remains in the historical archive and PRs.

## Next phase and authorization

Next: **Phase 13 - Sirius Command Center**. It is not authorized; wait for explicit owner approval. Phase 12 is published; contracts: [EVENT_AUTOMATION_ENGINE](docs/EVENT_AUTOMATION_ENGINE.md). Do not start the next phase based on historical instructions or the existence of the master plan.

## Migrations and blockers

Published schema head: `e47c2b6a901d`, parent `c9e42a7d160b`. Applied successfully by the [protected workflow](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38412230689), after mandatory owner Environment approval and before PR44 merge. No pending Phase 12 migration or publication blocker. No production test writes. [PRODUCTION_MIGRATIONS](docs/PRODUCTION_MIGRATIONS.md) remains authoritative.

## Decisions and continuity

- Keep the existing single Global Planner, operational study planning, fixed commitments and source histories. Finance forecasts/scenarios use recorded evidence and Decimal; unknown balances/rates stay unknown. Training intelligence is read-only: no automatic load changes or medical diagnoses. Unknown origin/RPE/loads remain unknown; historical sessions without stable day provenance cannot justify numeric progression. See [TRAINING_INTELLIGENCE](docs/TRAINING_INTELLIGENCE.md).
- Permanent development rules: [AGENTS](AGENTS.md). Read relevant module contracts through the [context map](docs/DEVELOPMENT_CONTEXT.md), not the whole historical archive.
- Nutrition uses registered/estimated/unknown evidence and explicitly confirmed targets. Plans and scenarios remain proposals; prices/availability are declared facts. Receipt-backed confirmation preserves histories and avoids duplicate records/XP; no clinical or energy-expenditure inference. See [NUTRITION_INTELLIGENCE](docs/NUTRITION_INTELLIGENCE.md).
- Automation uses canonical facts and durable owned receipts; reports/proposals remain read-only. In-app availability is not confirmed delivery; uncertain Telegram sends require explicit duplicate-risk consent. Stored command-reply recovery never reexecutes financial commands. Runtime flags, owner opt-in, channel policy and quiet hours remain explicit.
- Integral pre-reorganization history: [HANDOFF through Phase 9](docs/history/HANDOFF_THROUGH_PHASE_9.md); later evidence: [Phase 10 publication](docs/history/PHASE_10_PUBLICATION.md), [Phase 11 publication](docs/history/PHASE_11_PUBLICATION.md), [Phase 12 publication](docs/history/PHASE_12_PUBLICATION.md). Historical pending states/commands are superseded, not current instructions. The [context map](docs/DEVELOPMENT_CONTEXT.md#auditoria-e-fontes) records source provenance and hashes.
- Update this file only when current state, authorization, migration/blocker or a material decision changes. Detailed publication/review evidence belongs in the PR/history, not repeated session transcripts here.
