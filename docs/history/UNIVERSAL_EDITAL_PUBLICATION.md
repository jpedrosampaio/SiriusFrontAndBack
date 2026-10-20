# Universal incremental edital analyzer - deployment evidence

Deployment verified on 2026-10-20 UTC. [PR57](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/57), branch `feat/universal-edital-analyzer`, reviewed head `13200946271d6aeeeefb0b0d08a85323667f94be`, deployed merge `39ad9786ecb2eed57c3c9b65218388eedd0ebb42`. The merge differs from the reviewed head only in the independently approved migration registry. The original fourteen-phase plan, archived HANDOFF, trusted workflows and existing modules were preserved.

## Delivered scope and review

`edital/universal/6` preserves extracted PDF provenance before acceptance, discovers cargo inventory early and processes the selected/shared scope in durable small typed units. It reuses the existing job scheduler, providers, study catalog and planning engines. Responsive review includes sources, corrections, associations, findings, confirmation, history, recovery and canonical import without an LLM-generated fixed timetable.

Two P2 findings were fixed with regressions: Brazilian grouped question counts preserve magnitude (`1.000` becomes 1000, ambiguous values stay unknown); model-generated role spelling does not establish cross-analysis identity. Existing programs from the same PDF require reuse or explicit separate-program consent, while import XP is awarded once per document. Reanalysis preserves human decisions and makes unmatched corrections explicit blockers.

The subsequent P1 deletion finding was reproduced and corrected in the final head. User -> Analysis -> Job locks serialize deletion with intake/controls/workers. Active jobs are retired, references/leases cleared and sources deleted in one transaction, preserving completed job history. Deleted claims lose their lease; candidates deleted after discovery are skipped. Six new SQL tests plus an HTTP regression cover capacity release, ownership, rollback and worker races.

[Clean final Codex receipt](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/57#issuecomment-6289240506); the exact-head machine summary reported no findings and no unresolved threads remained. The [usage-limit checkpoint](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/57#issuecomment-6288949142), commits `c0e1cc0`/`a6ac92f`/`d4d700f` and the [prepublication HANDOFF](https://github.com/jpedrosampaio/SiriusFrontAndBack/blob/13200946271d6aeeeefb0b0d08a85323667f94be/HANDOFF.md) preserve the earlier pending states; those are historical, not instructions to repeat work.

## Tests and immutable CI evidence

All four workflows passed on the final feature head:

- [PostgreSQL 39410571126](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39410571126): schema from empty PostgreSQL/model agreement, 468 persistence tests and 6 mocked YouTube tests.
- [Regressions/security 39410571305](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39410571305): 235 regressions, 5 security tests and frontend unit coverage.
- [Migration safety 39410571285](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39410571285): 12 disposable PostgreSQL safety tests.
- [Frontend 39410571216](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39410571216): lint, 79 unit tests, production build and all21 browser suites, retaining 320/390/768/1024/1440 px.

Merge validation executions: [PostgreSQL 39414556563](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39414556563), [regressions 39414556588](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39414556588), [migration safety 39414556567](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39414556567), [frontend 39414556687](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39414556687). Their live results and final publication-record validation are linked from the PR conversation; previous head success is not substituted for a different SHA.

Local follow-up passed 50 targeted PostgreSQL cases, 235 regressions, 5 security tests, 12 migration-safety tests and 6 mocked YouTube tests. A full local 468-test execution had one environment-guard failure because its disposable database name lacked `test`; that startup test was repeated with a valid loopback test database and passed. The assertion was preserved. CI independently passed the entire 468-test suite. No failure was hidden or counted as success.

## Protected production migration

[Registry PR58](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/58) changed only eight registry lines, head `89659da2d1b1cbc9e61d99c054881a263907efdf`, merge `57f3ff022dabc1a26e1b0976dd31b0b2a43f1119`. Its four workflows passed: [regressions](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39412180582), [PostgreSQL](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39412180425), [safety](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39412180365), [frontend](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39412180384); [clean Codex receipt](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/58#issuecomment-6289420204).

Revision `a61015ed902b`, parent `f13c8a7b902d`; file `backend/alembic/versions/a61015ed902b_owned_edital_units.py`; Git-blob SHA-256 `f8754ff06a62934bec93126acfcd84c18dc5e099d4cfa8bde7dc256f503c9177`.

[Protected run 39413657221](https://github.com/jpedrosampaio/SiriusFrontAndBack/actions/runs/39413657221) executed from trusted main `57f3ff0`. Environment `production-migrations` was verified to accept only branch `main` and require reviewers. Preflight job `118597315478` approved the exact PR57 head and revision transition without database access. After the owner's GitHub approval, migrate job `118597396796` repeated the gates and reported **`Migration result: applied; revision a61015ed902b.`** at **2026-10-20 11:22:05 UTC**, before feature merge. Both jobs/run succeeded. No direct agent production Alembic/SQL, shared chat credential or automatic owner approval was used.

## Exact deployments and safe production checks

GitHub deployment records for merge `39ad9786ecb2eed57c3c9b65218388eedd0ebb42`:

- Northflank `7198399082`, environment `siriusfrontandback`, success at **11:23:50 UTC**.
- Vercel `7198453227`, environment `Production`, success at **11:26:21 UTC**.

Read-only checks passed against `https://back--siriusfrontandback--vbfgpbhc7tz8.code.run` and `https://siriusassistant.vercel.app`: live/ready200; preserved workout/notification contracts; incremental intake/review/import/history OpenAPI contracts; twenty unauthenticated private GET401 checks (thirteen preserved and seven analyzer/history reads); frontend HTML/assets/backend URL; pipeline and unmatched-correction UI assets; PWA worker/boot cache. No POST, authenticated import, test record or real provider call was performed.

Fresh public browser contexts passed at all five widths: login visible, no horizontal overflow, no page errors, no legacy vendor requests, viewport zoom available, offline `/login` boot and both boot assets cached. The first attempt passed320 then hit a 30s service-worker wait timeout at390. The complete repeat passed320/390/768/1024/1440 with the same assertions/timeouts and only added diagnostic logging; no application change or validation relaxation was made. The transient timeout's cause was not established. Authenticated user workflows in production were not exercised; synthetic CI covers those contracts without production writes.

## Remaining work, not started

Operational OCR, automatic rectification/complementary-document reconciliation, separately authorized real Gemini validation on heterogeneous notices, the unresolved workout `workout_generation_invalid_sessions` error and other real homologation issues remain backlog. The supplied PDF was only structurally extracted locally (70 text pages, 229422 characters, 2772 blocks, zero provider calls), never redistributed. Synthetic tests and deployment health do not prove semantic completeness or real Gemini/Groq availability. Notification maintenance PR55 and parser prerequisite PR56 are already published and were not reimplemented. No paid infrastructure was introduced; await authorization for further work.
