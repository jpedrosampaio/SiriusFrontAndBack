# Sirius 3.0 - Integrated Hardening

Phase 14 is authorized; this is an audit in progress, not a declaration that Sirius 3.0 is complete. Base: main `bd565c337d79b436a2b9777f2649bafa218f3762`, verified before creating `chore/sirius-3-integrated-hardening`. The original fourteen-phase plan remains byte-for-byte intact. Existing schema builds from empty disposable PostgreSQL to `f13c8a7b902d`; Alembic check reports no drift.

## Coverage matrix before product changes

Existing suites exercise individual engines and several integrations. Their existence does not prove every complete journey. Additional evidence will be recorded below only after execution.

| Flow | Existing coverage | Necessary integrated checks |
|---|---|---|
| A: edital to preparation, syllabus, study, question, error, review, strategy and authorized plan | `test_postgres_runtime_edital_import`, `test_postgres_preparation_state`, `test_postgres_question_intelligence`, `test_postgres_adaptive_strategy`, `test_postgres_exam_intelligence`, `test_postgres_study_tutor` | One persisted lineage through real routes, recorded evidence versus estimated results, replay, protected planning and isolation |
| B: task to schedule, planner, Home, completion, Life State and automation | `test_postgres_runtime_planning`, `test_postgres_life_state`, `test_postgres_command_center`, `test_postgres_event_engine` | Full transition, fixed work/appointments and competing flexible activities, stale confirmation, no duplicate XP/event |
| C: plan to session, sets, completion, Training State, Life State and recommendation | `test_postgres_runtime_workout_sessions`, `test_postgres_training_intelligence` | Real session route lineage, uncertain retries, preserved prescription, recorded origin/RPE versus unknown legacy history |
| D: expense to state, budget, alert, scenario and contextual explanation | `test_postgres_runtime_finance`, `test_postgres_finance_intelligence`, `test_postgres_command_center` | Exact Decimal across one route-driven journey, no scenario ledger writes, owner-only explanation |
| E: reviewed meal plan to confirmation, consumption, remaining targets and integrated context | `test_postgres_nutrition_intelligence`, `test_postgres_runtime_nutrition_plans` | Explicit reviewed/estimated/unknown provenance across routes, confirmation without implicit goals/consumption, one receipt/XP, budget/training context |
| F: canonical event to durable policy, delivery, history and Home | `test_postgres_event_engine`, `test_postgres_agent_automations`, `test_postgres_telegram` | End-to-end source transition and history, quiet hours, restart/lease ambiguity, no blind provider resend or financial reexecution |
| G: Home to contextual Agent, search, Why, scenario, confirmation, audit and undo | `test_postgres_command_center`, `test_command_context_regression`, `command-center-smoke.cjs` | One owned chain; blocked reads and context minimization; stale/ABA/replay across mutation and reversal |

## Initial security and risk priorities

- Investigate late frontend responses across token changes, including an old 401 cancelling a newer account. Existing profile-cache regression checks cache repopulation, but still permits returning a stale response to the original consumer.
- Investigate the Agent's eager `get_study_progress` read when message keywords match, before normal blocked-tool enforcement. Reproduce with blocked preferences and a mocked provider before changing product code.
- Preserve current owner filters, parent scopes, version/receipt/lock contracts and historical records. Expand Alice/Bob coverage through all seven flows, including search/export/audit/memory/undo and provider histories.
- Review connections held over external calls, bounded provider retries/concurrency, log redaction, storage fallback and mobile accessibility. No actual provider calls or production writes are allowed in this audit.

## Reference measurements

Synthetic local cross-domain day, disposable PostgreSQL, no providers, one Home invocation per trial, warmup excluded. Ten and one hundred flexible tasks plus fixed work, study, a selected workout, a bill, Decimal ledger evidence, a habit and a goal; nutrition is explicitly unknown. Five measured trials per size: **39 SELECTs** at both sizes, Home JSON **8,636 / 8,650 bytes**, median **41.09 / 46.58 ms** respectively. This workload does not establish production latency or high-volume capacity. Record fresh frontend build sizes separately; pre-existing build artifacts are not accepted as a source-matched reference.

