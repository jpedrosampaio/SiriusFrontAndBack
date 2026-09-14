# Concurrent XP updates

All 25 route-level XP read/overwrite blocks now call `award_xp`.
The helper reads the persisted balance and conditionally updates both XP and
rank only if that balance has not changed. A conflicting write retries with
a fresh balance. This works on standalone MongoDB as well as replica sets;
it does not require a schema migration or transactions.

Deductions retain the existing zero floor. Responses return the balance
produced by the operation, including the goal daily-check endpoint.
Legacy accounts without XP are initialized conditionally. Deleted accounts
return 404. Sustained contention is bounded to 100 attempts, then returns 503.

## Validation

Regression tests cover retrying stale reads, unchanged zero balances, missing
XP, deleted accounts and retry exhaustion. A separate CI job uses disposable
MongoDB 7 to exercise concurrent awards, mixed deltas, deductions and
initialization. Existing task, security and service-worker checks remain enabled.

## Scope and remaining work

This prevents distinct XP updates from overwriting each other. It does not make
completion state and XP a cross-document transaction, nor make habit toggles
or concurrent repeated task completions idempotent. A failure after saving
completion but before awarding XP can still leave those documents inconsistent.
Do not automatically replay a completion request solely because XP returned 503.
Duplicate-event handling and recovery require a subsequent change.
