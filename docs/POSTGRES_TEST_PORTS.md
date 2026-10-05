# Regression ports during runtime cutover

Mongo tests remain for unported domains. Their planning cases moved to
`backend/tests/test_postgres_runtime_planning.py`, against `server.app` and a real
disposable PostgreSQL database. No fake Mongo adapter is used.

| Previous coverage | SQL replacement |
| --- | --- |
| repeated task/habit completion and undo | `test_repeated_task_and_habit_completion_and_undo_each_apply_once` |
| checkbox/Kanban consistency, reload, per-day state | `test_checkbox_kanban_reload_and_day_isolation` |
| concurrent opposite states | `test_opposite_states_leave_matching_xp` |
| independent task dates, habit dates and streak | `test_distinct_habit_dates_and_independent_task_rewards` |
| independent XP writers | `test_other_xp_writers_coexist` |
| lost response, receipt replay, old replay after undo | `test_same_key_replays_after_lost_response_and_after_undo` |
| conflicting key, foreign task/habit, per-user key scope | `test_key_conflict_and_user_isolation` |
| task/habit rollback after XP mutation | `test_task_and_habit_failure_roll_back_state_xp_receipt` |
| toggle precondition and safe replay | `test_toggle_requires_key_and_replay_is_safe` |
| invalid dates, key, body without writes | `test_invalid_inputs_do_not_write` |
| one-query task listing, recurrence empty state | `test_instances_loaded_in_one_query_and_recurrence_filter` |
| legacy duplicates, foreign instances | `test_database_rejects_duplicate_and_foreign_instances` |

The Mongo-only standalone transaction rejection test is obsolete: PostgreSQL
provides transactions without replica-set configuration; rollback is tested above.
Legacy task duplicate/status normalization is not a data migration requirement:
SQL uniqueness, foreign keys and completion/status checks prevent those invalid
records. Legacy plaintext Gemini-key migration was replaced with encrypted SQL
credential tests because legacy data is explicitly discarded.

Additional SQL coverage checks archive semantics and retention of completion
evidence. Mongo focus, workouts, dashboard, dated plans and practice tests remain
until their equivalent runtime ports are ready.

Focus completion/replay and injected-failure rollback from
`test_activity_regression.py` now execute against PostgreSQL in
`test_postgres_runtime_study_activity.py`. The same suite ports both topic-progress
ownership and path/boolean-validation cases from `test_study_workspace_regression.py`.
It additionally verifies SQL study/question totals and streaks. The saved-edital
regression remains in its original suite until that domain is migrated.

Workspace: draft save/read/retry/conflicting tabs and ownership/validation now run
in `test_postgres_runtime_workspace.py`. The same suite ports the Mongo dated-plan
preservation/overbooking and topic-practice replay/ownership/counts tests.
Date validation is verified at the actual HTTP endpoint. Pure planner tests remain
unchanged in `test_workspace_features_regression.py`; its fake draft collection
was removed after the SQL equivalents passed.

Studies 2.0: individual-attempt concurrent replay/ownership and target creation
replay now run in `test_postgres_runtime_studies_v2.py`. That suite also covers
the two former mock ownership tests, full performance/overview/library/reviews
responses and normalized blueprint exam creation. The Mongo simulado submission
test stays active until the corresponding submission route is connected to SQL.

- WorkspaceTests.test_saved_analysis_requires_owner_and_excludes_raw_pdf: consolidado em RuntimeEditais.test_saved_analysis_owner_source_exclusion_and_delete_cache_copies, com rotas reais e PostgreSQL, leitura entre donos negada e texto/páginas ausentes; teste mock Mongo removido após equivalência passar.

- EditalJobTests (3 mocks GridFS): portados para RuntimeEditalJobs (PostgreSQL real + storage local descartável), mantendo sucesso/limpeza, falha sem retry de IA, validação de upload e limite por dono; acrescentados lease expirado, isolamento e 503 sem storage.

- StudyTransactions.test_simulado_replay_commits_one_grade_xp_and_evidence e TopicExamTests (3 mocks): portados/consolidados em RuntimeExams, usando server.app e SQL real. Seis submits concorrentes geram uma correção/XP/revisão; gabarito ponderado e branco, contexto de tópico, dono antes da IA, contagem inválida sem gravação, rollback, histórico/estatísticas/archive e PDF com limpeza testados. O helper Mongo de correção foi removido; grade puro permanece coberto.

- LessonTests.test_lessons_require_owned_notebook: portado para RuntimeStudyHistory.test_lessons_require_owned_active_notebook_before_provider, SQL real/HTTP, mantém isolamento antes de chamar YouTube e acrescenta archive. Testes puros de cache/provedor permanecem. Histórico acrescenta intervalo civil, acumulação, empty state e ownership.