Measurements precede product changes. Later comparisons must use the same fixture, environment, ordering, warmup and build configuration; timings remain observations, never promises or fabricated percentages. Query-count assertions should guard workload growth rather than mirror private implementation details.

## Remaining limits and publication gates

Progressive canonical exports are not full backup/restore. Original file durability depends on configured existing storage; extracted text is not original binary preservation. Providers may degrade or have ambiguous delivery outcomes. Undo is limited to intact reversible effects. Preserve these limits in UI and final evidence.

All four existing workflows, all browser suites and five widths remain mandatory. Final reviewed-head CI and clean Codex review precede merge. Any necessary migration requires exact separate registry approval, protected main workflow and mandatory owner Environment approval. Production validation is read-only on exact Vercel/Northflank merge deployments. The final audit must classify all twenty criteria of item 141, documenting any insufficient evidence or relevant blocker. Do not start a Phase 15 or expand product scope.

## Changes justified by reproduced failures

1. Late Alice responses were returned to consumers after Bob signed in; an old Alice 401 could clear Bob's token. Separate authentication generations now fence success/error responses and shared profile consumers. Token changes reset protected pages as well as caches, discard the global conversation pointer and preserve owner-namespaced drafts. Same-account mutations still allow concurrent reads. `auth-cache.test.cjs` and the browser's real cross-tab storage transition exercise both paths.
2. The Agent's eager study keyword read bypassed `blocked_tools`. The eager read now uses the same prohibition as normal tool routing. A mocked provider confirms no blocked study payload or tool reaches the request.
3. Telegram token redaction already existed. Its transport filter now also removes URL userinfo/query values while retaining HTTPX URL objects and Uvicorn's five-argument access formatter contract. Transport DEBUG traces are disabled; status, route and timing remain observable. Daily-summary and legacy generation/import exceptions log their type, without prompt/response text; fuzzy cargo merge diagnostics retain counts. Workout diagnostics no longer contain response excerpts. Unexpected generation/storage failures return generic errors rather than exception contents. MockTransport, workout provider/storage failures and PostgreSQL fallback tests cover these boundaries.
4. Desktop assistant close attempted to focus a still-hidden launcher. The command search also lost its invoking focus, and opening the assistant from a disappearing search item left no valid return target. Restoration now uses the closing autofocus lifecycle, deferred to the next frame; detached triggers fall back to the visible assistant entry point. Five-width browser coverage verifies a 44px close target, actual returned focus for direct/search entry, Escape, text contrast and error recovery.

The older smoke's assumption that an assistant remains open across an authentication reset was invalidated by intentional session teardown. It now asserts closure and explicitly reopens the authenticated assistant before retaining all previous keyboard/attachment/viewport checks. The new suite waits for search exit animation rather than assuming synchronous DOM removal. No assertion was removed to conceal a product failure.

## Integrated evidence and boundaries

`backend/tests/test_postgres_integrated_hardening.py` exercises the real ASGI application, independent hashed Alice/Bob sessions and disposable SQL. Providers are mocked only at external boundaries; owner/auth contracts are not mocked in this new suite.

