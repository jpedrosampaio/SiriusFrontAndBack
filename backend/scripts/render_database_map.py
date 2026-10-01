"""Render the source inventory into the cutover checklist (never copies data)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
inventory = json.loads((root/'docs/database-inventory.json').read_text(encoding='utf-8'))
groups = {
 'Identidade': 'users user_sessions telegram_link_codes telegram_links',
 'Planejamento': 'tasks task_instances habits habit_logs goals calendar_commitments',
 'Finanças': 'transactions finance_categories budgets credit_cards invoices projections monthly_bills',
 'Estudos': 'study_areas study_programs study_targets notebooks topic_progress study_sessions focus_sessions study_notes study_tasks study_schedules study_dated_plans study_drafts flashcards quizzes quiz_attempts question_logs study_attempts study_topic_reviews study_streaks simulados simulado_attempts mindmaps redacoes',
 'Saúde': 'workout_plans workout_sessions workout_logs workout_insights body_measurements daily_workout_status meals diets recipes nutrition_recipes nutrition_goals water_logs meal_plans shopping_lists',
 'Agent': 'ai_actions ai_audit ai_conversations chat_messages ai_memory ai_preferences ai_events ai_insights ai_usage gemini_usage daily_summaries',
 'Arquivos/RAG': 'ai_attachments ai_chunks ai_embeddings edital_analyses edital_jobs',
 'Concursos existentes': 'contest_sources contest_updates contest_host_limits',
 'Atividades/relatórios': 'activity_requests achievements challenges daily_quotes notifications notification_logs reports',
}
targets = {
 'activity_requests': 'activity_receipts', 'transactions':'financial_transactions',
 'calendar_commitments':'calendar_events', 'habit_logs':'habit_checks',
 'habits':'habits + habit_checks', 'goals':'goals + goal_checks + goal_sprints',
 'notebooks':'study_notebooks + study_topics', 'topic_progress':'topic_progress (uma linha/tópico)',
 'focus_sessions':'study_sessions (source=focus)', 'study_attempts':'question_attempts',
 'question_logs':'question_attempts (fatos agregados identificados pela origem)',
 'study_topic_reviews':'study_review_events + projeção de próxima revisão',
 'flashcards':'flashcards + flashcard_reviews', 'study_dated_plans':'study_plans + study_plan_entries',
 'study_schedules':'study_schedules', 'quizzes':'quizzes + questions',
 'quiz_attempts':'quiz_attempts + question_attempts', 'simulados':'exams + exam_questions',
 'simulado_attempts':'exam_attempts + question_attempts',
 'ai_conversations':'ai_conversations + ai_messages', 'chat_messages':'ai_messages',
 'ai_memory':'ai_memories', 'ai_audit':'ai_action_audit',
 'ai_attachments':'files', 'ai_chunks':'rag_sources + rag_chunks', 'ai_embeddings':'rag_embeddings (opcional)',
 'edital_jobs':'edital_jobs + files (storage externo)',
 'workout_plans':'workout_plans + workout_plan_days + plan_exercises',
 'workout_sessions':'workout_sessions + session_exercises + workout_sets',
 'workout_logs':'workout_logs (fatos preservados)', 'meals':'meals + meal_items',
 'recipes':'recipes + recipe_ingredients', 'nutrition_recipes':'recipes (origem identificada)',
 'challenges':'challenges + challenge_completions',
}
lines = ['# Mapa de substituição da persistência', '',
 'Base inspecionada: `e2b1bfd60c225d22329b9a28ac0daf3b4e8ee702`. Inventário estático de 80 collections com acesso direto, mais duas collections internas do GridFS. Destinos abaixo são o desenho de corte, não uma declaração de implementação concluída.', '',
 'Campos, chamadas e linhas exatas estão em [database-inventory.json](database-inventory.json). O inventário de campos captura literais nas queries e updates; modelos Pydantic e documentos construídos em variáveis precisam da revisão de domínio. Os nove acessos dinâmicos estão separados no JSON e não foram descartados.', '',
 '| Collection / finalidade | Domínio | Campos consultados (amostra) | Relações | Destino SQL / estratégia | Escritas transacionais atuais |',
 '|---|---|---|---|---|---|']
for name, row in inventory['collections'].items():
    domain = next((k for k,v in groups.items() if name in v.split()), 'Revisar')
    fields = [f for f in row['fields'] if '.' not in f and len(f)<40][:12]
    relations = [f for f in row['fields'] if f.endswith('_id') and '.' not in f]
    target = targets.get(name,name)
    strategy = 'split relational' if '+' in target or name in ('topic_progress','question_logs') else 'table'
    if domain == 'Arquivos/RAG' and name in ('ai_attachments','edital_jobs'):
        strategy = 'external storage metadata'
    if name in ('edital_analyses','reports','ai_preferences','ai_actions','ai_events'):
        strategy += ' + JSONB somente para estrutura variável'
    lines.append(f"| `{name}` | {domain} | {', '.join(fields) or 'ver origem'} | {', '.join(relations) or 'sem referência explícita nesta amostra'} | {target}; {strategy} | {len(row['transactions'])} chamadas com session explícita |")
lines += ['', '## Índices e transações', '',
 'Índices explícitos por collection estão no JSON. `operations.ensure_query_indexes` acrescenta owner/date para finanças, estudos e saúde; Agent e Contest Watch criam índices próprios no startup atual. O destino move todo DDL para Alembic. Uma contagem zero de session explícita não comprova ausência de transação: helpers e chamadas dinâmicas precisam ser seguidos.', '',
 '`run_activity_mutation` centraliza transações compostas, recibos, XP e eventos. `award_xp` possui caminho transacional e CAS standalone. Esses caminhos serão substituídos por transação SQL com lock de usuário. Finance, Agent e atividades não podem confirmar parcialmente.', '',
 '## Particularidades', '',
 '- GridFS: `edital_inputs.files` e `edital_inputs.chunks`, usados pela fila de análise; destino é metadata em `files` e bytes em storage externo. Não exportar arquivos antigos.',
 '- Nenhum `expireAfterSeconds` encontrado no runtime inspecionado. Sessões, propostas e leases possuem expiração lógica; Postgres precisa de cleanup explícito limitado, fora de requests.',
 '- RAG: Atlas `$vectorSearch` em `ai/rag.py`; destino pgvector opcional, filtro por dono e revalidação da fonte. Busca lexical continua sendo uma modalidade explícita.',
 '- Aggregations: `analytics_service.py`, `dashboard_service.py`, `report_metrics.py`, `ai/core.py`, `study_workspace_routes.py` e `server.py`; converter filtros/agregações para SQL parametrizado sem carregar históricos inteiros.',
 '- Jobs: EditalJobs, automações do Agent e Contest Watch. Preservar leases/idempotência, evitar polling que impeça scale-to-zero.',
 '- IDs públicos existentes já são strings, vários com prefixos ou hashes; destino UUID opaco. Não preservar ObjectId. `pop(_id)` atual é limpeza documental; GridFS usa ID interno.',
 '- `server_partial.py` é candidato legado; confirmar ausência de imports/entrypoints antes de remover.',
 '- As funcionalidades de Contest Watch já existentes serão preservadas; não expandir integrações nesta etapa.',
 '- Não há migração de dados, dual-write, shadow-read ou sincronização entre bancos.']
(root/'docs/DATABASE_REDESIGN_MAP.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
