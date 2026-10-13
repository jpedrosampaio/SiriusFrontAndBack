# Sirius - current handoff

## Published state

Phases 1-11 are completed and published. Phase 11: [PR41](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/41), functional merge `9a4008962da23ff8de3c8acbfbda96d828f6181b`, validated on 2026-10-13 UTC. Northflank and Vercel Production deployed that exact merge; live/ready/frontend/nutrition assets and unauthenticated route isolation passed read-only production checks. Final CI, clean Codex review and owner-approved migration evidence are in the [Phase 11 publication record](docs/history/PHASE_11_PUBLICATION.md).

Recheck Git/PR/deploy state at session start; the functional publication SHA is a reference, not a live query of main. Documentation publication can follow without changing functional code. Earlier publication evidence remains in the historical archive and PRs.

## Next phase and authorization

Next: **Phase 12 - Event & Automation Engine 2.0**. **Not authorized; await explicit owner permission before starting.** Phase 11 is published; its current contracts are in [NUTRITION_INTELLIGENCE](docs/NUTRITION_INTELLIGENCE.md).

## Migrations and blockers

Published schema head: `c9e42a7d160b`, parent `a81c9d37e502`. Applied successfully by the [protected workflow](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38356833389), after mandatory owner Environment approval and before PR41 merge. No pending migration or publication blocker; no production test writes. Future production migrations remain exclusive to the protected workflow and owner approval in [PRODUCTION_MIGRATIONS](docs/PRODUCTION_MIGRATIONS.md).

## Decisions and continuity

- Keep the existing single Global Planner, operational study planning, fixed commitments and source histories. Finance forecasts/scenarios use recorded evidence and Decimal; unknown balances/rates stay unknown. Training intelligence is read-only: no automatic load changes or medical diagnoses. Unknown origin/RPE/loads remain unknown; historical sessions without stable day provenance cannot justify numeric progression. See [TRAINING_INTELLIGENCE](docs/TRAINING_INTELLIGENCE.md).
- Permanent development rules: [AGENTS](AGENTS.md). Read relevant module contracts through the [context map](docs/DEVELOPMENT_CONTEXT.md), not the whole historical archive.
- Nutrition uses registered/estimated/unknown evidence and explicitly confirmed targets. Plans and scenarios remain proposals; prices/availability are declared facts. Receipt-backed confirmation preserves histories and avoids duplicate records/XP; no clinical or energy-expenditure inference. See [NUTRITION_INTELLIGENCE](docs/NUTRITION_INTELLIGENCE.md).
- Integral pre-reorganization history: [HANDOFF through Phase 9](docs/history/HANDOFF_THROUGH_PHASE_9.md); later evidence: [Phase 10 publication](docs/history/PHASE_10_PUBLICATION.md), [Phase 11 publication](docs/history/PHASE_11_PUBLICATION.md). Historical pending states/commands are superseded, not current instructions. The [context map](docs/DEVELOPMENT_CONTEXT.md#auditoria-e-fontes) records source provenance and hashes.
- Update this file only when current state, authorization, migration/blocker or a material decision changes. Detailed publication/review evidence belongs in the PR/history, not repeated session transcripts here.
