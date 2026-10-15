# Post-launch publication record

Authorization: owner maintenance request of 2026-10-14; validation date: 2026-10-15 UTC. The fourteen-phase plan is unchanged. This release is maintenance, not Phase 15; no subsequent work is authorized.

## Exact commits and review

- Functional [PR52](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/52), branch `fix/postlaunch-workouts-edital-dashboard`, base `dc4f3cf12ed6e14f666fe2575ca6204911df1d05`.
- Final reviewed head: `ceb74e0a94c6d54bc33474c9e7d4eaf60468c921`.
- Expected-head merge: `c0a92ec2d4338d17b0423d08ed341d14646ab69c`.
- [Final Codex no-major-issues result](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/52#issuecomment-6196960634) identifies that head; all inline threads were resolved before merge. Review was renewed after relevant corrections, rather than treating a Completed label alone as clean approval.
- No migration, dependency/service purchase, real AI test call, direct production Alembic/SQL or production test write. Schema remains `f13c8a7b902d`.

This documentation follow-up changes only HANDOFF/context/module/release records. Its own reviewed SHA, merge, CI and deployment confirmations belong in its PR conversation so that recording the documentation merge does not require an endless series of documentation commits. Post-merge CI executions are linked below; consult the run results rather than interpreting a historical pending state as current release status.

## Root causes and delivered behavior

The directed audit reproduced a fixed five-session calendar overriding declared workout frequency and a form omitting frequency for calisthenics. Full-calendar AI prompts were oversized by design, but actual truncation of the owner's original request was not confirmed. Shape-only exercise checks did not enforce apparatus, focus or modality. Hybrid expansion counted rest as training. The old prompt requested clinical guidance and the writer copied optional health input to account preferences.

Generation now uses bounded complete typed bases and exact deterministic composition: four weeks/three sessions yields 12, four/five yields 20, with stable week/day labels. The form declares location, equipment, focus, level, goal, time and exclusions. Split coverage, eight conditioning activities, alternation, running terrain and conservative level/volume/apparatus guards are validated before plan/XP writes. Bodyweight sessions require actual bodyweight work; mobility remains preparation. Weekly phases/recovery offsets are proposals without automatic load changes or fixed-commitment moves.

Revision of new proposals reuses the same engine, stored declared constraints, all current saved session prescriptions and separate real history. Template deduplication reduces context without omitting late edits; oversized input is explicitly rejected. The session editor preserves other weeks, ranges and duration. Legacy flat plans, explicit receipt fingerprints, old revision paths, history, tutorials and Workout Session UX 2.0 remain supported. Uncertain transport retries recover the same owned request without duplicate plan/XP. Omitted-duration legacy receipt keys can safely conflict; receipts and source plans are not rewritten.

Gemini failure kinds previously collapsed into generic/incorrect credential aliases. Typed allowlisted public errors now retain safe causes and references across direct/queued analysis, without provider/private payloads in messages or logs. Strict JSON/schema checks prevent a truncated prefix from becoming completed analysis. Active duplicate jobs coalesce; opposite-force jobs sharing a content-addressed upload coordinate reference attachment/deletion under the same owner lock. Explicit completed force-reanalysis preserves the existing new-analysis/cache-bypass behavior.

The analytical dashboard was placed after Home content and several absent metrics were displayed as zero; recorded financial net was called balance. Top-level Meu dia / Analises now reuse Command Center and existing aggregates/charts, with lazy graphs, cancellation/retry, honest confirmed-window labels and closed-pane unmounting. Decimal display/tooltips remain exact. Unknown targets, attempts, accuracy and calories stay unknown; recorded zero remains zero. Two backend completion paths and the form had invented calories from duration*6: that fallback is removed, historical entries remain registered with unverified provenance, and totals/averages require complete coverage.

Responsive corrections preserve every original assertion: narrow analytics controls stack; tablet workout actions no longer cover titles; assistant restoration waits for an effectively visible launcher and yields to an open dialog. Account fences and all other modules remain intact. [Current contracts](../POSTLAUNCH_MAINTENANCE.md) describe acceptance boundaries without importing the full history.

## CI and local verification

All four workflows passed on the final reviewed functional head:

| Workflow | Evidence and scope |
|---|---|
| PostgreSQL | [38768244193](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38768244193): empty-database Alembic upgrade, no model/schema drift, 396 persistence tests and six mocked YouTube tests |
| Backend/security/frontend units | [38768243793](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38768243793): 193 backend regressions, five security tests, 74 frontend unit tests |
| Migration safety | [38768243993](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38768243993): 12 tests against disposable PostgreSQL, no production database |
| Frontend | [38768243952](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38768243952): install, lint, units, production build and all nineteen browser suites at 320/390/768/1024/1440 px |

The functional merge has separate [PostgreSQL](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38769958489), [regression/security](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38769958542), [migration-safety](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38769958870) and [frontend](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38769958573) executions. Final post-merge confirmation is recorded in PR52 and the documentation PR after those executions finish.

Local disposable PostgreSQL passed 60 affected workout tests, four dashboard tests and nine edital-job tests; the added daily zero assertion was rerun successfully. Calendar regressions, the 193 backend regressions and five security tests also passed. Frontend lint, 74 unit tests and build passed. The final exact-source build plus all nineteen suites exited zero using Windows Chrome at all five widths; earlier bundled-Chromium focus verification also passed after the visibility correction. Providers and private API writes in browser tests are synthetic/intercepted.

Failures were investigated, not counted as passes: initial 320px analytics CI overflow and 1440px focus failures led to bounds/layout/focus corrections with unchanged assertions. A later real-click scenario reproduced tablet title/action overlap locally and in [obsolete-head run 38767943187](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38767943187); final-head Linux and Windows suites passed after the breakpoint correction. One earlier migration-safety run was cancelled during container initialization, not approved as a test pass; later full safety runs passed. A mistaken local security filename discovered zero tests and was replaced by the correct five-test security run.

## Exact production observation

GitHub deployment records for functional merge `c0a92ec2d4338d17b0423d08ed341d14646ab69c` confirmed:

- Vercel Production deployment `7098480048`: success at `2026-10-15T16:35:44Z`; Vercel commit status also success.
- Northflank environment `siriusfrontandback`, deployment `7098441098`: success at `2026-10-15T16:34:02Z`, in addition to successful build status. Build success alone was not treated as deployment proof.
- [Backend live](https://back--siriusfrontandback--vbfgpbhc7tz8.code.run/health/live): HTTP 200, `{"status":"ok"}`. [Ready](https://back--siriusfrontandback--vbfgpbhc7tz8.code.run/health/ready): HTTP 200, `{"status":"ready"}`.
- OpenAPI exposed the six new workout request fields. Ten private routes returned 401 without authentication: plans, today schedule, training intelligence, dashboard summary/panels/analytics, Command Center, Life State, study areas and tasks.
- [Frontend](https://siriusassistant.vercel.app): HTTP 200, valid manifest/assets, expected Northflank backend URL, account-response fences and published workout generator/calorie input, Home tabs and analytical chunks. PWA shell was v4; legacy telemetry/editor vendor markers were absent.
- Fresh public browser contexts at 320/390/768/1024/1440 loaded login, verified cached boot JS/CSS, then opened public login offline. All passed without page errors, horizontal overflow, legacy-vendor requests or writes. Non-GET/HEAD requests were blocked; none were attempted. This proves public shell/offline boot, not authenticated workflows in production.

Production checks were reads only; authenticated functionality was exercised in disposable PostgreSQL and intercepted browser fixtures, not by creating private records in production. Deployment SHA association comes from GitHub deployment records, not an invented version field in the health response.

## Limits, configuration and preserved history

The specific original production Gemini account/model failure and successful extraction of the owner's real PDF remain unverified. Mocks and official model/schema documentation do not prove real account availability or document accuracy. Existing provider credentials/access/quota remain user-managed; no credential is requested in chat and no new manual configuration is introduced by this release.

Generated exercise tags, estimated execution duration and clinical suitability still need user/professional review. The structural validator is not an exhaustive exercise ontology or medical assessment. Training phases/loads and recovery offsets are proposals, not measured progress. Old calorie provenance cannot reliably be reconstructed without rewriting history; it remains explicitly unverified. Offline private records remain uncached; a fully offline old client must reconnect to receive the updated shell.

The full [pre-publication implementation/audit log](POSTLAUNCH_IMPLEMENTATION_LOG.md) is an exact copy from functional merge c0a92ec2, SHA-256 `d0ed65ef54b243f4f058c3371ae373fa52e69415b4287d35df8589b1ea717c2f`. Its pending statuses are historical and superseded by this record and current GitHub evidence. The original master plan remains byte-identical, SHA-256 `bdd07d91175fd5024f18a05b541e8677fc3884b34a21648087e942a653f1c056`. Earlier HANDOFF/publication archives remain unchanged.

After the documentation follow-up completes its review/CI/merge/deployment/read-only checks, wait for the owner's next authorization. Do not begin another phase.
