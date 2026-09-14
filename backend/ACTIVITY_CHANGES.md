# Replay-safe task and habit completion

## Database prerequisite

MongoDB must support multi-document transactions: use Atlas, a replica set,
or a supported sharded deployment. Standalone MongoDB is not supported for these
three mutation routes. Confirm the production topology before merging/deploying.
No data migration is required. Existing completions and XP are retained.

## Behavior

Task checkbox, Kanban and habit completion now serialize on a per-user write
inside a MongoDB transaction. State, XP/rank and optional request receipt commit
together. A failed operation rolls them all back. The existing XP compare-and-set
helper accepts a session; other routes keep their existing behavior.

Clients should send `Idempotency-Key` (8-128 ASCII letters/digits/hyphen/underscore).
Receipts are stored in `activity_requests` using the built-in unique _id index,
scoped to the authenticated user. An identical replay returns the original result
plus `replayed: true`. Its XP/balance describe the original action, so clients
refresh the current state instead of treating that response as a fresh reward.
Reusing a key for another action returns 409, including after an undo.

Without a key, explicit desired state is safe for consecutive duplicate requests.
Replaying an old request after an intervening opposite action requires its
original key. Receipts intentionally have no TTL: expiring them would allow old
requests to apply again. Monitor collection size as usage grows.

Habits now accept `completed=true/false`. An old-style toggle without a key
returns 428 rather than guessing whether it is a retry. Update/reload old clients.
A keyed legacy toggle remains supported. Invalid dates return 422.

The UI sends explicit state and a request key, blocks additional actions on the
same resource until the request and refresh finish, and retains the key after an
uncertain network failure for a retry in the same mounted page. It suppresses
reward notifications on replay. The helper is shared by list and Kanban actions.

Legacy duplicate task instances are read as completed if any matching row is
completed, and normalized together on the next transition. Previously inflated
XP is not recalculated automatically.

## Validation

Existing route and XP regressions remain. New tests cover concurrent repeats,
opposite transitions, task/Kanban equivalence, separate dates, ownership, other
XP writers, lost responses, replay after undo, key misuse, rollback after the XP
write, legacy duplicates, legacy toggles and invalid input.
CI uses both a disposable MongoDB replica set and standalone MongoDB (fail-closed
verification). Node tests cover in-flight blocking and retry-key reuse.

Other modules (goals, workouts and studies) still need their own event
idempotency. Sync writes do not award XP and are outside these transactional
completion routes.
