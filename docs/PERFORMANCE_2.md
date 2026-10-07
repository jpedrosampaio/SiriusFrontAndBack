# Sirius Stability / Performance 2

## Baseline — main 59b054c (2026-10-07)

Audit performed before application changes. Runtime confirmed: React/Vercel → FastAPI/Northflank → PostgreSQL/Neon. Live and ready returned HTTP 200. No infrastructure or schema replacement planned.

Reproduce: build frontend, then `VISUAL_CASES=dashboard,workouts,chat,tasks,habits,calendar,finance,nutrition,reports,agent node tests/smoke.cjs` (PowerShell: set `$env:VISUAL_CASES`). Browser APIs are intercepted with synthetic owned data; these measurements are not production latency.

Dashboard initial requests at each of 1440/1024/768/390/320 px: 5 (`auth/me`, `stats/dashboard`, `dashboard/panels`, `ai/actions`, `ai/insights`). Heading timings: 848/244/309/(not retained)/287 ms respectively; cold chunk startup and local machine noise prevent attributing differences to code. no latency gain claimed.

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

DailyWorkspace now loads a deterministic preview automatically, showing free time, task blocks and fixed appointments. No capacity field, hidden 240 limit, redundant weekly button, or silent calendar write. Available time is the sum of real gaps in the **documented estimated 08–18 window**, not a claim that we know the user's working hours. Tasks have no persisted duration field: estimate remains 30min, visibly marked. Explicit API capacity remains supported for existing callers; default has no hard budget. No migration.

Chat keeps failed user messages with associated retry; distinct 401/409/429/503/504/network/timeout wording. Retry retains request_id **and the whole original payload**, preventing changed context from invalidating receipts. Replayed IDs replace pending messages once. Owned stored user-message context includes request_id so explicit refresh can reconcile a reply committed before network loss. Successful sends update conversation/list cache locally and notify other open instances with data. Initial history/list fetch in parallel; manual reload invalidates them. Degraded replies get a discreet data-based label. Existing provider/router and confirmed Agent writes retained.

Incremental TanStack Query: dashboard snapshot and planner use observers; workout plans/status and chat use targeted cache fetch/update; videos queried only in mounted tutorials. Memory only, session epoch namespaces, cancelled/cleared on auth/storage session changes; page state remounts on account transitions. No polling, aggressive focus refetch or automatic mutation retry. Desktop hover/focus on Workout navigation prefetches only plans. Chat transport no longer invalidates unrelated domain summaries. Legacy domain writes conservatively invalidate mutable queries. Optimistic daily exercise toggle guarded against double-click, with idempotency key and rollback.

| Assertion | Before | After / evidence |
| --- | --- | --- |
| Dashboard initial HTTP requests | 5 measured at all five widths | 4 measured (`auth/me`, `stats/dashboard`, `ai/daily`, `dashboard/panels`); core identity/summary still 2 |
| Closed suggestions | 2 measured requests | 0 asserted in browser; fetch enabled only when opened |
| Workout daily status | Per-plan requests confirmed by source audit; original baseline fixtures had no plans | 3-plan browser fixture: 1 batch request, 0 per-plan calls, 9 total initial requests including optional panels/session |
| Batch daily status SQL | Previous individual route loaded each plan graph and checks | 2 SELECT statements asserted with SQLAlchemy cursor instrumentation for multiple owned plans; excludes authentication query |
| Chat successful retry | Failure removed pending message in source; no before request-count measurement | Across all five widths: 409/429/503/504/network each recovers, identical retry payload, single user message, zero post-success conversation GETs |
| YouTube | No workout integration | 0 initial requests, 1 on open, 0 additional on reopen while cache valid; 0 initial iframe, iframe only after click |
| Expanded page smoke overflow | 10 failed page/width combinations | 0 after fixing page flex minimum widths, wrapping habit/export toolbars |

After broad local synthetic run heading times 1440/1024/768/390/320: 262/181/183/156/186ms. Unlike baseline, this run includes preceding signup/login/reload flows and warmed assets. These are **not directly comparable latency improvements**. Gzip main bundle grows approximately 8.5kB from adding query caching; no claim of reduced bundle size. No production SQL benchmarks collected. Server-Timing already exists and was preserved; observed ready request had app timing without SQL details.

## Validation

