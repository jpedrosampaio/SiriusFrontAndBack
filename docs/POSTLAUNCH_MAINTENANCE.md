# Post-launch maintenance: workouts, edital and dashboard

Authorized on 2026-10-14 (America/Sao_Paulo). Base main: `dc4f3cf12ed6e14f666fe2575ca6204911df1d05`; branch `fix/postlaunch-workouts-edital-dashboard`. This is maintenance, not Phase 15. The original fourteen-phase plan and historical releases remain unchanged.

## Directed audit before product changes

- Workout generation: the period calendar ignores `training_days_per_week` outside running and fixes five sessions. A synthetic calisthenics request for four weeks/three days produces `(4, 5)` rather than `(4, 3)`. The frontend omits frequency for calisthenics. Period prompts request every full session; the shared generator allows 8,192 output tokens and its correction repeats the entire request. Actual truncation in the owner's failed request is **not confirmed**.
- The calisthenics prompt includes a parallel-bars example even with declared no equipment. Exercise validation checks shape/name, not apparatus or level. Hybrid expansion counts a rest day inside the configured training frequency. Health instructions request rehabilitation/clinical contraindications, and the writer copies the report into account preferences. These are code findings, not diagnoses.
- Gemini facade maps unavailable/malformed errors to `other`, request/schema failures to the invalid-key alias, and rate limits to quota. Synthetic exceptions reproduce the classification loss without real provider calls. The direct analysis then emits the generic reported message; asynchronous failures discard safe diagnostic detail. Official Gemini model/structured-output/troubleshooting documentation was checked read-only on 2026-10-14; catalogue presence does not confirm account access/quota or the original production failure.
- Dashboard retains lazy `DashboardDetails` but exposes it after all Home sections. Closed details do not load stats. Existing analytics show several absent scores/targets as zero and label recorded financial net as balance; workout calorie provenance needs an explicit boundary. Reuse the existing services/charts and the sole planner, not a second statistics engine.

Audit followed models, generation/calendar/writer, session UX2/Training consumers, facade/router/providers, shared direct/job edital pipeline and its owner/hash cache, Dashboard/Details and aggregate sources. Existing atomic activity receipts, session fences, PostgreSQL ownership and history are mandatory constraints.

## Implementation and gates

Order: safe provider classification/recovery; bounded validated workout bases and deterministic calendar plus form; top-level Meu dia/Análises and truthful indicators; full self-review/tests/CI/Codex; exact merge deployments and read-only production checks. Prefer JSON-compatible metadata without migration. No real AI/YouTube/Telegram calls in tests, production test writes or paid infrastructure.

Publication is pending. Record concrete outcomes and remaining external/operational boundaries here; detailed final release evidence belongs in a separate history record. All four workflows, disposable PostgreSQL, security/regressions, frontend lint/unit/build, every browser suite and all five widths remain required.
