# Mapa de substituição da persistência

Base inspecionada: `e2b1bfd60c225d22329b9a28ac0daf3b4e8ee702`. Inventário estático de 80 collections com acesso direto, mais duas collections internas do GridFS. Destinos abaixo são o desenho de corte, não uma declaração de implementação concluída.

Atualização da integração de Saúde/Nutrição: receitas usam `recipes`/`recipe_ingredients`; dietas e planos alimentares compartilham `nutrition_plans` com dias/refeições/alimentos separados; listas de compras usam `shopping_lists`/`shopping_items`. A antiga leitura de `nutrition_recipes` foi substituída pelo catálogo real de receitas. O inventário inicial abaixo é histórico; contagens atuais ficam em [MONGO_BURNDOWN.md](MONGO_BURNDOWN.md).

Campos, chamadas e linhas exatas estão em [database-inventory.json](database-inventory.json). O inventário de campos captura literais nas queries e updates; modelos Pydantic e documentos construídos em variáveis precisam da revisão de domínio. Os nove acessos dinâmicos estão separados no JSON e não foram descartados.

| Collection / finalidade | Domínio | Campos consultados (amostra) | Relações | Destino SQL / estratégia | Escritas transacionais atuais |
|---|---|---|---|---|---|
| `achievements` | Atividades/relatórios | _id, achievement_id, category, description, icon, title, unlocked_at, user_id | _id, achievement_id, user_id | achievements; table | 0 chamadas com session explícita |
| `activity_requests` | Atividades/relatórios | _id, created_at, fingerprint, result, user_id | _id, user_id | activity_receipts; table | 2 chamadas com session explícita |
| `ai_actions` | Agent | _id, action_id, confirmed_at, executed_at, expires_at, result, status, user_id | _id, action_id, user_id | ai_actions; table + JSONB somente para estrutura variável | 3 chamadas com session explícita |
| `ai_attachments` | Arquivos/RAG | _id, attachment_id, indexed, user_id | _id, attachment_id, user_id | files; external storage metadata | 0 chamadas com session explícita |
| `ai_audit` | Agent | action_id, created_at, status, tool, user_id, version | action_id, user_id | ai_action_audit; table | 1 chamadas com session explícita |
| `ai_chunks` | Arquivos/RAG | _id, generation, notebook_id, program_id, section, source_id, source_type, user_id, vector | _id, notebook_id, program_id, source_id, user_id | rag_sources + rag_chunks; split relational | 0 chamadas com session explícita |
| `ai_conversations` | Agent | _id, archive, conversation_id, created_at, lease, lease_until, messages, receipts, summary, title, updated_at, user_id | _id, conversation_id, user_id | ai_conversations + ai_messages; split relational | 0 chamadas com session explícita |
| `ai_embeddings` | Arquivos/RAG | _id, dimensions, model, user_id, vector | _id, user_id | rag_embeddings (opcional); table | 0 chamadas com session explícita |
| `ai_events` | Agent | _id, created_at, event_id, lease_until, status, type, user_id | _id, event_id, user_id | ai_events; table + JSONB somente para estrutura variável | 3 chamadas com session explícita |
| `ai_insights` | Agent | _id, created_at, date, dry_run, evidence, feedback, insight_id, link, rule, snoozed_until, title, user_id | _id, insight_id, user_id | ai_insights; table | 0 chamadas com session explícita |
| `ai_memory` | Agent | _id, blocked, category, content, created_at, hash, memory_id, user_id | _id, memory_id, user_id | ai_memories; table | 0 chamadas com session explícita |
| `ai_preferences` | Agent | _id, settings, user_id | _id, user_id | ai_preferences; table + JSONB somente para estrutura variável | 1 chamadas com session explícita |
| `ai_usage` | Agent | _id, count, user_id | _id, user_id | ai_usage; table | 0 chamadas com session explícita |
| `body_measurements` | Saúde | _id, date, measurement_id, user_id | _id, measurement_id, user_id | body_measurements; table | 0 chamadas com session explícita |
| `budgets` | Finanças | _id, budget_id, category, limit, month, spent, user_id | _id, budget_id, user_id | budgets; table | 1 chamadas com session explícita |
| `calendar_commitments` | Planejamento | _id, date, end_minute, start_minute, user_id | _id, user_id | calendar_events; table | 3 chamadas com session explícita |
| `challenges` | Atividades/relatórios | _id, challenge_id, completed_by, week_start | _id, challenge_id | challenges + challenge_completions; split relational | 0 chamadas com session explícita |
| `chat_messages` | Agent | _id, chat_type, content, created_at, message_id, role, user_id | _id, message_id, user_id | ai_messages; table | 0 chamadas com session explícita |
| `contest_host_limits` | Concursos existentes | _id, next_poll | _id | contest_host_limits; table | 0 chamadas com session explícita |
| `contest_sources` | Concursos existentes | _id, enabled, error, failures, last_checked, lease, next_poll, program_id, snapshot, source_id, status, user_id | _id, program_id, source_id, user_id | contest_sources; table | 0 chamadas com session explícita |
| `contest_updates` | Concursos existentes | _id, detected_at, document_type, program_id, source, source_id, summary, update_id, user_id | _id, program_id, source_id, update_id, user_id | contest_updates; table | 0 chamadas com session explícita |
| `credit_cards` | Finanças | _id, card_id, user_id | _id, card_id, user_id | credit_cards; table | 0 chamadas com session explícita |
| `daily_quotes` | Atividades/relatórios | _id, context, created_at, habits_today, motivational_date, quote, time_of_day, user_id, workouts_this_week | _id, user_id | daily_quotes; table | 0 chamadas com session explícita |
| `daily_summaries` | Agent | _id, date, user_id | _id, user_id | daily_summaries; table | 0 chamadas com session explícita |
| `daily_workout_status` | Saúde | _id, completed, date, exercises_status, plan_id, updated_at, user_id | _id, plan_id, user_id | daily_workout_status; table | 0 chamadas com session explícita |
| `diets` | Saúde | _id, diet_id, user_id | _id, diet_id, user_id | diets; table | 0 chamadas com session explícita |
| `edital_analyses` | Arquivos/RAG | _id, analysis_id, analysis_version, cargos, pdf_filename, pdf_hash, pdf_pages, pdf_text, reviewed_at, revision, user_id | _id, analysis_id, user_id | edital_analyses; table + JSONB somente para estrutura variável | 0 chamadas com session explícita |
| `edital_jobs` | Arquivos/RAG | _id, analysis_id, file_id, finished_at, lease_until, phase, status, user_id | _id, analysis_id, file_id, user_id | edital_jobs + files (storage externo); external storage metadata | 2 chamadas com session explícita |
| `finance_categories` | Finanças | _id, name, user_id | _id, user_id | finance_categories; table | 0 chamadas com session explícita |
| `flashcards` | Estudos | _id, ease_factor, flashcard_id, interval_days, last_review, next_review, notebook_id, repetitions, user_id | _id, flashcard_id, notebook_id, user_id | flashcards + flashcard_reviews; split relational | 0 chamadas com session explícita |
| `focus_sessions` | Estudos | _id, date, focus_minutes, user_id | _id, user_id | study_sessions (source=focus); table | 1 chamadas com session explícita |
| `gemini_usage` | Agent | _id, created_at, date, model, user_id | _id, user_id | gemini_usage; table | 0 chamadas com session explícita |
| `goals` | Planejamento | _id, daily_checks, goal_id, progress, title, user_id | _id, goal_id, user_id | goals + goal_checks + goal_sprints; split relational | 0 chamadas com session explícita |
| `habit_logs` | Planejamento | completed, date, user_id | user_id | habit_checks; table | 0 chamadas com session explícita |
| `habits` | Planejamento | _id, best_streak, completions, habit_id, name, streak, user_id | _id, habit_id, user_id | habits + habit_checks; split relational | 2 chamadas com session explícita |
| `invoices` | Finanças | _id, amount, card_id, invoice_id, month, paid, user_id | _id, card_id, invoice_id, user_id | invoices; table | 0 chamadas com session explícita |
| `meal_plans` | Saúde | _id, plan_id, user_id | _id, plan_id, user_id | meal_plans; table | 0 chamadas com session explícita |
| `meals` | Saúde | _id, date, meal_id, user_id | _id, meal_id, user_id | meals + meal_items; split relational | 0 chamadas com session explícita |
| `mindmaps` | Estudos | _id, mindmap_id, user_id | _id, mindmap_id, user_id | mindmaps; table | 0 chamadas com session explícita |
| `monthly_bills` | Finanças | _id, bill_id, month, paid, paid_date, user_id | _id, bill_id, user_id | monthly_bills; table | 0 chamadas com session explícita |
| `notebooks` | Estudos | _id, area_id, conteudo_programatico, correct_questions, name, notebook_id, program_id, title, topicos, total_questions, total_study_time_minutes, user_id | _id, area_id, notebook_id, program_id, user_id | study_notebooks + study_topics; split relational | 12 chamadas com session explícita |
| `notification_logs` | Atividades/relatórios | ver origem | sem referência explícita nesta amostra | notification_logs; table | 0 chamadas com session explícita |
| `notifications` | Atividades/relatórios | _id, enabled, last_sent, notification_id, scheduled_time, user_id | _id, notification_id, user_id | notifications; table | 0 chamadas com session explícita |
| `nutrition_goals` | Saúde | _id, calories, carbs, created_at, daily_calories, daily_carbs, daily_fat, daily_protein, fat, goal_id, protein, updated_at | _id, goal_id, user_id | nutrition_goals; table | 0 chamadas com session explícita |
| `nutrition_recipes` | Saúde | _id, recipe_id, user_id | _id, recipe_id, user_id | recipes (origem identificada); table | 0 chamadas com session explícita |
| `projections` | Finanças | _id, month, projection_id, source_transaction_id, user_id | _id, projection_id, source_transaction_id, user_id | projections; table | 0 chamadas com session explícita |
| `question_logs` | Estudos | _id, banca, concurso, correct, created_at, date, disciplina, incorrect, log_id, notebook_id, program_id, simulado_id | _id, log_id, notebook_id, program_id, simulado_id, user_id | question_attempts (fatos agregados identificados pela origem); split relational | 4 chamadas com session explícita |
| `quiz_attempts` | Estudos | _id, user_id | _id, user_id | quiz_attempts + question_attempts; split relational | 0 chamadas com session explícita |
| `quizzes` | Estudos | _id, notebook_id, quiz_id, user_id | _id, notebook_id, quiz_id, user_id | quizzes + questions; split relational | 0 chamadas com session explícita |
| `recipes` | Saúde | _id, recipe_id, user_id | _id, recipe_id, user_id | recipes + recipe_ingredients; split relational | 0 chamadas com session explícita |
| `redacoes` | Estudos | _id, user_id | _id, user_id | redacoes; table | 0 chamadas com session explícita |
| `reports` | Atividades/relatórios | _id, report_id, user_id | _id, report_id, user_id | reports; table + JSONB somente para estrutura variável | 0 chamadas com session explícita |
| `shopping_lists` | Saúde | _id, items, list_id, user_id | _id, list_id, user_id | shopping_lists; table | 0 chamadas com session explícita |
| `simulado_attempts` | Estudos | _id, simulado_id, user_id | _id, simulado_id, user_id | exam_attempts + question_attempts; split relational | 2 chamadas com session explícita |
| `simulados` | Estudos | _id, program_id, simulado_id, user_id | _id, program_id, simulado_id, user_id | exams + exam_questions; split relational | 3 chamadas com session explícita |
| `study_areas` | Estudos | _id, area_id, color, created_at, icon, name, user_id | _id, area_id, user_id | study_areas; table | 1 chamadas com session explícita |
| `study_attempts` | Estudos | _id, attempt_id, correct, error_reason, program_id, user_id | _id, attempt_id, program_id, user_id | question_attempts; table | 5 chamadas com session explícita |
| `study_dated_plans` | Estudos | _id, entries, program_id, user_id | _id, program_id, user_id | study_plans + study_plan_entries; split relational | 4 chamadas com session explícita |
| `study_drafts` | Estudos | _id, notebook_id, revision, text, user_id | _id, notebook_id, user_id | study_drafts; table | 0 chamadas com session explícita |
| `study_notes` | Estudos | _id, attachments, content, note_id, notebook_id, title, user_id | _id, note_id, notebook_id, user_id | study_notes; table | 0 chamadas com session explícita |
| `study_programs` | Estudos | _id, area_id, created_at, name, program_id, source_type, status, target_date, user_id | _id, area_id, program_id, user_id | study_programs; table | 3 chamadas com session explícita |
| `study_schedules` | Estudos | _id, program_id, schedule_id, user_id | _id, program_id, schedule_id, user_id | study_schedules; table | 0 chamadas com session explícita |
| `study_sessions` | Estudos | _id, created_at, date, duration_minutes, notebook_id, user_id | _id, notebook_id, user_id | study_sessions; table | 0 chamadas com session explícita |
| `study_streaks` | Estudos | _id, best_streak, current_streak, last_study_date, total_study_days, user_id | _id, user_id | study_streaks; table | 4 chamadas com session explícita |
| `study_targets` | Estudos | _id, program_id, user_id | _id, program_id, user_id | study_targets; table | 2 chamadas com session explícita |
| `study_tasks` | Estudos | _id, completed, task_id, user_id | _id, task_id, user_id | study_tasks; table | 0 chamadas com session explícita |
| `study_topic_reviews` | Estudos | _id, accuracy, correct, date, due_date, mastery, notebook_id, program_id, reason, review_count, title, total | _id, notebook_id, program_id, user_id | study_review_events + projeção de próxima revisão; split relational | 6 chamadas com session explícita |
| `task_instances` | Planejamento | _id, completed, created_at, date, instance_id, status, task_id, user_id | _id, instance_id, task_id, user_id | task_instances; table | 3 chamadas com session explícita |
| `tasks` | Planejamento | _id, completed, is_template, task_id, title, user_id | _id, task_id, user_id | tasks; table | 1 chamadas com session explícita |
| `telegram_link_codes` | Identidade | _id, code, created_at, expires_at, user_id | _id, user_id | telegram_link_codes; table | 0 chamadas com session explícita |
| `telegram_links` | Identidade | _id, chat_id, linked_at, status, telegram_name, unlinked_at, user_id | _id, chat_id, user_id | telegram_links; table | 0 chamadas com session explícita |
| `topic_progress` | Estudos | _id, notebook_id, progress_id, updated_at, user_id | _id, notebook_id, progress_id, user_id | topic_progress (uma linha/tópico); split relational | 0 chamadas com session explícita |
| `transactions` | Finanças | _id, bill_id, category, date, description, transaction_id, type, user_id | _id, bill_id, transaction_id, user_id | financial_transactions; table | 0 chamadas com session explícita |
| `user_sessions` | Identidade | _id, session_token | _id | user_sessions; table | 0 chamadas com session explícita |
| `users` | Identidade | _id, activity_revision, email, health_condition, name, password, picture, rank, user_id, xp | _id, user_id | users; table | 3 chamadas com session explícita |
| `water_logs` | Saúde | _id, date, user_id | _id, user_id | water_logs; table | 0 chamadas com session explícita |
| `workout_insights` | Saúde | _id, insight_id, user_id | _id, insight_id, user_id | workout_insights; table | 0 chamadas com session explícita |
| `workout_logs` | Saúde | _id, completed, date, exercises_completed, log_id, name, plan_id, user_id | _id, log_id, plan_id, user_id | workout_logs (fatos preservados); table | 1 chamadas com session explícita |
| `workout_plans` | Saúde | _id, days, description, name, plan_id, user_id | _id, plan_id, user_id | workout_plans + workout_plan_days + plan_exercises; split relational | 1 chamadas com session explícita |
| `workout_sessions` | Saúde | _id, completed_at, exercises, feedback, plan_id, plan_name, session_id, started_at, status, total_duration_seconds, user_id | _id, plan_id, session_id, user_id | workout_sessions + session_exercises + workout_sets; split relational | 7 chamadas com session explícita |

