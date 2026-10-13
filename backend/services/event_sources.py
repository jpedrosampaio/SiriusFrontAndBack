"""Bounded canonical readers. References/cursors belong to the outbox, facts to their domains."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_, and_
from db.session import unit_of_work
from db.models.identity import User
from db.models.planning import Task, TaskInstance, Goal
from db.models.studies import StudySession, StudyPlanEntry, StudyProgram, StudyTarget, Notebook
from db.models.health import WorkoutLog
from db.models.finance import FinancialTransaction
from db.models.contests import ContestUpdate
from event_contracts import EventCandidate
from services.study_evidence import latest_reviews, attempts
from question_intelligence import forensic_clusters

PAGE = 40


def candidate(kind, source, occurrence, facts, reason, identity=None):
    return EventCandidate(event_type=kind, entity_type=source, entity_id=identity,
        occurrence=str(occurrence), facts=facts, reasons=[reason])


async def collect(user_id, *, now=None, cursors=None, target=None, transaction=None):
    """Keyset pages rotate even when records remain unresolved; target rechecks bypass cursors."""
    uid=UUID(str(user_id)); instant=now or datetime.now(timezone.utc)
    if instant.tzinfo is None: raise ValueError('Aware instant required')
    cursors=dict(cursors or {}); next_cursors={}; result=[]; limitations=[]
    async with unit_of_work(session=transaction) as session:
        from sqlalchemy import text
        if transaction is None:await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        user=await session.get(User,uid)
        if user is None:return [],{},['Conta indisponível.']
        local=instant.astimezone(ZoneInfo(user.timezone)); day=local.date()
        lower=datetime.combine(day-timedelta(days=6),time(),ZoneInfo(user.timezone))

        async def page(model, source, *conditions):
            query=select(model).where(model.user_id==uid,*conditions)
            if target and target.entity_type==source:
                query=query.where(model.id==target.entity_id)
            elif target:return []
            elif source in cursors:
                try:query=query.where(model.id>UUID(cursors[source]))
                except (ValueError,TypeError):pass
            rows=list((await session.scalars(query.order_by(model.id).limit(PAGE+1))).all())
            if not target:
                if rows:next_cursors[source]=str(rows[min(len(rows),PAGE)-1].id)
                if len(rows)>PAGE:limitations.append(f'{source}: leitura incremental; há mais registros para o próximo lote.')
            return rows[:PAGE]

        from task_recurrence import expand_task_dates
        tasks=await page(Task,'task',Task.archived_at.is_(None),Task.date<day)
        occurrence_conditions=[and_(TaskInstance.task_id==r.id,TaskInstance.date==r.date) for r in tasks if r.recurrence=='once']
        occurrence_conditions.append(and_(TaskInstance.task_id.in_([r.id for r in tasks if r.recurrence!='once']),
            TaskInstance.date.between(day-timedelta(days=32),day-timedelta(days=1))))
        instances=(await session.execute(select(TaskInstance.task_id,TaskInstance.date).where(
            TaskInstance.user_id==uid,or_(*occurrence_conditions),TaskInstance.completed.is_(True)))).all() if tasks else []
        done={(identity,str(when)) for identity,when in instances}
        for row in tasks:
            dates=[str(row.date)] if row.recurrence=='once' else expand_task_dates(
                {'date':str(row.date),'recurrence':row.recurrence},str(day-timedelta(days=32)),str(day-timedelta(days=1)))
            pending=[when for when in dates if (row.id,when) not in done]
            if row.recurrence!='once':pending=pending[-1:]
            if target:pending=[when for when in pending if when==target.occurrence]
            for when in pending:
                result.append(candidate('task.overdue','task',when,{'title':row.title[:200],'due_date':when},
                    'Ocorrência registrada vencida e ainda pendente; recorrentes mostram a última pendência nos últimos 32 dias.',row.id))
        if any(r.recurrence!='once' for r in tasks):limitations.append('Alertas recorrentes mostram a última ocorrência pendente em 32 dias; histórico anterior não é varrido nem alterado.')
        completed_instances=await page(TaskInstance,'task_instance',TaskInstance.completed.is_(True),TaskInstance.date.between(day-timedelta(days=6),day))
        task_titles={r.id:r for r in (await session.scalars(select(Task).where(Task.user_id==uid,Task.archived_at.is_(None),
            Task.id.in_([r.task_id for r in completed_instances])))).all()} if completed_instances else {}
        for row in completed_instances:
            task=task_titles.get(row.task_id)
            if task:result.append(candidate('task.completed','task_instance',row.date,{'title':task.title[:200],'date':str(row.date)},
                'Conclusão registrada na ocorrência da tarefa.',row.id))
        active_programs=select(StudyProgram.id).where(StudyProgram.user_id==uid,StudyProgram.archived_at.is_(None),StudyProgram.status=='active')
        for model,source,kind,conditions in [
            (StudySession,'study_session','study.session.completed',[StudySession.completed.is_(True),StudySession.date.between(day-timedelta(days=6),day)]),
            (WorkoutLog,'workout_log','workout.completed',[WorkoutLog.completed.is_(True),WorkoutLog.date.between(day-timedelta(days=6),day)]),
            (FinancialTransaction,'transaction','expense.created',[FinancialTransaction.type=='expense',FinancialTransaction.created_at>=lower,FinancialTransaction.created_at<=instant]),
            (ContestUpdate,'contest_update','edital.updated',[ContestUpdate.detected_at>=lower,ContestUpdate.detected_at<=instant,ContestUpdate.program_id.in_(active_programs)])]:
            for row in await page(model,source,*conditions):
                if source=='contest_update':
                    facts={'title':row.title[:200],'official':row.official,'source_type':row.source_type,
                        'impact_available':bool(row.changes),'url':(row.url or '')[:2000]}
                    occurrence=row.content_hash
                else:
                    facts={'date':str(row.date)};occurrence=str(row.date)
                    if source=='transaction':facts.update(amount=str(row.amount),category=row.category,title=(row.description or row.category)[:200])
                    else:facts['recorded_minutes']=row.duration_minutes
                result.append(candidate(kind,source,occurrence,facts,'Registro canônico próprio; nenhuma atividade foi alterada.',row.id))
        active_books=select(Notebook.id).join(StudyProgram,(StudyProgram.id==Notebook.program_id)&(StudyProgram.user_id==Notebook.user_id)).where(
            Notebook.user_id==uid,Notebook.archived_at.is_(None),StudyProgram.archived_at.is_(None),StudyProgram.status=='active')
        for row in await page(StudyPlanEntry,'study_block',StudyPlanEntry.notebook_id.in_(active_books),StudyPlanEntry.completed.is_(False),
            StudyPlanEntry.date.between(day-timedelta(days=6),day-timedelta(days=1))):
            result.append(candidate('study.block.missed','study_block',row.date,{'title':row.name[:200],'date':str(row.date),'planned_minutes':row.minutes},
                'Bloco datado ainda não concluído; replanejamento é somente proposta.',row.id))
        for row in await page(StudyTarget,'study_target',StudyTarget.exam_date.between(day,day+timedelta(days=90)),StudyTarget.program_id.in_(active_programs)):
            if row.metadata_origin not in ('manual','official','extracted','user_confirmed'):
                limitations.append('Datas de prova de origem desconhecida/inferida não disparam alertas.');continue
            distance=(row.exam_date-day).days
            milestone=next(n for n in (0,1,2,7,14,30,90) if distance<=n)
            result.append(candidate('exam.approaching','study_target',f'{row.exam_date}:{milestone}',
                {'title':row.name or 'Prova registrada','exam_date':str(row.exam_date),'days_remaining':distance,'origin':row.metadata_origin},
                'Marco calculado da data e origem registradas, sem atribuir fonte oficial a dados manuais.',row.id))
        # Existing Questions Intelligence contracts exclude aggregate/blank/unmapped attempts.
        if target is None or target.entity_type in ('review','question_cluster'):
            after=UUID(cursors.get('review','00000000-0000-0000-0000-000000000000')) if not target else None
            reviews=await latest_reviews(session,uid,due=day,limit=PAGE+1,after_id=after,
                review_id=target.entity_id if target and target.entity_type=='review' else None)
            if not target and reviews:next_cursors['review']=reviews[min(len(reviews),PAGE)-1]['review_id']
            if len(reviews)>PAGE:limitations.append('Revisões: leitura incremental; mais registros no próximo lote.')
            for row in reviews[:PAGE]:
                if target and target.entity_type!='review':continue
                if target and str(target.entity_id)!=row['review_id']:continue
                result.append(candidate('study.review.overdue','review',row['due_date'],row,
                    'Próxima revisão registrada no contrato de Preparação está vencida.',UUID(row['review_id'])))
            evidence=await attempts(session,uid,user.timezone,limit=501,active_topics=True)
            if len(evidence)>500:limitations.append('Questões: no máximo 500 tentativas recentes; recorrências são evidências locais, não diagnóstico completo.')
            evidence=[r for r in evidence[:500] if datetime.fromisoformat(r['answered_at'])>=lower and datetime.fromisoformat(r['answered_at'])<=instant]
            # A later correct attempt resolves that question's previous error for this alert.
            latest={}
            for row in evidence:latest.setdefault(row['internal_question_id'],row)
            unresolved=[r for r in evidence if not latest[r['internal_question_id']]['correct']]
            for cluster in forensic_clusters(unresolved):
                if target and (target.entity_type!='question_cluster' or target.occurrence!=cluster['fingerprint']):continue
                result.append(candidate('question.failed','question_cluster',cluster['fingerprint'],cluster,
                    'Questions Intelligence: pelo menos três questões distintas no mesmo assunto e causa; classificação heurística.'))
        for goal in await page(Goal,'goal',Goal.archived_at.is_(None),Goal.target_date<day,Goal.progress<100):
            result.append(candidate('goal.off_track','goal',goal.target_date,
                {'id':str(goal.id),'title':goal.title[:200],'target_date':str(goal.target_date),'progress':goal.progress},
                'Prazo informado vencido com progresso registrado abaixo de 100%; não presume trajetória ideal.',goal.id))
        if target is None or target.entity_type=='nutrition':
            # Reuse the exact domain adapter without loading unrelated modules for a nutrition alert.
            from services.life_adapters import nutrition as nutrition_adapter
            nutrition_state=await nutrition_adapter(session,uid,day,ZoneInfo(user.timezone))
            nutrition=nutrition_state.facts;limitations.extend(nutrition_state.warnings)
            remaining={k:v for k,v in nutrition.get('remaining',{}).items() if v is not None and Decimal(str(v))>0}
            if remaining and local.hour>=18:
                result.append(candidate('nutrition.target_remaining','nutrition',day,{'remaining':remaining,'origin':nutrition.get('target_origin')},
                    'Diferença calculada apenas de metas confirmadas e composição conhecida; não é prescrição.'))
    # Public engine contracts are read independently; no module writes or copied financial ledger.
    if target is None or target.entity_type in ('budget','obligation'):
        from services.finance_intelligence import FinanceEngine
        finance=await FinanceEngine().get_state(uid,months=1,now=instant,session=transaction)
        limitations.extend(finance.warnings)
        for budget in finance.budgets:
            if target and (target.entity_type!='budget' or str(target.entity_id)!=budget.budget_id):continue
            limit=budget.effective_limit
            if limit is None or limit<=0 or budget.spent<limit*Decimal('0.8'):continue
            kind='budget.exceeded' if budget.spent>limit else 'budget.threshold_reached'
            result.append(candidate(kind,'budget',finance.month,{'category':budget.category,'spent':str(budget.spent),'limit':str(limit),
                'basis':budget.basis},'80% do limite efetivo registrado; saldo bancário não é presumido.',UUID(budget.budget_id)))
        for bill in finance.upcoming_bills:
            source_uuid=UUID(bill.source_id.split(':',1)[-1])
            if target and (target.entity_type!='obligation' or target.entity_id!=source_uuid or target.facts.get('source_type')!=bill.source_type):continue
            if bill.due_date is None:
                limitations.append('Obrigações sem dia conhecido não geram alertas de vencimento exato.');continue
            if bill.due_date>day+timedelta(days=3):continue
            result.append(candidate('bill.due','obligation',bill.due_date,bill.model_dump(mode='json'),
                'Obrigação materializada não paga e vencimento conhecido no FinanceEngine.',source_uuid))
    if target:result=[c for c in result if c.event_type==target.event_type and c.entity_type==target.entity_type and c.entity_id==target.entity_id and c.occurrence==target.occurrence]
    return result,next_cursors,list(dict.fromkeys(limitations))[:30]
