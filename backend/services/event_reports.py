"""Daily/night/weekly factual composition. No AI metrics, writes or competing planner."""
from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, text
from fastapi import HTTPException
from db.session import unit_of_work
from db.models.identity import User
from db.models.planning import Task, TaskInstance, CalendarEvent, Habit, HabitCheck
from db.models.studies import StudySession, StudyPlanEntry
from db.models.health import WorkoutLog
from db.models.finance import FinancialTransaction
from task_recurrence import expand_task_dates
from event_contracts import Briefing


async def briefing(user_id, *, mode='morning', day=None, now=None, transaction=None):
    if mode not in ('morning','night','weekly'):raise HTTPException(422,'Resumo desconhecido.')
    uid=UUID(str(user_id));instant=now or datetime.now(timezone.utc)
    if instant.tzinfo is None:raise ValueError('Aware instant required')
    limitations=['Planejado é reconstruído dos registros atuais; mudanças antigas sem snapshot não permitem medir aderência histórica exata.',
        'Tempo registrado não comprova a execução de cada bloco; nenhum horário ou plano é alterado por este resumo.']
    async with unit_of_work(session=transaction) as session:
        if transaction is None:await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        user=await session.get(User,uid)
        if user is None:raise HTTPException(404,'Conta não encontrada.')
        zone=ZoneInfo(user.timezone);today=instant.astimezone(zone).date();end=day or today
        if not today-timedelta(days=30)<=end<=today:raise HTTPException(422,'Consulte hoje ou os últimos 30 dias.')
        start=end-timedelta(days=6) if mode=='weekly' else end
        tasks=list((await session.scalars(select(Task).where(Task.user_id==uid,Task.archived_at.is_(None),Task.date<=end,
            (Task.recurrence!='once')|(Task.date>=start)).order_by(Task.date,Task.id).limit(501))).all())
        partial=len(tasks)>500;tasks=tasks[:500]
        if partial:limitations.append('Tarefas: limite de 500 modelos; totais planejados são desconhecidos.')
        instances=(await session.execute(select(TaskInstance.task_id,TaskInstance.date,TaskInstance.completed).where(
            TaskInstance.user_id==uid,TaskInstance.task_id.in_([r.id for r in tasks]),TaskInstance.date.between(start,end)))).all()
        completed={(identity,str(when)) for identity,when,done in instances if done}
        expected=[(row,when) for row in tasks for when in expand_task_dates({'date':str(row.date),'recurrence':row.recurrence},str(start),str(end))]
        pending=[{'id':str(row.id),'date':when,'title':row.title[:200]} for row,when in expected if (row.id,when) not in completed]
        task_done=await session.scalar(select(func.count()).select_from(TaskInstance).where(TaskInstance.user_id==uid,
            TaskInstance.date.between(start,end),TaskInstance.completed.is_(True)))
        study=(await session.execute(select(func.count(),func.coalesce(func.sum(StudySession.duration_minutes),0)).where(
            StudySession.user_id==uid,StudySession.completed.is_(True),StudySession.date.between(start,end)))).one()
        planned=(await session.execute(select(func.count(),func.coalesce(func.sum(StudyPlanEntry.minutes),0),
            func.count().filter(StudyPlanEntry.completed.is_(True))).where(StudyPlanEntry.user_id==uid,StudyPlanEntry.date.between(start,end)))).one()
        workout=(await session.execute(select(func.count(),func.coalesce(func.sum(WorkoutLog.duration_minutes),0)).where(
            WorkoutLog.user_id==uid,WorkoutLog.completed.is_(True),WorkoutLog.date.between(start,end)))).one()
        active_habits=await session.scalar(select(func.count()).select_from(Habit).where(Habit.user_id==uid,Habit.archived_at.is_(None)))
        checks=await session.scalar(select(func.count()).select_from(HabitCheck).where(HabitCheck.user_id==uid,HabitCheck.date.between(start,end)))
        financial=dict((await session.execute(select(FinancialTransaction.type,func.sum(FinancialTransaction.amount)).where(
            FinancialTransaction.user_id==uid,FinancialTransaction.date.between(start,end)).group_by(FinancialTransaction.type))).all())
        tomorrow=end+timedelta(days=1);lower=datetime.combine(tomorrow,time(),zone);upper=datetime.combine(tomorrow+timedelta(days=1),time(),zone)
        agenda_query=select(CalendarEvent).where(CalendarEvent.user_id==uid,CalendarEvent.start_at<upper,CalendarEvent.end_at>lower)
        agenda=list((await session.scalars(agenda_query.order_by(CalendarEvent.start_at,CalendarEvent.id).limit(21))).all())
        if len(agenda)>20:limitations.append('Agenda de amanhã: exibição limitada a 20 registros; use Calendário para todos os compromissos.')
        from services.nutrition_data import period
        nutrition,_,_=await period(session,uid,start,end)
        calories=sum(v['calories'] for v in nutrition.values()) if all(v['calories'] is not None for v in nutrition.values()) else None
        facts={'window':{'start':str(start),'end':str(end)},
            'tasks':{'expected_current_templates':None if partial else len(expected),'recorded_completed':task_done,'pending':pending[:20],
                'pending_count':None if partial else len(pending),'partial':partial or len(pending)>20},
            'preparation':{'planned_entries':planned[0],'planned_minutes':planned[1],'marked_completed_entries':planned[2],
                'recorded_sessions':study[0],'recorded_minutes':study[1]},
            'training':{'recorded_completed':workout[0],'recorded_minutes':workout[1],'planned_days':None},
            'habits':{'expected_current_templates':active_habits*((end-start).days+1),'recorded_checks':checks},
            'finance':{'recorded_income':str(financial.get('income',0)),'recorded_expense':str(financial.get('expense',0)),
                'bank_balance':None,'basis':'Transações próprias no período; não é saldo bancário.'},
            'nutrition':{'recorded_meals':sum(v.get('meals_count',0) for v in nutrition.values()),'calories':str(calories) if calories is not None else None,
                'basis':'Composição desconhecida propaga desconhecido; datas sem registros não são avaliação de alimentação.'},
            'tomorrow':{'date':str(tomorrow),'commitments':[{'id':str(r.id),'title':r.title[:200],
                'start':r.start_at.astimezone(zone).isoformat(),'end':r.end_at.astimezone(zone).isoformat(),
                'kind':'confirmed_plan' if r.source_type=='global_plan' else 'recorded_commitment'} for r in agenda[:20]],'display_limited':len(agenda)>20}}
        from life_contracts import Availability
        from db.models.health import WorkoutPlan
        from pydantic import ValidationError
        try:availability=Availability.model_validate((user.preferences or {}).get('life_availability',{}))
        except ValidationError:availability=None
        if availability and availability.training_plan_id:
            owned_plan=await session.scalar(select(WorkoutPlan.id).where(WorkoutPlan.id==availability.training_plan_id,
                WorkoutPlan.user_id==uid,WorkoutPlan.archived_at.is_(None)))
            if owned_plan:
                weekdays=availability.training_weekdays
                facts['training']['planned_days']=sum((start+timedelta(days=i)).weekday() in weekdays for i in range((end-start).days+1))
                facts['training']['plan_basis']='Dias da preferência atual, sem presumir qual sessão foi cumprida.'
    proposals=[]
    if end==today:
        from services.life_state import daily, agent_context, agent_plan, collect as life_collect, preview
        if transaction is not None:
            life=await life_collect(transaction,uid,now=instant)
            current={'state':life.model_dump(mode='json'),'plan':preview(life,now=instant)}
        else:current=await daily(uid,now=instant)
        facts['life_state']=agent_context(current['state'])
        facts['global_plan']=agent_plan(current['plan'])
        limitations.extend(current['state']['warnings'])
        if pending or planned[0]>planned[2]:
            proposals.append({'kind':'review_global_plan','title':'Revisar disponibilidade e pendências no Global Planner',
                'link':'/calendar','reasons':['Há ocorrências ou blocos registrados ainda pendentes.'],
                'requires_confirmation':True})
    else:limitations.append('Estado unificado e disponibilidade atual não são apresentados como snapshot histórico.')
    return Briefing(mode=mode,date=end,timezone=user.timezone,generated_at=instant,facts=facts,
        proposals=proposals,limitations=list(dict.fromkeys(limitations))[:30])


