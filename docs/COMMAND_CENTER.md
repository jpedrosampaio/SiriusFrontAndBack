# Sirius Command Center — Phase 13

## Directed audit

Base main `4a90864ad3657526264a04e5892a2741739ad5e9`, after Phase 12. The existing Home eagerly combined dashboard aggregates, optional panels and the Agent daily preview. `global_search.py` already scoped queries to the owner but capped each kind at five without continuation and omitted questions, source documents and conversations. `Memory` already had kind/hash/provenance, blocking and a fifty-record limit; its explicit editor exposed only legacy types. `ActionAudit` already retained Agent confirmations. Life State, the single Global Planner, FinanceEngine, preparation/Adaptive Strategy, conversation receipts and lexical RAG indexes already supplied the necessary facts and boundaries.

Reuse those engines, tables, locks, receipts and histories. Add only `command_audit` for business changes that lacked a retained reason and for safe undo; do not duplicate financial ledgers, Agent audits or provider logs. Original fourteen-phase master plan and all four CI workflows remain intact. The earlier dashboard stays available under “Painel detalhado”; it is loaded only on request.

## Home and explanations

GET `/api/command/home` is a read-only repeatable-read snapshot. Life State collects canonical domains, and `preview` invokes the existing Global Planner with **all** constraints. Home never supplies new ranking or availability. A current/future recorded commitment can be the next action; proposed blocks are explicitly unconfirmed. Unsafe planning suspends the next-action proposal. Unknown durations and availability stay unknown.

Today displays at most twelve entries while retaining the full constraint set inside the planner. Attention combines actual overdue flashcards/latest topic reviews, overdue task candidates, known FinanceEngine bill dates and recently detected official rectifications for active owned programs. Month-only obligations do not receive invented daily deadlines. Boundaries, financial incompleteness and truncation are disclosed. Areas display registered facts rather than inferred health, stability or mastery labels. Recorded financial net is never a bank balance.

`Why` standardizes evidence, constraints, limitations and source. The “Por quê?” component consumes these facts on Home, scenarios and Global Planner. It does not expose model reasoning or fabricate retrospective explanations.

## Contextual Agent

Selection strings are navigation hints. Server SQL validates every referenced program, notebook, analysis, file, question, exercise, transaction and calendar event against the authenticated owner. Archived notebook/plan scopes revoke related selection access. Names/excerpts are bounded, at most four entities are selected, and arbitrary client facts/titles are ignored. Intention is an enum. The page allowlist, blocked tools, account timezone and provider settings remain authoritative.

Scoped memories are sent only for the relevant page; blocked domain contexts are not forwarded. Global explicit memories remain available. Facts declared by a user are labeled unverified, never promoted to verified evidence. Prompt minimization keeps complete sections and explicitly lists omitted oversized sections rather than cutting JSON or inventing totals. Provider histories retain their existing independent bounds. UI/account changes clear cached contexts; navigation clears stale page selections while expanded chat retains its intentional handoff.

## Universal search

GET `/api/search/global?q=&domain=&cursor=&limit=` retains the legacy `results` array and adds typed `groups` with independent UUID keyset cursors. Two–100 character literal terms, one–ten rows per domain (default five), no unbounded offsets or full-bank reads. Cursor requires a selected domain. Queries directly scope root records and joins to the owner. Archived records/parents are excluded where relevant. Results never contain credentials, storage keys or hidden conversation context.

Domains: tasks, finance, habits, goals, calendar, workout plans/exercises/history, nutrition, notes, programs/targets/notebooks/topics, questions/errors/reviews, materials/editais and conversations. Existing RAG term indexes support document content when indexed; unindexed documents remain searchable by filename. Message content is searched using owned SQL EXISTS and only user/assistant roles; full histories are not copied to search payloads. Search pages replace the current domain page rather than accumulating unlimited results. Contextual questions pass verified record hints to the shared Agent.

## Explicit memory

`/api/command/memory` consolidates the existing `ai_memories`: Fact, Preference, Decision and preserved legacy Rule/Goal/Context. New records carry owner, scope, `user_declared` provenance and `verified=false`. The editor is shared with Agent settings. Only explicit authenticated endpoints save/correct memory; no LLM tool silently persists assumptions.