| Journey | New integrated evidence | Complementary coverage preserved | Boundary |
|---|---|---|---|
| A | Stored source/explicit weight → cargo import/replay → syllabus → focus/error/review → Strategy → dated plan; scoped Tutor replay; foreign requests cannot call the provider | Direct PDF import, extraction/jobs, source review, preparation state, Questions Intelligence, exams and Tutor suites | Source text/extraction and generative quality use synthetic fixtures, not an actual provider accuracy evaluation |
| B | Real task creation/edit/completion, competing study/training, availability, Home/search, stale rejection and one completion | Runtime planning, Life State, event producers/engine and XP suites | Schedule confirmation never completes the source task or pays a bill |
| C | Plan → actual sets/RPE → concurrent completion → one session/log/set lineage → Training/Life State; prescription unchanged | Training progression/substitution, replaced days, legacy origins, resumable workout sessions | Unknown legacy load/origin remains unknown; suggestions do not apply new loads |
| D | Decimal 0.10+0.20 → 0.30 state/budget alert → read-only scenario → ownership-verified Agent selection | Forecast, debt, budget, transaction, payment, receipt/rollback suites | Recorded net is not bank balance; simulations never create ledger rows |
| E | Reviewed preview/confirmation → one recorded meal → estimated macros/unknown targets → explicit calorie target/remaining → owned Finance budget and recorded training context | Nutrition preview expiry, prices, exclusions, rollback, recipes/plans and evidence suites | No implicit goals/consumption, clinical diagnosis or energy-expenditure inference |
| F | Real overdue source → dedup/owned policy → one leased delivery → ambiguous fake acknowledgement → restart/history → owner-only inbox/duplicate-risk gate | Quiet-hours/DST, daily caps, durable retries, worker fencing, changed bindings and stored Telegram command replies | No real Telegram send; uncertain transport is not proven delivery and cannot auto-resend |
| G | Owned Home/Why/search → read-only preview → stale confirmation → concurrent acceptance/audit → owner-only replay-safe undo | Command memory/version/ABA/export bounds, contextual Agent, frontend tools/confirmation | Undo is restricted to intact future allocations and eligible effects, not general historical reset |

The realistic-day fixture includes fixed work 08:00–17:00, a fixed appointment 18:00–19:00, owned review, selected workout, work task and a bill with due date derived from the owned card configuration. Fixed times and source histories survive confirm/undo; bill payment and source study completion remain untouched. Changing the task duration invalidates the preview before any allocation is written. Existing tests additionally cover unknown fixed durations, DST, conflicting schedules and empty availability with allocation suspended.

## Multiuser security matrix

| Surface | Alice/Bob adversarial evidence | Expected outcome |
|---|---|---|
| Studies/source/cargo/Tutor/strategy | Integrated A plus catalog, editais, source tracking, questions/exam/Tutor suites | Foreign parent IDs return 404/422 before provider access; no forged official evidence or estimated mastery |
| Tasks/calendar/planner/audit/undo | Integrated BG plus Life State/Command suites | Owner-only search/state; stale/ABA/started allocations refused; atomic replay and fixed commitments preserved |
| Workout plans/sessions/sets/history | Integrated C plus training/session suites | Foreign mutation 404; actual owner evidence only; no duplicate XP/session/log |
| Finance/budget/context | Integrated D/E plus finance/Agent suites | Decimal and owner filtering; no foreign deletion, budget read or client-invented balance |
| Nutrition/template/preview/target | Integrated E plus nutrition suites | Foreign preview/template/budget 404; targets require explicit confirmation; replay records once |
| Automations/delivery/Telegram recovery | Integrated F plus event/Telegram suites | Foreign inbox empty/receipt 404; explicit ambiguous retry consent; no repeated financial execution |
| Conversations/memory/materials/export | Command, conversations, RAG/retrieval/storage suites and auth/browser regressions | Owned rows/versions/pages; hidden tool content excluded; blocked provider context minimized |
| Logout/expiry/account/cache | Real SQL sessions plus browser cross-tab and interceptor unit tests | Revoked/expired tokens 401 across engines; no stale payload/profile/401 effects across identities; drafts remain owner-scoped |

## Performance and dependencies audit

Reproduce after preparing an empty **disposable localhost** database using the existing CI schema commands and building with `CI=true`, `REACT_APP_BACKEND_URL=https://sirius-api.test`:

```powershell
$env:RUN_POSTGRES_TESTS='true'
$env:HARDENING_TEST_DATABASE_URL='postgresql://sirius_test@127.0.0.1:5432/sirius_hardening_test'
python tools/benchmark_integrated.py
```