def render_text(report):
    facts=report['facts'];labels={'morning':'Seu dia no Sirius','night':'Revisão do dia','weekly':'Revisão semanal'}
    task=facts['tasks'];study=facts['preparation'];workout=facts['training'];finance=facts['finance']
    lines=[f"{labels[report['mode']]} · {report['date']} ({report['timezone']})",
        f"Tarefas: {task['recorded_completed']} conclusões registradas; {task['pending_count'] if task['pending_count'] is not None else 'quantidade desconhecida de'} pendências nos modelos atuais.",
        f"Estudos: {study['recorded_minutes']} min registrados; {study['planned_minutes']} min nos blocos atuais.",
        f"Treinos: {workout['recorded_completed']} registros concluídos, {workout['recorded_minutes']} min.",
        f"Despesas registradas no período: R$ {finance['recorded_expense']} (não é saldo bancário)."]
    lines.extend('Pendente: '+p['title'] for p in task['pending'][:3])
    lines.extend('Amanhã: '+c['title']+' · '+c['start'] for c in facts['tomorrow']['commitments'][:3])
    if report['proposals']:lines.append('Há propostas para revisar no Sirius; nada foi reorganizado automaticamente.')
    lines.append('Limitações: '+report['limitations'][0])
    return '\n'.join(lines)[:3900]