Writes require Idempotency-Key. Correction/removal require a server version derived from the existing record and provenance; concurrent changes return409. Same-key uncertain retries recover the original receipt. Receipts retain identity/version, not a second personal-content copy. Removal erases content/provenance and blocks its hash from relearning. Audit records metadata and reasons, not forgotten memory text. Fifty active memories remain the existing bounded limit; prior origins remain explicitly legacy/unknown rather than being relabeled as verified.

## Audit and undo

GET `/api/command/audit` paginates owned business records or the existing Agent audit (`source=agent`); it does not copy Agent logs. Actor, event/action, UTC timestamp, entity, structured reason and appropriate before/after summaries support review of day-plan acceptance/release, availability, operational study-plan regeneration/entry changes and memory changes. Audit and mutation commit atomically under the existing user lock. Source records and protected study blocks remain authoritative; this is not a full duplicate event store.

POST `/api/command/audit/{id}/undo` requires explicit `confirmed=true` plus idempotency. Safe reversals: latest unchanged availability (including a revision token to reject changed-and-restored/ABA edits), and an intact batch of future Global Planner allocations. Allocation snapshots include update time; every row is owned/locked and all checks precede deletion. Started, changed, missing, fixed or external records reject reversal. Restoring an unavailable training-plan preference rejects undo. Replays never award XP or repeat reversal. There is no undo for financial transactions, sent notifications, erased memory content or study-plan mutations with dependent histories.

Migration `f13c8a7b902d`, parent `e47c2b6a901d`, creates only the owned audit table and indexes. Existing histories are untouched; downgrade refuses to erase nonempty audit history. Production application exclusively uses the protected workflow and mandatory owner Environment approval before functional merge.

## Scenario Center

POST `/api/command/scenarios` composes the existing read-only Life State/Global Planner daily scenarios and optional FinanceEngine Decimal forecast. Study, workout and task candidates compete through the same allocator. Original operational dates and fixed commitments stay protected. Hypothetical monetary inputs never silently change time priorities. Responses label assumptions, unknowns and proposals; previews do not create receipts, ledger records, calendar blocks, XP or source history.

The advanced configuration reuses `GlobalPlanner`. Applying a reviewed routine remains the existing `/life/accept` confirmation/fingerprint/idempotency contract. No scenario endpoint applies financial or other module writes. Financial projections are not bank balances or predictions of unregistered income.

## Progressive portability

GET `/api/command/export/{dataset}/{json|csv}` exports explicit canonical fields from the authenticated owner. Default100, maximum200 records; ascending UUID pages with `next_cursor` in JSON and `X-Export-Next-Cursor`. Supported sets are listed in `services/command_export.py` and in the UI. Daily date filters apply only to compatible sets, with invalid ranges rejected. Unknown values remain null and Decimal money remains exact strings. Before transferring rows, PostgreSQL checks projected page size inside the same repeatable-read snapshot; oversized pages return413 without silently dropping records. Response cap2MB; reduce the page limit when needed.

CSV uses UTF-8/BOM, quoting and formula neutralization for spreadsheet programs. Exports omit credentials, provider prompts, message context, storage keys and other owners; message export includes only user/assistant roles. Extracted materials export metadata; original file binaries are not newly retained or promised. JSON `sirius-export/1` identifies schema, scope and ordering. These are progressive canonical-record exports, not a complete disaster-recovery backup or restoration format. Existing finance/study/nutrition exports remain available.

GET `/api/command/export/daily-report.pdf` renders the same owned daily projection and discloses display limits, estimates and unknowns. It escapes user text. Export and PDF reads have no provider calls or production mutations and use `Cache-Control: no-store`.

## Validation and publication

Local disposable PostgreSQL and mocked providers only. Specific coverage includes ownership, pagination/literal/indexed search, client context manipulation, memory provenance/concurrent correction/blocking, audit atomicity, conflict-aware undo and uncertain retries, previews without writes/XP, exact money and CSV/PDF export. Browser flows exercise Home, Why, memory retries/conflicts, confirmed undo, scenario preview, download, contextual search, recovery/account switch and overflow at320/390/768/1024/1440.

All pre-existing backend, PostgreSQL, security, migration safety, frontend unit/lint/build and browser suites remain required. A clean Codex review of the final head, four exact-head green CI checks, owner-approved protected migration, reviewed-head merge and exact Vercel/Northflank deployments plus read-only production verification are still pending publication gates. Detailed final evidence belongs in a separate historical publication record; Phase14 requires new explicit authorization.