The tool rejects remote/non-test databases, missing opt-in, query overrides and libpq service/host-address overrides before loading persistence. It creates synthetic owned fixtures only; it does not reset any database or contact providers. It collects five trials after warmup, payload/bundle sizes and 39 EXPLAIN plans without credentials/query parameters. Reference artifacts live in `docs/benchmarks/`. Small UUID tie ordering can choose task labels of different lengths; payload byte differences are not invented compression gains.

The audited Home remains 39 SELECTs for 10/100 tasks. Existing Preparation projection remains 19 SELECTs for 2/100 topics, with a measured 88,347-byte 100-topic response. Neither observation establishes unlimited capacity. Owner/time indexes exist for tasks, calendar, study sessions/attempts/reviews, bills/transactions, workout history and meals/water. EXPLAIN includes owner indexes; sequential scans on small tables alone do not justify a new index/migration. Preserve query/child limits and explicit truncation/fail-closed warnings. No schema/index change was justified here.

| Measure | Source-matched before | Final local snapshot | Interpretation |
|---|---|---|---|
| Home, 10 tasks | 39 SELECTs; 8,636 bytes; median 41.09ms | 39 SELECTs; 8,636 bytes; median 37.74ms | Same bounded query count and payload; timing is an observation, not a proven speedup |
| Home, 100 tasks | 39 SELECTs; 8,650 bytes; median 46.58ms | 39 SELECTs; 8,650 bytes; median 40.51ms | No demonstrated N+1 growth in this fixture, not unlimited scalability |
| Main JS | 611,506 bytes / 186,282 gzip | 612,862 bytes / 186,685 gzip | Small safety/focus increase; no bundle reduction claimed |
| Initial Home browser requests | Existing suite records requests | 1 profile + 1 Home, plus the existing automation-state request | Shared profile remains deduplicated; closed assistant makes no generation request |

Final timing measurements ran with background validation stopped. Concurrent diagnostic runs varied (roughly 44–62ms); they are not substituted for the comparable reference or represented as improvement percentages. The Home/Preparation projection logic was not changed for benchmark gains. Raw [before](benchmarks/integrated-before.json) and [after](benchmarks/integrated-after.json) artifacts preserve every measured trial, bundle and final EXPLAIN plan.

SQL transactions finish before external I/O; the integrated delivery test asserts zero checked-out connections while invoking the fake sender. The shared SQL pool remains bounded (2 + 1 overflow, 15-second acquisition timeout), with pre-ping/recycle and hidden parameters. Provider routing uses a finite catalog, durable internal quotas, bounded cooldowns and existing per-call timeouts/fallback; HTTPX's bounded connection pool is retained. Gemini upload polling is finite; YouTube uses a fixed endpoint, bounded query/cache/pending work and timeout. Telegram leases and uncertain outcomes remain durable. This is not a load certification or proof of per-account provider parallelism limits.

