# Notification presentation maintenance

Authorized structural maintenance, base main `70de336c09b5f7f290103a3840afd978f827453a`. Not a new phase. Implementation and technical self-review are complete; full browser/remote review/publication gates remain pending. No publication claim.

## Directed audit before changes

- `NotificationManager` remembers automated pop-ups only in a 50-entry in-memory Map. Remount/reload loses that state. Polling has no in-flight guard; configuration, permission resolution and interval can overlap.
- `GET /automations/inbox` returns the ten oldest available deliveries. Availability remains until owner read/dismiss, correctly separate from presentation. A stale unread backlog can prevent newer alerts from being considered.
- `Notifications` also polls `/notifications/check` every 30 seconds and emits its own toast/browser/audio presentations. The global manager polls the same legacy transport every minute. The server's legacy occurrence/channel receipts help prevent duplicate claims, but two clients own presentation behavior.
- `EventDelivery.history` is durable JSONB, ownership-indexed and protected by existing delivery/account transactions. Current read/dismiss replaces history; presentation audit would be lost unless that operation appends instead.
- Existing typed preferences live in the established JSON settings, and the outbox already has durable creation/availability/read states. Reuse those structures; no SQL column or migration is needed for presentation receipts/preferences.

## Contract and decisions

Event creation, central availability, presentation attempt, UI-render confirmation and explicit read remain distinct. Automatic presentation is globally coordinated per account/delivery, across devices. A transactional claim is an **at-most-once automatic attempt**, not proof the user saw or read it. A separate acknowledgement records that the client rendered the preview. If the client disappears after claiming or the acknowledgement is lost, availability/history remain and presentation can stay unconfirmed; do not automatically replay the popup. Human attention cannot be guaranteed by an HTTP receipt.

Use bounded recent candidate selection, current rule/channel/quiet-hour checks, priority/newness ordering and canonical source revalidation. Old reports remain in the central history rather than becoming current pop-ups. Group a backlog into one preview instead of a popup queue. Explicit policy controls routine-summary pop-ups independently of automation/history. Every priority respects quiet hours. Existing source frequency/daily-cap semantics remain.

Persist claim, grouped and rendered receipts in the owned in-app delivery history under account serialization; keep read/dismiss history. No provider text, credentials or personal facts go in presentation audit metadata. A replay only recovers the same brief claim window, never an already-rendered or obsolete popup. Noop polls do not create activity receipts. Manual reads retain existing idempotent receipt behavior.

A lost claim response gets one same-key retry after one second, without spending its 30-second replay window reloading configuration. Claim responses identify their owner; an ownership change invalidates the shared UI session. Later failures return to normal polling and central history rather than an unbounded retry queue.

Legacy scheduled reminders retain their due occurrence through quiet/offline periods. Missed repeats coalesce into the latest due date; a one-shot keeps its first date at the input's minute precision. SQL applies ownership, recurrence/day, creation, occurrence and supported-channel eligibility before the 50-row limit; lookahead cannot cross into quiet hours. All dates use the account timezone, including DST. The client explicitly reports browser permission: browser-only reminders remain unclaimed without it, and unsupported channels are never silently consumed. Reminders with in-app enabled can still appear there without browser permission.

One global manager owns polling/presentation. Serialize its requests, abort and fence on account change, suppress hidden-tab pop-ups, coordinate across tabs/devices through server claims, and render one compact automation/reminder toast with a central-history action. The notifications page manages reminders/history/preferences, not a second presentation poller. Browser permission remains explicit. Closing a toast is not read confirmation.

Browser-only reminders use separate owned reservations in the existing activity receipt store. A scheduler GET does not advance `last_sent`/`last_occurrence`; an idempotent acceptance ACK does, atomically with the existing browser delivery receipt. Known native API rejection leaves the occurrence eligible for another capable device (at most three automatic attempts). A lost response retries the ACK rather than the OS notice. An unresolved reservation or ambiguous API timeout stays unconfirmed and requires an explicit central retry with duplicate-risk consent. The central shows the latest occurrence and attempt count; complete transitions remain in the owned receipt history. Accepted means API acceptance, never human reading.

Use an existing Service Worker registration first, with a desktop constructor fallback only after definite rejection. Registration lookup and presentation waits are bounded. A presentation timeout is ambiguous and cannot trigger fallback. This follows [MDN's notification constructor guidance](https://developer.mozilla.org/en-US/docs/Web/API/Notification/Notification), including mobile constructor limitations. Closing an old OS surface checks its presentation token so it cannot close a newer account's notice. Notification clicks open only `/notifications`; a payload cannot redirect off origin.

Simultaneous automation and in-app reminder claims share one preview that explicitly counts the reminders; neither transport hides the other after consuming its claim. If reminder lookup fails, the already reserved automation still renders. The render acknowledgement is sent only when that final combined preview mounts.

## Acceptance

Disposable PostgreSQL and intercepted browser tests must cover new/backlogged/old deliveries, concurrent tabs/devices, reload/reconnect, owner changes, overlapping polling, disabled policies, quiet hours including high priority, read failure, presented/unread and read-confirmed states. Test transport loss independently from UI acknowledgement and retain complete history. Preserve all existing suites/19 browser scenarios and add targeted five-width coverage. Require four workflows, final-head Codex, expected-head merge and exact deploy/read-only production validation.

Detailed release evidence belongs in the PR/history; update HANDOFF only to reflect actually published state. The separately authorized universal edital pipeline remains outstanding and is not completed by this PR.
