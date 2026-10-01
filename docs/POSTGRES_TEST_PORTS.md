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