Provider catalog/support was checked read-only against [Gemini models](https://ai.google.dev/gemini-api/docs/models), [embeddings](https://ai.google.dev/gemini-api/docs/embeddings) and [Groq models](https://console.groq.com/docs/models) on 2026-10-13. No catalog, paid-provider configuration, infrastructure or service was added. A model's availability does not guarantee a particular account's quota or free billing entitlement. All tests use mocks, including malformed output, rate limits, timeouts, key failures and fallback.

Binary storage remains optional and explicit: unavailable storage refuses durable binary writes rather than pretending extracted text is an original file. Progressive exports are bounded canonical pages, not full backup/restore. Existing runtime flags, opt-in, channel rules, quiet hours and readiness behavior are preserved. No feature flag hides a failed gate.

## Item 141 — all twenty criteria

Classification is **comprovado por evidência** within the stated executable-contract/disposable-SQL/mocked-provider boundary. This does not certify live provider answer quality, original-file retention without configured storage, full restore or every user's production history. Publication gates remain separate until exact deployments are verified.

| # | Criterion | Classification | Primary evidence |
|---|---|---|---|
| 1 | Preparation Engine real | Comprovado | Preparation state plus integrated A, real hierarchy and evidence |
| 2 | Syllabus evidence | Comprovado | Integrated sourced weight and source review/import regressions |
| 3 | Auditable mastery | Comprovado | Preparation/Questions evidence, no invented samples, estimates do not write mastery |
| 4 | Radar/Impact Analysis | Comprovado | Contest tracking source versions/diff/timeline, partial source disclosures, SSRF/ownership and radar smoke |
| 5 | Questions Intelligence | Comprovado | Recorded identity/confidence/skips/reviews and mocked validation boundaries |
| 6 | Strategy Engine | Comprovado | Integrated A, adaptive recovery/constraints/read-only simulation |
| 7 | Exams feed strategy | Comprovado | Exam attempt → canonical QuestionAttempt, timing/blank/penalty evidence, no duplicate XP; strategy consumes these facts |
| 8 | Tutor uses real context | Comprovado | Integrated owned lineage/replay and scoped retrieval/material/error-context suites; provider explanation remains assisted |
| 9 | Life State aggregates modules | Comprovado | Eight typed owned adapters, integrated BCDEG, bounded-query tests |
| 10 | Global Planner arbitrates priorities | Comprovado | Realistic-day conflict/availability/stale/confirm/undo and Life planner tests, single allocator |
| 11 | Finance forecasting | Comprovado | Decimal forecast/scenarios, owned dated sources, unknown balance/rates |
| 12 | Training Intelligence | Comprovado | Real sets/RPE/history and deterministic progression/record/substitution contracts |
| 13 | Nutrition Intelligence | Comprovado | Reviewed receipts, registered/estimated/unknown provenance, confirmed remaining targets and shared budget/training facts |
| 14 | Events feed automations | Comprovado | Canonical producers/outbox/leases, integrated F, policy/retry/history; external receipt uncertainty disclosed |
| 15 | Cross-domain briefing | Comprovado | Event reports and daily-summary fallback use canonical domain facts and deterministic score |
| 16 | Command Center next action | Comprovado | Owned Home fixed/flexible priorities and empty/unsafe state, Command and five-width browser suites |
| 17 | Contextual Agent | Comprovado | Server-owned selection, scoped memories/blocked tools, cross-domain facts and confirmation receipts |
| 18 | Why | Comprovado | Home/scenario evidence+constraints+limitations+source, browser details and real-day reasons |
| 19 | Audit | Comprovado | Owned business audit, versions, replay/ABA/stale fences, safe atomic undo and pagination |
| 20 | Historical modules operational | Comprovado | Full PostgreSQL/runtime/regression suites, all original frontend smoke suites preserved; no resets/backfills |

No essential technical defect is waived by this matrix. A failed final workflow/review/deployment invalidates publication readiness. The final release record must link final-head checks/review and merge deployments, and disclose real limitations instead of claiming unconditional acceptance.

## Local validation and review readiness

- PostgreSQL: 351 tests passed in the full disposable suite; strengthened integrated A/B/Tutor/bill assertions subsequently passed all seven new cases. Empty schema upgrade and Alembic check agree on unchanged `f13c8a7b902d`.
- Backend: syntax, 185 regressions, 5 security routes, 6 mocked YouTube tests and 12 protected-migration safety tests passed. Benchmark safety guards reject unsafe connection overrides before imports/connect.
- Frontend: zero-warning lint, 62 unit tests, production build and all 18 smoke suites passed against the final frontend, including the focus extension and all five widths.
- Self-review covered the complete product diff, owner/parent/version/receipt boundaries, rollback/replay/concurrency, unknown evidence, provider failure, mobile focus/contrast/closing, historical compatibility, benchmark guards and plan/source integrity. No model, migration, workflow, paid service or source-history reset was introduced.

These are local evidence, not a substitute for the four final-head remote workflows, final Codex review or exact merge/deployment checks. Publication is still pending.
