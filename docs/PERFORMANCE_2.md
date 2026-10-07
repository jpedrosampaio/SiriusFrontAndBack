# Sirius Stability / Performance 2

## Baseline — main 59b054c (2026-10-07)

Audit performed before application changes. Runtime confirmed: React/Vercel → FastAPI/Northflank → PostgreSQL/Neon. Live and ready returned HTTP 200. No infrastructure or schema replacement planned.

Reproduce: build frontend, then `VISUAL_CASES=dashboard,workouts,chat,tasks,habits,calendar,finance,nutrition,reports,agent node tests/smoke.cjs` (PowerShell: set `$env:VISUAL_CASES`). Browser APIs are intercepted with synthetic owned data; these measurements are not production latency.

Dashboard initial requests at each of 1440/1024/768/390/320 px: 5 (`auth/me`, `stats/dashboard`, `dashboard/panels`, `ai/actions`, `ai/insights`). Heading timings: 848/244/309/255/287 ms respectively; cold chunk startup and local machine noise prevent attributing differences to code. The 390 timing must be verified against saved output before comparison; no latency gain claimed.

### Flow audit

| Flow | Current finding / scope |
| --- | --- |
| Signup/login/session/reload/logout | ProtectedRoute gates session; getCurrentUser already coalesces requests in memory. Auth events/storage events exist; new caches must cancel and clear on session changes. |
| Dashboard | Core summary parallel; panels secondary; analytics intersection loaded. Preserve these optimizations. DailyWorkspace unnecessarily loads actions/insights while details closed. |
| Daily plan | Reads owned tasks and real calendar, excludes completed instances; 08–18 window and fixed 240 budget; task domain has no persisted duration. Keep explicit 30-min estimate without migration. |
| Chat/new/history | Conversation/list sequential; full history refetched on event after POST; pending user message removed on failure/cancel. Backend request receipts already support replay. Preserve request payload for retries. |
| Agent proposals/confirm/cancel | Explicit controls and SQL idempotent receipts already exist; preserve writes and provider router. Degraded metadata exists but needs a discreet label. |
| Tasks/habits | Existing feedback/guards; habits toolbar overflows at 768. Verify existing SQL ownership/XP tests. |
| Calendar | Calendar SQL is owner-scoped; horizontal overflow at 768/390/320 in synthetic smoke. |
| Finance | Requests and writes already separated by tabs; some read failures silent; toolbar overflow at 768/390/320. Do not change financial rules. |
| Studies | Existing lazy module, syllabus/session flows and mocked smoke; no sections 67+ scope. |
| Workouts/active session | Per-plan daily status HTTP fan-out; status SQL individually loads plan graph. Optional status failure currently replaces known checks with empty state. Tutorial expanded UI reusable; no workout YouTube service. |
| Nutrition | Six parallel initial requests plus weekly trend, recipes/diets loaded even on diary tab; overflow at 768/390/320. Preserve user data on optional failure. |
| Reports | Separate lazy page, existing feedback; no overflow in baseline. |
| Agent settings | Existing preferences/key configuration and loading; no router rewrite required. |

Expanded baseline smoke: 50 page/viewport combinations; 10 overflow failures (habits 768; finance/nutrition/calendar 768/390/320). Dashboard, chat, workouts, tasks, reports and settings had no overflow in those fixtures. Mocked fixtures do not prove live provider quality, real mobile keyboard behavior, or production SQL timings.

## Changes and after measurements

Pending implementation and verification. Only measured results will be recorded. Server-Timing already exists in production; preserve it. No persistent offline cache, no YouTube calls from CI, no production mutations.
