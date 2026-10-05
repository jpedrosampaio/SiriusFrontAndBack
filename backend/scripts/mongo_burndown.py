"""Track remaining real Mongo calls by domain; never accesses a database."""
import ast
import json
from collections import Counter
from pathlib import Path
from inventory_persistence import inventory,ROOT

GROUPS={
 'identity':'users user_sessions',
 'planning':'tasks task_instances habits habit_logs calendar_commitments',
 'finance':'transactions budgets finance_categories credit_cards invoices projections monthly_bills',
 'goals':'goals',
 'studies':'study_areas study_programs study_targets notebooks topic_progress study_sessions focus_sessions study_notes study_tasks study_schedules study_dated_plans study_drafts flashcards quizzes quiz_attempts question_logs study_attempts study_topic_reviews study_streaks simulados simulado_attempts mindmaps redacoes',
 'health':'workout_plans workout_sessions workout_logs workout_insights body_measurements daily_workout_status meals diets recipes nutrition_recipes nutrition_goals water_logs meal_plans shopping_lists',
 'agent':'ai_actions ai_audit ai_conversations chat_messages ai_memory ai_preferences ai_events ai_insights ai_usage gemini_usage daily_summaries',
 'files_rag':'ai_attachments ai_chunks ai_embeddings edital_analyses edital_jobs',
 'contest':'contest_sources contest_updates contest_host_limits',
 'notifications':'notifications notification_logs telegram_link_codes telegram_links',
 'other':'activity_requests achievements challenges daily_quotes reports',
}


def main():
    data=inventory()
    counts=Counter()
    for name,row in data['collections'].items():
        group=next((k for k,v in GROUPS.items() if name in v.split()),'other')
        counts[group]+=len(row['calls'])
    imports=[]
    identifiers=Counter()
    for path in sorted(ROOT.rglob('*.py')):
        if any(part in ('tests','scripts','alembic','__pycache__') for part in path.relative_to(ROOT).parts) or path.name=='server_partial.py': continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            modules=[]
            if isinstance(node,ast.Import): modules=[a.name for a in node.names]
            if isinstance(node,ast.ImportFrom): modules=[node.module or '']
            for module in modules:
                if module.split('.')[0] in ('motor','pymongo','bson','gridfs'):
                    imports.append(f'{path.relative_to(ROOT).as_posix()}:{node.lineno}: {module}')
            if isinstance(node,ast.Name) and node.id in ('ObjectId','MongoClient','AsyncIOMotorClient','AsyncIOMotorGridFSBucket'):
                identifiers[node.id]+=1
    report={'initial_direct_calls':669,'remaining_direct_calls':sum(counts.values()),
        'remaining_collections':len(data['collections']),'remaining_dynamic_accesses':len(data['dynamic_calls_to_resolve']),
        'remaining_gridfs_constructors':identifiers['AsyncIOMotorGridFSBucket'],
        'domains':dict(sorted(counts.items())),'mongo_imports':imports,'mongo_identifiers':dict(identifiers)}
    destination=ROOT.parent/'docs'
    (destination/'mongo-burndown.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    lines=['# Mongo runtime burn-down','','Baseline: 669 chamadas diretas. Contagens geradas de código, não de dados. Um domínio só está concluído quando as rotas reais e sua cobertura PostgreSQL passam. A linha identity inclui acessos de XP/outros domínios à coleção users, não apenas rotas de autenticação.','',
        '| Domínio | Chamadas Mongo restantes |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in sorted(counts.items())]
    lines += ['',f"Total direto: **{report['remaining_direct_calls']}**; collections: **{report['remaining_collections']}**; dinâmicos: **{report['remaining_dynamic_accesses']}**; construtores GridFS: **{report['remaining_gridfs_constructors']}**; imports: **{len(imports)}**.",'',
        'Scripts de inventário, testes e server_partial.py (sem import pelo app) são excluídos. As chamadas dinâmicas ainda precisam ser migradas, mesmo quando repetem collections já contadas. As chamadas em helpers recebem os domínios das collections; uma operação composta pode aparecer em mais de uma linha.','',
        'Histórico de implementação: 669 → 646 (identidade) → 627 (tarefas/hábitos/calendário) → 584 (finanças) → 578 (metas) → 544 (catálogo de estudos) → 526 (atividades de estudo) → 504 (workspace) → 462 (Studies 2.0) → 433 (análises/fila de editais; GridFS removido) → 407 (importação/cronogramas/verticalização) → 384 (simulados) → 369 (flashcards/quizzes) → 351 (tarefas/estatísticas de estudo) → 347 (aulas/histórico) → 340 (mapas/redações) → 337 (materiais PDF) -> 326 (workout sessions) -> 320 (workout plans) -> 318 (workout generation/import) -> 314 (workout improvements) -> 306 (workout logs/stats) -> 301 (workout history) -> 291 (daily workout) -> 279 (measurements/insights) -> 262 (nutrition core) -> 257 (recipes) -> 242 (nutrition plans/shopping) -> 238 (study/nutrition exports) -> 233 (reports) -> 227 (dashboard summary). Consulte o JSON para a contagem exata da revisão corrente.']
    (destination/'MONGO_BURNDOWN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='mongo_imports'}))


if __name__=='__main__': main()