## Índices e transações

Índices explícitos por collection estão no JSON. `operations.ensure_query_indexes` acrescenta owner/date para finanças, estudos e saúde; Agent e Contest Watch criam índices próprios no startup atual. O destino move todo DDL para Alembic. Uma contagem zero de session explícita não comprova ausência de transação: helpers e chamadas dinâmicas precisam ser seguidos.

`run_activity_mutation` centraliza transações compostas, recibos, XP e eventos. `award_xp` possui caminho transacional e CAS standalone. Esses caminhos serão substituídos por transação SQL com lock de usuário. Finance, Agent e atividades não podem confirmar parcialmente.

## Particularidades

- GridFS: `edital_inputs.files` e `edital_inputs.chunks`, usados pela fila de análise; destino é metadata em `files` e bytes em storage externo. Não exportar arquivos antigos.
- Nenhum `expireAfterSeconds` encontrado no runtime inspecionado. Sessões, propostas e leases possuem expiração lógica; Postgres precisa de cleanup explícito limitado, fora de requests.
- RAG: Atlas `$vectorSearch` em `ai/rag.py`; destino pgvector opcional, filtro por dono e revalidação da fonte. Busca lexical continua sendo uma modalidade explícita.
- Aggregations: `analytics_service.py`, `dashboard_service.py`, `report_metrics.py`, `ai/core.py`, `study_workspace_routes.py` e `server.py`; converter filtros/agregações para SQL parametrizado sem carregar históricos inteiros.
- Jobs: EditalJobs, automações do Agent e Contest Watch. Preservar leases/idempotência, evitar polling que impeça scale-to-zero.
- IDs públicos existentes já são strings, vários com prefixos ou hashes; destino UUID opaco. Não preservar ObjectId. `pop(_id)` atual é limpeza documental; GridFS usa ID interno.
- `server_partial.py` é candidato legado; confirmar ausência de imports/entrypoints antes de remover.
- As funcionalidades de Contest Watch já existentes serão preservadas; não expandir integrações nesta etapa.
- Não há migração de dados, dual-write, shadow-read ou sincronização entre bancos.
