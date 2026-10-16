# Notification maintenance publication

Published on 2026-10-16 UTC, preserving the original fourteen phases and all modules. The universal edital analyzer remains a separate delivery in progress.

- Branch: `fix/notification-presentation-dedup`; [PR55](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/55).
- Reviewed head: `eaacbbc02fa7845369b1c63035a46238a806ffda`.
- Merge: `ffa02f45f06711d23bdb02e69c10430321ae847b`, using the reviewed expected head. Both commits have the identical Git tree `cfe1ca46e1e93116188c4a38ffaa4088f0799ec4`.
- [Final Codex receipt](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/55#issuecomment-6216592439): no major issues; final-head machine state completed with no findings and no unresolved threads.

## Behavior and evidence

The old presentation Map disappeared on reload, two components polled scheduled reminders, and stale inbox ordering could hide new events. Owned durable receipts now distinguish claim, grouping, render confirmation and read. One controller presents compact previews, revalidates source/policy/quiet hours, groups simultaneous reminders and makes routine pop-ups opt-in. Central history and explicit read remain independent.

Browser-only reminders reserve an occurrence without consuming it. Native API acceptance has a separate idempotent ACK, with Service Worker support, bounded waits, recovery of lost ACKs, isolated conflicting peers, and explicit duplicate-risk consent for ambiguous manual retries. Quiet/offline backlog and IANA/DST dates are preserved. Historical routine candidates without a generated briefing remain accessible without a fabricated report or a history-wide error. Design and residual limits: [NOTIFICATION_PRESENTATION](../NOTIFICATION_PRESENTATION.md).

Local validation: 418 PostgreSQL tests, 6 mocked YouTube tests, 193 backend regressions, 5 security tests, 12 protected-migration safety tests, model check, lint/build and 79 frontend unit tests passed. All 20 browser suites passed; the expanded notification cases passed at 320/390/768/1024/1440, including reload/tabs/devices, owner changes, quiet rules, failed read, native failures, lost ACK, deleted peer, configuration 503 and queued foreign-account exclusion. One earlier edital-test click timeout was retained, investigated with isolated execution and followed by a complete passing rerun without reducing assertions. A tutor receipt test was repaired to wait for the successful retry response rather than an already-visible record; its same-key/provider-once assertions remain.

All four final-head workflows passed:

- [PostgreSQL persistence](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38908033814).
- [Backend/browser regressions](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38908033781).
- [Production migration safety](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38908033675).
- [Frontend, all 20 browser suites](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38908033806).

The exact merge also passed all four main workflows: [PostgreSQL](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38909877263), [regressions](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38909876740), [migration safety](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38909877653), [frontend](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/38909877267).

## Deployment and production validation

GitHub deployment records confirmed the exact merge: Northflank `7120487408` succeeded at 13:42:55 UTC; Vercel Production `7120573366` succeeded at 13:46:49 UTC. Public backend `health/live` and `health/ready`, current notification OpenAPI contracts, frontend/required JS chunks and the PWA worker passed read-only verification. Thirteen private GET routes returned 401 without authentication. Public login and offline PWA boot passed at all five widths, with no page errors, overflow or legacy telemetry requests. The inspection helper initially used the wrong OpenAPI placeholder name (`delivery_id` instead of `identity`); correcting the helper verified the deployed route without changing product code.

No migration, paid service, real AI call or production test write was used. Production smoke was public/read-only; it did not manufacture notices in real accounts. API acceptance/render receipts are not proof of human attention or reading. A crash after reserving but before acknowledging remains visible as unconfirmed rather than automatically replaying a potentially displayed notice.
