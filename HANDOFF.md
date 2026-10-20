# Sirius - current handoff

## Published state

Phases 1-14 remain completed and published within the executable-contract validation scope. Latest functional maintenance: the universal incremental edital analyzer, [PR57](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/57), reviewed head `13200946271d6aeeeefb0b0d08a85323667f94be`, deployed merge `39ad9786ecb2eed57c3c9b65218388eedd0ebb42`. Its four head workflows passed with clean final Codex review; the protected owner-approved migration returned `applied`. Northflank and Vercel deployed that exact merge. Live/ready, preserved/new contracts, frontend/assets, twenty unauthenticated private GETs and public offline PWA boot at 320/390/768/1024/1440 px passed read-only checks. [Publication evidence, merge validation runs and limits](docs/history/UNIVERSAL_EDITAL_PUBLICATION.md).

Latest shared-session follow-up: [PR60](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/60), reviewed head `d0a555d58e14ff6724b4143445030712342f52d9`, deployed merge `a374c4d21c0ee3293d0017c786df01a79229490a`. It fixes a real anonymous 401/auth-change/poll feedback loop discovered during final production checks, preserving account fences and cookie-only authentication. Four head workflows and clean Codex review passed; both exact deploys and fresh production reads/PWA checks passed at all five widths, with three initial anonymous state denials per case and no continuing storm. No migration or notification-manager rewrite. [Follow-up evidence and merge validation](docs/history/UNIVERSAL_EDITAL_PUBLICATION.md#shared-session-follow-up).

Notification maintenance remains published: PR55, reviewed head `eaacbbc02fa7845369b1c63035a46238a806ffda`, merge `ffa02f45f06711d23bdb02e69c10430321ae847b`. Four head/merge workflows, clean Codex review, exact deploys and read-only production checks passed; [historical evidence](docs/history/NOTIFICATION_PUBLICATION.md). Do not reimplement it.

Earlier functional maintenance remains published: [PR52/post-launch evidence](docs/history/POSTLAUNCH_PUBLICATION.md); [Phase 14 publication](docs/history/PHASE_14_PUBLICATION.md). These are historical records, not pending work.

PDF parser security prerequisite: PR56, reviewed head `874ff61b9a4e852d4f2d53663fbad11c106c1a69`, published merge `516a5fb4028173f71aa7bf9e97f72a55fd33213d`. Four workflows passed on head/merge, Codex was clean, both exact deploys and read-only production checks passed. No migration; [historical evidence](docs/history/PDF_PARSER_PUBLICATION.md). The published analyzer preserves that trusted workflow/dependency base.

Recheck Git/PR/deploy state at session start; publication SHAs are references, not live queries of main. Earlier evidence remains in the historical archive and PRs.

## Next phase and authorization

PDF runtime follow-up is published in [PR62](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/62),
merge `e93b7ff6a69d20d6e0916b0593daa8edaac4bde2`. The owner confirmed that the
real 70-page PDF now passes extraction. Historical reproduction, safe diagnostics
and unchanged resource limits remain in [PDF extraction evidence](docs/PDF_EXTRACTION_DIAGNOSTICS.md).

Current authorized P0: structured-provider compatibility and safe recovery of
the saved semantic analysis (67 inventory units, zero completed, five attempts
reserved). Recovery release and publication receipts: [PR63](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/63).
Provider-specific
transport keeps canonical Pydantic/documentary gates, adds correlated sanitized
HTTP failures, explicit one-call pilot authorization and complete known-work
budget forecasting. Existing IR/checkpoints/history remain intact; only new
intake uses denser packing. No migration or live AI call is part of this hotfix.
Publication requires four green workflows, clean final Codex review and
both exact deploys/read-only production checks; consult the PR's exact-SHA
receipts rather than assuming publication from local tests. The generic historical HTTP400
does not establish the rejected field. After publication, **await owner
authorization for one small real-provider pilot, then pause and obtain separate
authorization before the remaining batches/budget extension**. Local/mocked
schema acceptance is not live semantic success.
[Contracts, incident limits and manual pilot](docs/EDITAL_PROVIDER_DIAGNOSTICS.md).

The original fourteen-phase plan remains intact; **there is no Phase 15**. The authorized notification/PDF-security maintenance and incremental analyzer are deployed. Early inventory/selection, durable small units, recovery, human review/confirmation, canonical import and responsive workspace reuse the existing engines; [contracts and boundaries](docs/UNIVERSAL_EDITAL_ANALYZER.md). No real Gemini/Groq inference was performed or authorized for these tests; deployment does not establish semantic generalization. Await owner authorization before starting further work.

Backlog only: operational OCR; rectification/complementary-document reconciliation; separately authorized real Gemini validation with heterogeneous notices; the unresolved workout `workout_generation_invalid_sessions` failure; other real homologation issues. These were not implemented or silently marked resolved by this release.

## Migrations and blockers

Published schema head: `a61015ed902b`, parent `f13c8a7b902d`. Registry PR58 was integrated as `57f3ff022dabc1a26e1b0976dd31b0b2a43f1119` after its own four green workflows and clean review. The [protected workflow 39413657221](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39413657221) ran from that main, required the owner's Environment approval and confirmed `applied; revision a61015ed902b` at 2026-10-20 11:22:05 UTC, before feature merge. No analyzer migration remains pending. [PRODUCTION_MIGRATIONS](docs/PRODUCTION_MIGRATIONS.md) governs future migrations; never execute production Alembic/SQL directly in the agent or perform production test writes.

The earlier safe-stop and open review findings are superseded, preserved in the [historical checkpoint](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/57#issuecomment-6288949142) and publication record. Both P2 fixes (thousands magnitude and document-based import/XP identity) and the P1 fix (transactional job retirement and deleted-worker fencing) are included in the deployed merge. No relevant review finding remained open at merge. The publication record preserves the local startup naming-guard failure/retry, production PWA failures/retries and the later diagnosed auth-loop follow-up; no assertion or timeout was weakened.

## Decisions and continuity

- Keep the existing single Global Planner, operational study planning, fixed commitments and source histories. Finance forecasts/scenarios use recorded evidence and Decimal; unknown balances/rates stay unknown. Training intelligence is read-only: no automatic load changes or medical diagnoses. Unknown origin/RPE/loads remain unknown; historical sessions without stable day provenance cannot justify numeric progression. See [TRAINING_INTELLIGENCE](docs/TRAINING_INTELLIGENCE.md).
- New workout proposals compose the declared calendar from bounded validated bases; revision reuses current saved prescriptions and real history. Session editing preserves the other weeks. Old plans/session UX2/tutorials remain compatible. Missing workout calories are not inferred from duration; historical entries retain unverified provenance. Edital errors expose safe causes/references and reject incomplete JSON/schema, but the original real Gemini account/model/PDF failure remains unverified. Meu dia/Análises reuse existing services and preserve exact money, unknown values and session fences.
- Permanent development rules: [AGENTS](AGENTS.md). Read relevant module contracts through the [context map](docs/DEVELOPMENT_CONTEXT.md), not the whole historical archive.
- Nutrition uses registered/estimated/unknown evidence and explicitly confirmed targets. Plans and scenarios remain proposals; prices/availability are declared facts. Receipt-backed confirmation preserves histories and avoids duplicate records/XP; no clinical or energy-expenditure inference. See [NUTRITION_INTELLIGENCE](docs/NUTRITION_INTELLIGENCE.md).
- Automation uses canonical facts and durable owned receipts; reports/proposals remain read-only. In-app availability is not confirmed delivery; uncertain Telegram sends require explicit duplicate-risk consent. Stored command-reply recovery never reexecutes financial commands. Runtime flags, owner opt-in, channel policy and quiet hours remain explicit.
- Command Center reuses canonical Life State and the sole Global Planner. Context selections are ownership-verified; explicit memory retains scope/provenance and requires versions/idempotency even on legacy mutations. Undo is limited to intact reversible changes; exports are progressive canonical records, not complete backup/restore. Facts, estimates and unknowns remain distinct. See [COMMAND_CENTER](docs/COMMAND_CENTER.md).
- Session fences discard earlier-account payloads/401s and unmount personal views on authentication changes. Repeated anonymous 401s invalidate once per generation; explicit auth changes or a valid current profile/owned notification configuration rearm expiry, including cookie-only sessions. Blocking study reads also blocks Agent document retrieval. Transport/generation logs omit credentials and private response/exception contents. PWA v4 installs boot JS/CSS before activating; fully offline devices need an online update and private API responses remain uncached. Legacy generator telemetry/editor scripts were removed; explicit Google login remains supported.
- Integral pre-reorganization history: [HANDOFF through Phase 9](docs/history/HANDOFF_THROUGH_PHASE_9.md); later evidence: [Phase 10 publication](docs/history/PHASE_10_PUBLICATION.md), [Phase 11 publication](docs/history/PHASE_11_PUBLICATION.md), [Phase 12 publication](docs/history/PHASE_12_PUBLICATION.md), [Phase 13 publication](docs/history/PHASE_13_PUBLICATION.md), [Phase 14 publication](docs/history/PHASE_14_PUBLICATION.md). Historical pending states/commands are superseded, not current instructions. The [context map](docs/DEVELOPMENT_CONTEXT.md#auditoria-e-fontes) records source provenance and hashes.
- Update this file only when current state, authorization, migration/blocker or a material decision changes. Detailed publication/review evidence belongs in the PR/history, not repeated session transcripts here.
