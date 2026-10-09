"""Independent read-only domain adapters; each emits the shared contract."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from sqlalchemy import select, func
from db.models.planning import Task, TaskInstance, CalendarEvent, Habit, HabitCheck, Goal
from db.models.studies import StudyProgram, StudyPlan, StudyPlanEntry, Notebook, StudySchedule, StudySession
from db.models.health import WorkoutPlan, WorkoutSession, WorkoutLog
from db.models.finance import FinancialTransaction, MonthlyBill, Budget
from services.nutrition_data import period
from task_recurrence import expand_task_dates
from life_contracts import DomainState, Candidate, Constraint

LIMIT = 200
FIXED_LIMIT = 1000


def candidate(domain, row, day, title, duration, link, *, priority='medium', locked=False, reasons=(), latest=None):
    return Candidate(id=f'{domain}:{row.id}:{day}', domain=domain, source_id=str(row.id), action_type=domain,
        title=title[:300], duration_minutes=duration, duration_origin='recorded' if duration else 'unknown',
        earliest=day, latest=latest or day, date_locked=locked, priority=priority, reasons=list(reasons), link=link)


async def tasks(session, uid, day, zone, now=None):
    # Temporal constraints never use the shorter display limit.
    done_once=select(TaskInstance.id).where(TaskInstance.user_id==uid,TaskInstance.task_id==Task.id,
        TaskInstance.date==Task.date,TaskInstance.completed.is_(True)).correlate(Task).exists()
    allocated_once=select(CalendarEvent.id).where(CalendarEvent.user_id==uid,
        CalendarEvent.source_type=='global_plan',CalendarEvent.source_id==Task.id,
        CalendarEvent.details['domain'].as_string()=='tasks',
        CalendarEvent.end_at>(now or datetime.now(timezone.utc))).correlate(Task).exists()
    pairs = (await session.execute(select(Task,allocated_once).where(Task.user_id == uid, Task.archived_at.is_(None),
        (Task.recurrence!='once')|Task.scheduled_time.is_not(None)|(Task.date==day)|~allocated_once,
        Task.date <= day,(Task.recurrence!='once')|(Task.date==day)|
        ((Task.scheduled_time.is_not(None))&(Task.date==day-timedelta(days=1)))|
        ((Task.scheduled_time.is_(None))&~done_once))
        .order_by(Task.date, Task.id).limit(FIXED_LIMIT+1))).all()
    rows=[row for row,_ in pairs]
    allocated={row.id for row,reserved in pairs if reserved}
    instances = (await session.execute(select(TaskInstance.task_id, TaskInstance.date, TaskInstance.completed).join(Task,
        (Task.id==TaskInstance.task_id)&(Task.user_id==TaskInstance.user_id)).where(
        TaskInstance.user_id == uid, ((Task.recurrence=='once')&(TaskInstance.date==Task.date))|
            TaskInstance.date.between(day-timedelta(days=1),day),
        TaskInstance.task_id.in_([r.id for r in rows])))).all()
    completed = {(identity, when): value for identity, when, value in instances}
    state = DomainState(domain='tasks', truncated=len(rows) > FIXED_LIMIT)
    unknown_fixed = False
    completed_today=0;eligible_today=0
    for row in rows[:FIXED_LIMIT]:
        occurrence = bool(expand_task_dates({'date':row.date.isoformat(),'recurrence':row.recurrence}, day.isoformat(), day.isoformat()))
        overdue = row.recurrence == 'once' and row.date < day and row.scheduled_time is None
        done = completed.get((row.id, day if occurrence else row.date), False)
        if occurrence:
            eligible_today+=1;completed_today+=int(done)
        if (occurrence or overdue) and not done:
            if row.scheduled_time is not None:
                begin = row.scheduled_time.hour*60+row.scheduled_time.minute
                if row.duration_minutes is None:
                    unknown_fixed = True
                state.constraints.append(Constraint(id=f'tasks:{row.id}:{day}', domain='tasks', title=row.title[:300],
                    start_minute=begin, end_minute=min(1440,begin+(row.duration_minutes or (1440-begin))),
                    reason='Horário fixo registrado.' if row.duration_minutes else 'Duração fixa desconhecida; planejamento suspenso.'))
            elif row.recurrence=='once' and row.id in allocated:
                pass  # Allocation is not completion: retain factual daily totals.
            elif len(state.candidates) < LIMIT:
                c = candidate('tasks',row,day,row.title,row.duration_minutes,'/tasks',priority=row.priority,
                    reasons=['Prioridade informada: '+row.priority, 'Data registrada: '+row.date.isoformat()],latest=row.date)
                state.candidates.append(c)
            else:
                state.truncated = True
        # Reserve the portion of yesterday's fixed task crossing midnight.
        previous = day-timedelta(days=1)
        if row.scheduled_time and row.duration_minutes and bool(expand_task_dates(
            {'date':row.date.isoformat(),'recurrence':row.recurrence},previous.isoformat(),previous.isoformat())):
            overflow = row.scheduled_time.hour*60+row.scheduled_time.minute+row.duration_minutes-1440
            if overflow > 0 and not completed.get((row.id, previous), False):
                state.constraints.append(Constraint(id=f'tasks:{row.id}:{previous}',domain='tasks',title=row.title[:300],
                    start_minute=0,end_minute=overflow,reason='Tarefa fixa iniciada no dia anterior.'))
    state.facts = {'pending_candidates':len(state.candidates),'fixed_occurrences':len(state.constraints),
        'eligible_today':eligible_today,'completed_today':completed_today,'unknown_fixed_duration':unknown_fixed}
    if len(state.constraints)>FIXED_LIMIT:
        state.truncated=True; state.constraints=state.constraints[:FIXED_LIMIT]
    return state


async def calendar(session, uid, day, zone):
    lower = datetime.combine(day,time(),zone); upper = datetime.combine(day+timedelta(days=1),time(),zone)
    rows = (await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id == uid,
        CalendarEvent.start_at < upper, CalendarEvent.end_at > lower).order_by(CalendarEvent.start_at, CalendarEvent.id)
        .limit(FIXED_LIMIT+1))).all()
    state = DomainState(domain='calendar', truncated=len(rows) > FIXED_LIMIT)
    accepted = [];allocations=[]
    for row in rows[:FIXED_LIMIT]:
        begin_utc=max(row.start_at.astimezone(timezone.utc),lower.astimezone(timezone.utc))
        end_utc=min(row.end_at.astimezone(timezone.utc),upper.astimezone(timezone.utc))
        begin,end=begin_utc.astimezone(zone),end_utc.astimezone(zone)
        # Round outward so seconds cannot leak occupied time.
        a = begin.hour*60+begin.minute
        b = 1440 if end == upper else end.hour*60+end.minute+bool(end.second or end.microsecond)
        reason='Alocação já confirmada.' if row.source_type == 'global_plan' else 'Compromisso fixo registrado.'
        elapsed=int((end_utc-begin_utc).total_seconds()/60)
        ambiguous=begin.utcoffset()!=end.utcoffset()
        if ambiguous:
            # Civil-minute windows cannot represent a repeated/skipped hour.
            # Retain the fact conservatively; the coordinator suspends this day.
            a,b=0,1440
            reason=f'Mudança de horário: janela civil conservadora, não duração do evento; {elapsed} min reais. Alocação suspensa.'
        if a < b:
            state.constraints.append(Constraint(id='calendar:'+str(row.id),domain='calendar',title=row.title[:300],
                start_minute=a,end_minute=b,reason=reason,elapsed_minutes=elapsed,civil_time_ambiguous=ambiguous))
        if row.source_type == 'global_plan':
            accepted.append((row.details or {}).get('candidate_id'))
            allocations.append({'event_id':str(row.id),'title':row.title[:300],'start_at':row.start_at.isoformat(),
                'end_at':row.end_at.isoformat()})
    state.facts = {'accepted_candidate_ids':accepted,'commitments':len(state.constraints),'allocations':allocations}
    return state


async def preparation(session, uid, day, zone):
    rows = (await session.execute(select(StudyPlanEntry,StudyPlan.program_id).join(StudyPlan,
        (StudyPlan.id == StudyPlanEntry.plan_id)&(StudyPlan.user_id == StudyPlanEntry.user_id)).join(StudyProgram,
        (StudyProgram.id == StudyPlan.program_id)&(StudyProgram.user_id == StudyPlan.user_id)).join(Notebook,
        (Notebook.id == StudyPlanEntry.notebook_id)&(Notebook.user_id == StudyPlanEntry.user_id))
        .where(StudyPlanEntry.user_id == uid,StudyPlanEntry.date == day,StudyPlanEntry.completed.is_(False),
            StudyProgram.archived_at.is_(None),StudyProgram.status == 'active',Notebook.archived_at.is_(None))
        .order_by(StudyPlanEntry.fixed.desc(),StudyPlanEntry.id).limit(LIMIT+1))).all()
    state = DomainState(domain='preparation',truncated=len(rows)>LIMIT)
    for row,pid in rows[:LIMIT]:
        c=candidate('preparation',row,day,row.name+' · '+row.kind,row.minutes,
            f'/studies?program={pid}&view=cronograma',locked=row.fixed or row.manual,
            reasons=['Bloco canônico do cronograma em '+day.isoformat(),row.reason[:400] or 'Distribuição do plano operacional.'])
        c.scope_id=str(row.notebook_id);state.candidates.append(c)
    schedules = (await session.execute(select(StudySchedule,Notebook.name).join(Notebook,
        (Notebook.id == StudySchedule.notebook_id)&(Notebook.user_id == StudySchedule.user_id)).where(
        StudySchedule.user_id == uid,Notebook.archived_at.is_(None)).order_by(StudySchedule.id).limit(FIXED_LIMIT+1))).all()
    state.truncated |= len(schedules)>FIXED_LIMIT
    labels=('monday','tuesday','wednesday','thursday','friday','saturday','sunday')
    for row,title in schedules[:FIXED_LIMIT]:
        if row.day_of_week != labels[day.weekday()]: continue
        if not row.repeat:
            created=row.created_at.astimezone(zone).date()
            occurrence=created+timedelta(days=(labels.index(row.day_of_week)-created.weekday())%7)
            if occurrence!=day:continue
        a=row.start_time.hour*60+row.start_time.minute; b=row.end_time.hour*60+row.end_time.minute
        if b<=a:
            if not state.warnings:state.warnings.append('Horário de estudo inválido; planejamento suspenso.')
        else:
            state.constraints.append(Constraint(id='schedule:'+str(row.id),domain='preparation',scope_id=str(row.notebook_id),title=title[:300],
                start_minute=a,end_minute=b,reason='Horário recorrente de estudo registrado.'))
    state.facts={'dated_blocks':len(state.candidates),'locked_date_blocks':sum(c.date_locked for c in state.candidates),
        'recorded_minutes_today':await session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes),0)).where(
            StudySession.user_id==uid,StudySession.date==day,StudySession.completed.is_(True)))}
    return state


async def finance(session, uid, day, zone):
    start=day.replace(day=1)
    totals=dict((await session.execute(select(FinancialTransaction.type,func.sum(FinancialTransaction.amount)).where(
        FinancialTransaction.user_id==uid,FinancialTransaction.date.between(start,day)).group_by(FinancialTransaction.type))).all())
    bills=(await session.execute(select(func.count(),func.coalesce(func.sum(MonthlyBill.amount),0)).where(
        MonthlyBill.user_id==uid,MonthlyBill.month==start,MonthlyBill.paid.is_(False)))).one()
    budgets=await session.scalar(select(func.count()).select_from(Budget).where(Budget.user_id==uid,Budget.month==start))
    income,expense=(totals.get(k,Decimal('0.00')) for k in ('income','expense'))
    state=DomainState(domain='finance',facts={'period_start':str(start),'period_end':str(day),'income':str(income),
        'expense':str(expense),'recorded_net':str(income-expense),'unpaid_monthly_bills':bills[0],
        'unpaid_monthly_amount':str(bills[1]),'budgets':budgets,'due_day_known':False},
        warnings=['Contas mensais sem vencimento diário não viram urgência inventada.'])
    first=await session.scalar(select(MonthlyBill).where(MonthlyBill.user_id==uid,MonthlyBill.month==start,
        MonthlyBill.paid.is_(False)).order_by(MonthlyBill.id).limit(1))
    if first:
        state.candidates.append(candidate('finance',first,day,'Revisar contas pendentes do mês',None,'/finance',priority='low',
            reasons=[f'{bills[0]} conta(s) não paga(s) registrada(s) no mês. Vencimento diário desconhecido.']))
    return state


async def training(session, uid, day, zone, *, now=None):
    active=(await session.execute(select(WorkoutSession,WorkoutPlan).join(WorkoutPlan,
        (WorkoutPlan.id==WorkoutSession.plan_id)&(WorkoutPlan.user_id==WorkoutSession.user_id)).where(
        WorkoutSession.user_id==uid,WorkoutSession.status=='active',WorkoutPlan.archived_at.is_(None)).limit(1))).first()
    count,minutes=(await session.execute(select(func.count(),func.coalesce(func.sum(WorkoutLog.duration_minutes),0)).where(
        WorkoutLog.user_id==uid,WorkoutLog.date==day,WorkoutLog.completed.is_(True)))).one()
    plans=(await session.scalars(select(WorkoutPlan).where(WorkoutPlan.user_id==uid,WorkoutPlan.archived_at.is_(None))
        .order_by(WorkoutPlan.id).limit(LIMIT+1))).all()
    state=DomainState(domain='training',truncated=len(plans)>LIMIT,facts={'completed_today':count,'recorded_minutes_today':minutes,
        'active_session':str(active[0].id) if active else None,'available_plans':[{'id':str(p.id),'name':p.name[:200]} for p in plans[:LIMIT]]})
    if active and day==(now or datetime.now(timezone.utc)).astimezone(zone).date():
        state.candidates.append(candidate('training',active[1],day,'Retomar '+active[1].name,None,'/workouts',
            reasons=['Sessão ativa real. Duração restante precisa da sua estimativa.']))
    elif not active and count==0:
        for p in plans[:LIMIT]:
            state.candidates.append(candidate('training',p,day,'Treino: '+p.name,None,'/workouts',
                reasons=['Plano cadastrado; inclusão no dia exige sua seleção e estimativa de duração.']))
    elif active:
        state.warnings.append('Uma sessão de treino ativa só é sugerida para hoje, sem duplicação em dias futuros.')
    return state


async def nutrition(session, uid, day, zone):
    meals,water,goals=await period(session,uid,day,day)
    state=DomainState(domain='nutrition',facts={'consumed':meals.get(day,{}),'water_ml':water.get(day,0),
        'targets':{k:v for k,v in goals.items() if k.startswith('daily_') or k=='water_goal_ml'},
        'target_origin':'recorded' if goals.get('goal_id') else 'existing_default'},
        warnings=['Metas nutricionais não definem horário nem necessidade clínica.'])
    if goals.get('goal_id') and not meals.get(day):
        state.candidates.append(candidate('nutrition',SimpleNamespace(id=UUID(goals['goal_id'])),day,
            'Conferir registros de alimentação',None,'/nutrition',priority='low',
            reasons=['Meta nutricional cadastrada e nenhuma refeição registrada na data. Não é orientação clínica.']))
    return state


async def habits(session, uid, day, zone):
    rows=(await session.execute(select(Habit,HabitCheck.id).outerjoin(HabitCheck,
        (HabitCheck.habit_id==Habit.id)&(HabitCheck.user_id==Habit.user_id)&(HabitCheck.date==day)).where(
        Habit.user_id==uid,Habit.archived_at.is_(None)).order_by(Habit.id).limit(LIMIT+1))).all()
    state=DomainState(domain='habits',truncated=len(rows)>LIMIT,facts={'recorded':min(len(rows),LIMIT),
        'completed_today':sum(check is not None for _,check in rows[:LIMIT])})
    for row,check in rows[:LIMIT]:
        if check is None:
            state.candidates.append(candidate('habits',row,day,row.name,None,'/habits',priority='low',
                reasons=['Hábito cadastrado ainda não marcado hoje; duração não cadastrada.']))
    return state


async def goals(session, uid, day, zone):
    rows=(await session.scalars(select(Goal).where(Goal.user_id==uid,Goal.archived_at.is_(None),Goal.progress<100)
        .order_by(Goal.target_date,Goal.id).limit(LIMIT+1))).all()
    state=DomainState(domain='goals',truncated=len(rows)>LIMIT,facts={'items':[{'id':str(r.id),'title':r.title[:200],
        'target_date':str(r.target_date),'progress':r.progress} for r in rows[:LIMIT]]},
        warnings=['Revisar uma meta é uma proposta; não representa progresso nem sua próxima ação operacional.'])
    for row in rows[:LIMIT]:
        state.candidates.append(candidate('goals',row,day,'Revisar meta: '+row.title,None,'/goals',priority='low',latest=row.target_date,
            reasons=['Meta cadastrada com progresso '+str(row.progress)+'%. A revisão exige duração informada.']))
    return state


ADAPTERS=(tasks,calendar,preparation,finance,training,nutrition,habits,goals)
