# Sirius - current handoff

## Published state

Phases 1-10 are completed and published. Phase 10: [PR39](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/39), functional merge `c23374679b63edaee8391def51e466b238800cdf`, validated on 2026-10-09 UTC. Northflank and Vercel Production deployed that exact merge; live/ready/frontend/training assets passed read-only production checks. Final CI and clean Codex review evidence are in the [Phase 10 publication record](docs/history/PHASE_10_PUBLICATION.md).

Recheck Git/PR/deploy state at session start; the functional publication SHA is a reference, not a live query of main. Documentation publication can follow without changing functional code. Earlier publication evidence remains in the historical archive and PRs.

## Next phase and authorization

Current: **Phase 11 - Nutrition Intelligence 2.0**, explicitly authorized after PR40; base main `ccf566bf38b365e0bffe1628c8b86a9e2ab4ad77`, branch `feat/nutrition-intelligence-2`. See [NUTRITION_INTELLIGENCE](docs/NUTRITION_INTELLIGENCE.md). Implementation, final CI/review, protected migration and publication are pending. **Phase 12 is not authorized; await permission after Phase 11 publication.**

## Migrations and blockers

Published schema head: `a81c9d37e502`. Proposed Phase 11 migration: `c9e42a7d160b`, additive nullable nutrition provenance; not applied in production. No production test writes. Production migrations remain exclusive to the protected workflow and mandatory owner approval in [PRODUCTION_MIGRATIONS](docs/PRODUCTION_MIGRATIONS.md); merge waits for confirmed migration.

## Decisions and continuity

- Keep the existing single Global Planner, operational study planning, fixed commitments and source histories. Finance forecasts/scenarios use recorded evidence and Decimal; unknown balances/rates stay unknown. Training intelligence is read-only: no automatic load changes or medical diagnoses. Unknown origin/RPE/loads remain unknown; historical sessions without stable day provenance cannot justify numeric progression. See [TRAINING_INTELLIGENCE](docs/TRAINING_INTELLIGENCE.md).
- Permanent development rules: [AGENTS](AGENTS.md). Read relevant module contracts through the [context map](docs/DEVELOPMENT_CONTEXT.md), not the whole historical archive.
- Integral pre-reorganization history: [HANDOFF through Phase 9](docs/history/HANDOFF_THROUGH_PHASE_9.md); later evidence: [Phase 10 publication](docs/history/PHASE_10_PUBLICATION.md). Historical pending states/commands are superseded, not current instructions. The [context map](docs/DEVELOPMENT_CONTEXT.md#auditoria-e-fontes) records source provenance and hashes.
- Update this file only when current state, authorization, migration/blocker or a material decision changes. Detailed publication/review evidence belongs in the PR/history, not repeated session transcripts here.