- ActivityTransactionTests.test_workout_start_and_completion_serialize_and_replay: portado para RuntimeWorkoutSessions.test_start_revision_and_completion_serialize_and_replay com rotas reais/SQL. Oito starts produzem uma sessão, updates concorrentes da revisão 0 geram um sucesso/um conflito, dez conclusões geram um log/XP. Acrescentados ownership, séries normalizadas, rollback, histórico, abandono e seleção da semana 2 em plano de quatro semanas. Helper Mongo workout_session_service removido sem consumidores restantes.

- CalendarTests.test_invalid_start_day_never_falls_back_to_whole_plan: consolidado em RuntimeWorkoutSessions.test_owner_validation_and_abandon; índices negativos, fora do calendário, string e booleano retornam 422 e não criam sessão. Testes puros de calendário e geração permanecem.

- CalendarTests.test_improve_uses_user_llm_and_preserves_four_weeks: portado para RuntimeWorkoutGeneration.test_improve_owned_plan_preserves_four_weeks_and_parent, com SQL/HTTP reais. Preserva calendário e original, retry de resposta parcial, dono antes de IA e FK do plano anterior. Demais testes puros de calendário seguem ativos, com o writer de geração substituído por mock somente nesses testes de algoritmo.

- HistoryTests.test_exact_exercise_name_and_literal_regex: portado para RuntimeWorkoutHistory.test_exact_literal_exercise_history_and_owner. Nome exato insensível a caixa, parênteses literais, tentativa `.*` sem correspondência e isolamento agora verificados via HTTP/SQL. A suíte também prova ausência de contagem dupla sessão/log, wildcard literal em evolução e cargas com séries incompletas/sem dados.

- MetricsTests.test_report_full_history_date_and_owner: ported to RuntimeReports.test_report_full_history_date_and_owner with PostgreSQL real data (1005 rows per fact), owner/date isolation, Decimal, civil-date UTC boundaries and blank-answer exclusion. RuntimeReports also covers real HTTP snapshots, concurrent replay, rollback, list filtering and owned download. Other Mongo metrics/Agent tests remain until their domains are ported.

- Dashboard Mongo tests from ActivityTransactionTests/MetricsTests: consolidated in RuntimeDashboard.test_dashboard_real_percent_applicable_tasks_full_history_and_owner. Real HTTP/SQL preserves 1005-entry full history, ownership, focus minutes, progress average, future-task exclusion and once/weekly recurrence. Added empty dashboard and evidence-based suggestions checks. Mongo analytics and conversations tests remain active pending their ports.

- MetricsTests.test_analytics_matches_legacy_and_exceeds_its_limits: ported to RuntimeAnalytics.test_analytics_contract_full_history_owner_and_period. Explicit legacy response contract, >5000 transactions, exact cents, owner filtering, 7/90-day ranges, invalid range and zero-filled days are covered in PostgreSQL. Added XP ledger replay/undo/rollback tests. The old informational Mongo-only latency printout is obsolete after cutover; no SQL-versus-Mongo benchmark is claimed. Historical analytics_legacy_fixture.py remains test-only, not imported by runtime.

- Agent Core SQL reads/context: 5 new integration tests cover every read tool, composed daily/weekly responses, owner/archive, invalid page IDs, 1005-row Decimal totals, timezone/month boundary, completed focus counted once, four-week plans, limits and >30 calendar events preserving unavailable time. No existing Mongo conversation/action tests removed in this step.

- ActionTransactionTests (2 Mongo tests) ported to RuntimeAgentActions using the real AgentRuntime router and PostgreSQL. Concurrent R$48 confirmation, ownership, rollback after write, cancellation and persisted expiration preserved. Added duplicate proposal, live action refresh, policy change after proposal, tool-version rejection, task/calendar conflict and study XP replay/foreign notebook. PostgresAgent foundation tests remain.

- Mock blocked-memory test ported to RuntimeMemory: real AgentRuntime endpoints with SQL verify owner isolation, edit, erasure/hash tombstone, cross-category/case/spacing recreation block, permanent delete, six concurrent duplicate saves and concurrent 50-memory limit. Pure fingerprint normalization remains in regression tests.

- MetricsTests.test_conversation_ownership_replay_and_bounded_context ported to SQLConversations. Added real AgentRuntime/server aliases, active-lease contention, cancellation/failure release, expired-token takeover rejection, live SQL action refresh, 200-message retention, 12 receipts and cursor/offset pagination. All cases from test_metrics_regression.py now have SQL equivalents (reports/dashboard/analytics/conversations), so its empty legacy Mongo CI invocation was removed; other Mongo CI jobs remain.

- Mock RAG ownership/revocation test ported to RuntimeRetrieval with real SQL/AgentRuntime routes: duplicate PDF uploads, citations/page, owner isolation, source deletion/archive, refreshed notebook content, rollback of initial attachment and replacement chunks. Pure chunk/quiet-hour tests remain. No vector performance claim; runtime retrieval is lexical only.