- All 180 PostgreSQL tests passed; final receipt-context change separately revalidated by all 6 conversation integration tests. Batch tests include ownership, concurrency, transactions and two-query assertion.
- 96 backend regressions passed; mocked YouTube tests cover key absence, malformed input, normalization, timeout/status failures, projection, auth, cache/coalescing/bounds.
- Frontend lint, 41 unit tests and production build passed. Broad synthetic smoke covers auth, dashboard/modal, full chat, workouts, studies/preparation/analysis/syllabus/study session, tasks, habits, finance, nutrition, reports, calendar, settings at 1440/1024/768/390/320. Additional workout smoke covers active session, drafts/reload, series, tutorial text/videos/cache/embed at the same widths.
- Read-only production smoke before merge: frontend/health/live/health/ready/OpenAPI HTTP200; 250 existing routes; expected auth/chat/workout paths; CORS accepts exact Vercel origin. No production users or records created.

## Limits

Browser APIs/providers are mocked and mobile keyboard is simulated by viewport height; physical-device keyboard and YouTube result quality remain manual checks. No YouTube live test or production key verification. Cache is process/browser memory and disappears on restart/reload; optional offline persistence deferred. Finance/nutrition maintain their existing domain loading architecture; no broad refactor of all modules. 08–18 is transparent estimated planning window, not inferred personal availability. No schema changes, Mongo imports, startup DDL, paid providers, or later Studies67+ features introduced.
# Operational Corrections — atualização da Fase A

Base: merge PR #23 (`c10b907`). O escopo mantém o orçamento HTTP do dashboard e do batch de treino; nenhuma busca de YouTube foi antecipada. Chat em hidratação usa os dois GETs iniciais e o POST, sem refetch de sucesso; o teste controla a resposta tardia e verifica exatamente uma resposta/mensagem. Três cliques rápidos geram três POSTs serializados por plano (sem fanout de leitura), cada um com receipt próprio. Timeout/5xx interrompe o envio posterior até retry seguro; 409/4xx definitivo desfaz só a operação rejeitada.

O briefing com texto em cache agora consulta novamente tarefas e hábitos para calcular progresso atual: há custo SQL adicional deliberado para evitar score congelado, sem invocar LLM nem recarregar refeições/estudos/treinos nessa leitura. Nenhum ganho de latência de produção foi medido nesta fase. Bundle principal local: aproximadamente 184,29 kB gzip, contra 184,26 kB no PR #23; sem novas dependências. Detalhes de contratos/migration: [OPERATIONAL_PLANNING.md](OPERATIONAL_PLANNING.md).

## Workout Session UX2 — Fase B

Base auditada antes das alterações: main `c5c3f2c`, PR #24. O smoke de sessão ativa com três planos registrou 9 GETs iniciais, um batch de status e nenhum GET individual de status/histórico/evolução/YouTube. Na fonte anterior, iniciar já usava um POST e um GET de próximas cargas para o plano inteiro; a navegação visual nova não introduz fan-out.

| Fluxo | Antes | UX2 / evidência sintética |
| --- | --- | --- |
| Página de treinos com sessão existente | 9 GETs medidos, 1 batch/0 individuais | Mesmos 9 GETs no fixture legado sem `plan_id`; sessão com `plan_id` também busca uma sugestão para o plano, inclusive ao retomar |
| Iniciar sessão de 12 exercícios | POST + próximas cargas por plano (auditoria da fonte), refresh de identidade pelo evento de escrita | 12 chamadas totais desde a página: 9 GETs iniciais + 1 POST start + 1 GET auth/me existente + 1 GET next-loads, nos cinco viewports |
| Trocar exercício visualmente | Todos os cards eram renderizados juntos | 0 chamadas; rascunho local por exercício |
| Tutorial fechado | 0 chamadas de vídeo | 0; uma chamada ao abrir, cache existente e iframe só ao clicar |
| Histórico fechado | Sob demanda | 0; uma chamada por exercício não cacheado; falha/retry explícitos |
| Séries/descanso | PATCH por série + timer local | PATCH por série; retry preserva chave/payload; nenhum polling; desfazer usa um PATCH extra somente quando acionado |

Build local: principal aproximadamente 184,67 kB gzip (base Fase A 184,29 kB); chunk lazy de Workouts aproximadamente 31,96 kB e CSS UX2 2,21 kB. Sem nova dependência. Não se atribui ganho de latência ou SQL de produção a medidas de browser interceptado. A retomada agora apresenta sugestão de carga quando há plano, custo adicional de uma chamada por plano/sessão, não por exercício. Histórico, evolução completa e vídeos continuam sem preload.

Verificação: suite frontend unitária e quatro smokes de browser, incluindo fluxo UX2 em 1440/1024/768/390/320, carga decimal/vazia, 3/8 séries, 12 exercícios, retry depois de commit/reload, 409, desfazer persistido, timer, tutorial, histórico, resumo e abandono. Veja [WORKOUT_SESSION_UX2.md](WORKOUT_SESSION_UX2.md) para contratos e limites de teclado/Wake Lock simulados.
