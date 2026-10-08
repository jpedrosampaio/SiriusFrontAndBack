# Adaptive Strategy Engine

Phase 5 separates a pure ranking (`backend/adaptive_strategy.py`) from capacity allocation (`backend/study_planner.py`). Inputs come from owned PreparationState facts, active canonical topics, answered individual questions, latest reviews, dated blocks and deadline tasks. No AI calls, paid services, new infrastructure or duplicated ledger. Legacy nonadaptive planning remains available.

## Contracts

- GET `/api/study/programs/{program_id}/strategy`: ranked candidates, categorized debt, a default next-28-day preview ending no later than the target, three scenarios and assumptions. An expired target produces no new blocks.
- POST `.../strategy/simulate`: read-only scenarios with start/end, seven weekday minute budgets, block size and `missed_days` (0–181). Start must be today or later, horizon at most181 days, capacity0–720 and at least one day with15 min. A target date is enforced. No receipt, plan, progress, answer, review or XP is written.
- Existing POST `.../dated-plan`: `adaptive=true` consumes ranked candidates. `recovery=true` additionally replaces uncompleted automatic blocks from the past28 days. Completed, manual, fixed and out-of-window blocks remain untouched. Recovery never adds missed minutes to daily capacity. Client retries keep a stable idempotency key/payload; the existing activity receipt and user lock protect actual persistence.
- Legacy active notebooks without canonical topics fall back to the existing discipline allocator, with an explicit reason that topic priorities are unavailable. Enabling adaptation must not silently erase all future blocks merely because the topic snapshot is empty. No fictitious topic or mastery is invented.
- Topic-linked blocks preserve their canonical UUID. The frontend opens the stored active topic key; archived links are marked unavailable rather than falling back to a different topic. Legacy blocks with no link retain the old topic-selection flow.

## Versioned operational formula

Version `adaptive-strategy-1`. Components are additive:

| Component | Contribution |
|---|---|
| Uncovered |15, otherwise0 |
| Estimated mastery gap |30 × (1 − estimated score/100); unknown uses50% only for ranking, not a reported mastery fact |
| Recent mistakes |min(15,3 × mistakes in latest5 answered questions) |
| Latest review due today or earlier |15 |
| Evidence age |10 × (1 − exp(−age_days/60)); no evidence yields0 plus the insufficient-evidence component |
| Fewer than5 answered individual questions |10 |
| Accuracy decline |5 if two complete consecutive samples of5 answers declined by more than10 percentage points |

Multiply by1.2 if target is0–30 days away and clamp to100. This is operational risk, not failure probability or a claim that the user forgot. No future timestamps increase age. Risk components, reasons, source status and evidence IDs are returned.

Impact = clamped registered discipline weight (0.1–100) × registered question count (1–200, unknown1) ÷ active topic count in the discipline. Unknown/unverified weights and incidence are labeled for confirmation; no official distribution per topic is invented. Expected return = impact × risk/100 ÷ suggested cost. Cost is50 minutes for initial contact,25 for a covered topic/review; these are explicit defaults, not measured learning times. Ordering is deterministic with canonical ID tie breaking.

Review suggestions use the existing mastery and history rule (1–45 days), recent mistakes, previous review count, optional difficulty, and reported guess/uncertain confidence. Limited confidence halves the interval; weight≥3 multiplies by0.75, always with minimum1 day. Confidence does not change mastery. Current persisted review due dates are respected; suggestions do not rewrite historical review events. Automatic adaptive blocks cannot schedule the same review twice within its suggested interval.

History counts distinct calendar dates in the owner's timezone strictly before today, matching the existing attempt/exam writers. Multiple answers/events during one day never count as multiple prior review days. The batched aggregation also returns `review_history_days` for audit.

## Capacity, scenarios and recovery

The allocator picks expected return divided by (1 + already allocated minutes/suggested cost), to avoid repeating the same highest-ranked topic all day. It never exceeds weekday capacity minus preserved blocks and calendar reservations. Minimum block15 min; unusable remainder stays free. Review candidates respect their due date and suggested interval. Canonical IDs produce stable preview block IDs; SQL entries retain normal UUID identities.

Partial review blocks accumulate across days. The interval starts only after at least25 suggested minutes are allocated in that cycle, then cycle progress resets. With15-minute blocks this requires two blocks (30 minutes), respecting the minimum chunk and each day's capacity. A single partial block never defers the remaining work by an entire review interval.

A uses entered capacity, B caps each day at45 min, C at25 min. Missed days reserve the firstN simulation days for no new suggestions; existing protected blocks remain, explicitly counted. Projected coverage only adds unstarted topics with at least50 suggested minutes, assumes actual completion, and never marks real progress. Due reviews without25 suggested minutes and critical topics without50 remain listed as unaddressed. Deadline tasks and flashcards are not falsely completed by simulation. Expired targets have no new capacity projection.

Debt categories: reviews before today, risk≥40 unstarted topics, covered topics with evidence-age contribution≥5, missed dated blocks in28-day window, and uncompleted owned once-only active tasks with elapsed deadlines. Those tasks are the existing intermediate-goal evidence; unattached tasks cannot be assigned to a preparation. Recurring tasks use their own completion flow and are not treated as once-only milestones.

Load guard warns on protected over-capacity days, seven or more consecutive scheduled days, consistency<50%, or a scheduled7-day window above max(180 min,1.5 × recent actual weekly minutes) when at least3 completed sessions exist. It suggests a break after50 min; blocks have no wall-clock start/end, so it does not claim to measure continuous work or diagnose burnout.

## Limits and migration

PreparationState bounds:2000 books/topics/reviews/sessions/materials,5000 answers,100 ledger items,28 days of debt/history. Latest reviews and lifetime review counts are batched. Deadline tasks are filtered by ownership, preparation and completion before a501-row read; display500 with truncation propagated. Each scenario returns at most200 entries plus true count; UI shows20 blocks and10 ranked candidates. Larger source snapshots remain explicitly partial, never complete promises.

Migration `a81c9d37e502`, parent `b73a16ce9024`, adds only nullable `study_plan_entries.topic_id` and an owner-scoped FK. No backfill or rewrite of completed/manual/fixed history. Downgrade removes only the optional link. Round-trip tests use an isolated disposable loopback database and verify original protected rows, question and attempt facts remain. Production migration must be applied by the owner before merge, per the master plan. Exact-head readiness may return503 between migration and matching deployment.

No real provider/production writes in tests. Pure tests cover deterministic ranking, bounded decay, risk unknowns, safe reviews, protected capacity, missed-week A/B/C and conditional coverage. SQL tests cover simulations without writes, ownership, periods, milestone exclusions, recovery/history, topic identity/archive and receipt replay. Browser checks cover all five widths, scenario switching, Saturday capacity, lost-week simulation, double-click locks, uncertain delivery retry and opening the correct topic.
