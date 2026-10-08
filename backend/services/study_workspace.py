from db.study_attempts import answered_attempt
from datetime import date,datetime,time,timedelta,timezone
from collections import defaultdict
from uuid import UUID,uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request,Query,HTTPException
from sqlalchemy import select,func,delete
from db.session import unit_of_work
from db.models.studies import Notebook,StudyProgram,StudyTopic,StudyDraft,StudyPlan,StudyPlanEntry,QuestionAttempt,ReviewEvent,StudyTask,StudyTaskCheck
from db.models.planning import CalendarEvent
from db.repositories.studies import StudiesRepository
from services.studies_catalog import owned,notebooks as catalog_notebooks
from services.auth_routes import account
from services.study_activity_routes import mutate
from services.time import local_today
from study_workspace_routes import DraftUpdate,PlanSettings,TopicPractice,PlanEntryUpdate,StrategyScenario
from study_planner import build_plan,build_strategy_plan
from adaptive_strategy import strategy_summary,preview_strategy
from services.preparation_state import preparation_state
from study_adaptation import next_review
from services.study_plan_views import entry_json

router=APIRouter(prefix='/study')


def draft_json(row):
    return {'user_id':str(row.user_id),'notebook_id':str(row.notebook_id),'topic_key':row.topic_key,
        'text':row.text,'revision':row.revision,'updated_at':row.updated_at.isoformat()}


@router.get('/notebooks/{notebook_id}/draft')
async def draft_get(request: Request,notebook_id: UUID,topic_key: str = Query('general',pattern=r'^(general|\d+(?:_\d+)?)$')):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await owned(session,Notebook,uid,notebook_id)
        row=await session.scalar(select(StudyDraft).where(StudyDraft.user_id==uid,StudyDraft.notebook_id==notebook_id,StudyDraft.topic_key==topic_key))
        return draft_json(row) if row else {'text':'','revision':0}


@router.put('/notebooks/{notebook_id}/draft')
async def draft_save(request: Request,notebook_id: UUID,body: DraftUpdate,topic_key: str = Query('general',pattern=r'^(general|\d+(?:_\d+)?)$')):
    async def apply(session,user):
        await owned(session,Notebook,user.id,notebook_id)
        row=await session.scalar(select(StudyDraft).where(StudyDraft.user_id==user.id,StudyDraft.notebook_id==notebook_id,StudyDraft.topic_key==topic_key))
        if row is None and body.revision==0:
            row=StudyDraft(user_id=user.id,notebook_id=notebook_id,topic_key=topic_key,text=body.text,revision=1); session.add(row)
        elif row and row.revision==body.revision:
            row.text=body.text; row.revision+=1
        elif row and row.text==body.text: return draft_json(row)
        else: raise HTTPException(409,'Esta anotação foi alterada em outra sessão. Recarregue antes de substituir.')
        await session.flush(); await session.refresh(row)
        return draft_json(row)
    return await mutate(request,['draft',str(notebook_id),topic_key,body.model_dump()],apply)


@router.get('/notebooks/{notebook_id}/learning-summary')
async def learning_summary(request: Request,notebook_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await owned(session,Notebook,uid,notebook_id)
        total,correct=(await session.execute(select(func.coalesce(func.sum(QuestionAttempt.total),0),func.coalesce(func.sum(QuestionAttempt.correct),0))
            .where(QuestionAttempt.user_id==uid,QuestionAttempt.notebook_id==notebook_id,answered_attempt()))).one()
    return {'answered':total,'correct':correct,'accuracy':round(correct/total*100,1) if total else None}


@router.post('/notebooks/{notebook_id}/practice')
async def practice(request: Request,notebook_id: UUID,body: TopicPractice):
    if body.correct>body.total: raise HTTPException(422,'Acertos não podem superar o total.')
    if not request.headers.get('Idempotency-Key'): raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        notebook=await owned(session,Notebook,user.id,notebook_id)
        repo=StudiesRepository(session); topic=await repo.topic(user.id,notebook_id,body.topic_key)
        if not topic: raise HTTPException(422,'Assunto não encontrado no conteúdo da disciplina.')
        today=local_today(user.timezone); due=date.fromisoformat(next_review(today.isoformat(),body.total,body.correct))
        attempt=await repo.add_attempt(user.id,notebook_id=notebook_id,topic_id=topic.id,total=body.total,correct=body.correct,
            source='topic_practice',answered_at=datetime.now(timezone.utc))
        await repo.add_review(user.id,topic.id,'practice',due)
        return {'user_id':str(user.id),'notebook_id':str(notebook_id),'program_id':str(notebook.program_id) if notebook.program_id else None,
            'topic_key':body.topic_key,'title':topic.name,'total':body.total,'correct':body.correct,'incorrect':body.total-body.correct,
            'date':today.isoformat(),'source':'topic_practice','created_at':attempt.created_at.isoformat(),'due_date':due.isoformat(),
            'accuracy':round(body.correct/body.total*100,1)}
    return await mutate(request,['topic-practice',str(notebook_id),body.model_dump()],apply)


@router.get('/notebooks/{notebook_id}/reviews')
async def reviews(request: Request,notebook_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        notebook=await owned(session,Notebook,uid,notebook_id)
        latest=select(ReviewEvent).where(ReviewEvent.user_id==uid).distinct(ReviewEvent.topic_id).order_by(ReviewEvent.topic_id,ReviewEvent.reviewed_at.desc(),ReviewEvent.id.desc()).subquery()
        attempts=select(QuestionAttempt).where(QuestionAttempt.user_id==uid,QuestionAttempt.notebook_id==notebook_id,answered_attempt()).distinct(QuestionAttempt.topic_id)
        attempts=attempts.order_by(QuestionAttempt.topic_id,QuestionAttempt.answered_at.desc(),QuestionAttempt.id.desc()).subquery()
        rows=(await session.execute(select(StudyTopic.topic_key,StudyTopic.name,latest.c.next_review,latest.c.reviewed_at,attempts.c.total,attempts.c.correct)
            .join(latest,(latest.c.topic_id==StudyTopic.id)&(latest.c.user_id==StudyTopic.user_id))
            .outerjoin(attempts,(attempts.c.topic_id==StudyTopic.id)&(attempts.c.user_id==StudyTopic.user_id))
            .where(StudyTopic.user_id==uid,StudyTopic.notebook_id==notebook_id,StudyTopic.archived_at.is_(None)).order_by(latest.c.next_review))).all()
        return [{'user_id':str(uid),'notebook_id':str(notebook_id),'program_id':str(notebook.program_id) if notebook.program_id else None,
            'topic_key':key,'title':name,'due_date':due.isoformat() if due else None,
            'created_at':stamp.isoformat(),'total':total or 0,'correct':correct or 0,'incorrect':(total or 0)-(correct or 0),
            'accuracy':round(correct/total*100,1) if total else 0} for key,name,due,stamp,total,correct in rows]


async def plan_rows(session,uid,program_id):
    plan=await session.scalar(select(StudyPlan).where(StudyPlan.user_id==uid,StudyPlan.program_id==program_id))
    entries=[] if plan is None else list((await session.scalars(select(StudyPlanEntry).where(StudyPlanEntry.user_id==uid,StudyPlanEntry.plan_id==plan.id)
        .order_by(StudyPlanEntry.date,StudyPlanEntry.id))).all())
    topics = {t.id:t for t in (await session.scalars(select(StudyTopic).where(StudyTopic.user_id==uid,
        StudyTopic.id.in_(sorted({e.topic_id for e in entries if e.topic_id})),StudyTopic.archived_at.is_(None)))).all()}
    for entry in entries:
        topic=topics.get(entry.topic_id)
        entry.strategy_topic_key=topic.topic_key if topic and topic.notebook_id==entry.notebook_id else None
    return plan,entries


def plan_json(plan,entries):
    if plan is None: return {'entries':[],'settings':None}
    return {'user_id':str(plan.user_id),'program_id':str(plan.program_id),'settings':{'start_date':plan.start_date.isoformat(),
        'end_date':plan.end_date.isoformat(),'availability':plan.availability,'block_minutes':plan.block_minutes,'adaptive':plan.adaptive},
        'entries':[entry_json(row) for row in entries],'updated_at':plan.updated_at.isoformat()}


async def reserved_minutes(session,user,start,end):
    zone=ZoneInfo(user.timezone)
    first=datetime.combine(start,time(),zone); last=datetime.combine(end+timedelta(days=1),time(),zone)
    events=(await session.scalars(select(CalendarEvent).where(CalendarEvent.user_id==user.id,CalendarEvent.start_at<last,CalendarEvent.end_at>first))).all()
    result=defaultdict(int)
    for row in events:
        cursor=max(first,row.start_at.astimezone(zone)); finish=min(last,row.end_at.astimezone(zone))
        while cursor<finish:
            boundary=min(finish,datetime.combine(cursor.date()+timedelta(days=1),time(),zone))
            result[cursor.date().isoformat()]+=max(0,int((boundary-cursor).total_seconds()/60)); cursor=boundary
    return dict(result)


async def strategy_state(session,uid,program,zone,today):
    state=await preparation_state(session,uid,program,zone,today)
    ids=[UUID(d['id']) for d in state['syllabus_graph']['disciplines']]
    checked=select(StudyTaskCheck.id).where(StudyTaskCheck.user_id==uid,StudyTaskCheck.task_id==StudyTask.id).exists()
    tasks=list((await session.scalars(select(StudyTask).where(StudyTask.user_id==uid,
        StudyTask.notebook_id.in_(ids),StudyTask.archived_at.is_(None),StudyTask.recurrence=='once',
        StudyTask.deadline<today,~checked).order_by(StudyTask.deadline,StudyTask.id).limit(501))).all())
    state['strategy_facts']['late_milestones']=[{'task_id':str(t.id),'title':t.title,
        'deadline':t.deadline.isoformat(),'notebook_id':str(t.notebook_id)} for t in tasks[:500]]
    state['truncated'] |= len(tasks)>500
    return state


def validate_scenario(body,today,exam_date=None):
    if any(m<0 or m>720 for m in body.availability) or not any(m>=15 for m in body.availability):
        raise HTTPException(422,'Informe de 15 a 720 minutos em pelo menos um dia.')
    if body.start_date<today or not 0<=(body.end_date-body.start_date).days<=180:
        raise HTTPException(422,'Simule um período futuro de até 181 dias.')
    if exam_date and body.end_date>date.fromisoformat(exam_date):
        raise HTTPException(422,'A simulação deve terminar até a data da prova/meta.')


@router.get('/programs/{program_id}/strategy')
async def strategy_get(request: Request,program_id: UUID):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        program=await owned(session,StudyProgram,uid,program_id)
        state=await strategy_state(session,uid,program,user['timezone'],today)
        plan,previous=await plan_rows(session,uid,program_id)
        end=today+timedelta(days=27)
        if state['exam_date']: end=min(end,date.fromisoformat(state['exam_date']))
        body=StrategyScenario(start_date=today,end_date=end,availability=plan.availability if plan else [60]*5+[0,0],
            block_minutes=plan.block_minutes if plan else 50,adaptive=True)
        reserved=await reserved_minutes(session,SimpleUser(uid,user['timezone']),today,end) if end>=today else {}
        return preview_strategy(state,today,body,[entry_json(e) for e in previous],reserved)


class SimpleUser:
    def __init__(self,uid,zone): self.id=uid; self.timezone=zone


@router.post('/programs/{program_id}/strategy/simulate')
async def strategy_simulate(request: Request,program_id: UUID,body: StrategyScenario):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        program=await owned(session,StudyProgram,uid,program_id)
        state=await strategy_state(session,uid,program,user['timezone'],today)
        validate_scenario(body,today,state['exam_date'])
        _,previous=await plan_rows(session,uid,program_id)
        reserved=await reserved_minutes(session,SimpleUser(uid,user['timezone']),body.start_date,body.end_date)
        return preview_strategy(state,today,body,[entry_json(e) for e in previous],reserved,body.missed_days)


@router.get('/programs/{program_id}/dated-plan')
async def plan_get(request: Request,program_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await owned(session,StudyProgram,uid,program_id)
        return plan_json(*(await plan_rows(session,uid,program_id)))


@router.post('/programs/{program_id}/dated-plan')
async def plan_create(request: Request,program_id: UUID,body: PlanSettings):
    if any(value<0 or value>720 for value in body.availability) or not any(value>=15 for value in body.availability):
        raise HTTPException(422,'Informe de 15 a 720 minutos em pelo menos um dia.')
    if not 0<=(body.end_date-body.start_date).days<=180: raise HTTPException(422,'Escolha um período de até 181 dias.')
    async def apply(session,user):
        program=await owned(session,StudyProgram,user.id,program_id)
        if program.target_date and body.end_date>program.target_date: raise HTTPException(422,'O cronograma deve terminar até a data da prova/meta.')
        notebooks=await catalog_notebooks(session,user.id,program_id=program_id)
        if not notebooks: raise HTTPException(422,'Adicione disciplinas antes de planejar.')
        plan,previous=await plan_rows(session,user.id,program_id)
        today=local_today(user.timezone)
        preserved=[row for row in previous if row.completed or row.manual or row.fixed or row.date>body.end_date or
            (row.date<max(today,body.start_date) and not (body.adaptive and body.recovery and today-timedelta(days=27)<=row.date<today))]
        if body.adaptive:
            state=await strategy_state(session,user.id,program,user.timezone,today)
            if state['exam_date'] and body.end_date>date.fromisoformat(state['exam_date']):
                raise HTTPException(422,'O cronograma deve terminar até a data da prova/meta.')
            candidates=strategy_summary(state,today)['candidates']
        reserved=await reserved_minutes(session,user,body.start_date,body.end_date)
        generated=(build_strategy_plan(str(program_id),candidates,body.availability,max(today,body.start_date).isoformat(),
            body.end_date.isoformat(),body.block_minutes,[entry_json(row) for row in preserved],reserved) if body.adaptive else
            build_plan(str(program_id),notebooks,body.availability,max(today,body.start_date).isoformat(),
            body.end_date.isoformat(),body.block_minutes,[entry_json(row) for row in preserved],reserved))
        values=body.model_dump(exclude={'recovery'})
        if plan is None: plan=StudyPlan(user_id=user.id,program_id=program_id,**values); session.add(plan)
        else:
            for key,value in values.items(): setattr(plan,key,value)
        await session.flush()
        keep={str(row.id) for row in preserved}
        for row in previous:
            if str(row.id) not in keep: await session.delete(row)
        entries=list(preserved)
        for values in generated:
            if values['entry_id'] in keep: continue
            row=StudyPlanEntry(user_id=user.id,plan_id=plan.id,notebook_id=UUID(values['notebook_id']),date=date.fromisoformat(values['date']),
                topic_id=UUID(values['topic_id']) if values.get('topic_id') else None,
                name=values['name'],minutes=values['minutes'],kind=values['kind'],reason=values.get('reason',''))
            row.strategy_topic_key=values.get('topic_key')
            session.add(row); entries.append(row)
        await session.flush(); await session.refresh(plan)
        return plan_json(plan,sorted(entries,key=lambda row:(row.date,str(row.id))))
    return await mutate(request,['dated-plan',str(program_id),body.model_dump(mode='json')],apply)


@router.patch('/programs/{program_id}/dated-plan/{entry_id}')
async def entry_update(request: Request,program_id: UUID,entry_id: UUID,body: PlanEntryUpdate):
    async def apply(session,user):
        await owned(session,StudyProgram,user.id,program_id)
        plan,entries=await plan_rows(session,user.id,program_id)
        row=next((row for row in entries if row.id==entry_id),None)
        if row is None: raise HTTPException(404,'Bloco não encontrado')
        if body.date:
            if row.completed: raise HTTPException(409,'O histórico concluído não pode ser remarcado.')
            if not plan.start_date<=body.date<=plan.end_date: raise HTTPException(422,'Data fora do período planejado.')
            occupied=sum(entry.minutes for entry in entries if entry.date==body.date and entry.id!=row.id)
            reserved=await reserved_minutes(session,user,body.date,body.date)
            if occupied+reserved.get(body.date.isoformat(),0)+row.minutes>plan.availability[body.date.weekday()]:
                raise HTTPException(422,'Este dia não tem tempo disponível para o bloco.')
            row.date=body.date; row.manual=True
        if body.completed is not None: row.completed=body.completed
        return entry_json(row)
    return await mutate(request,['dated-entry',str(program_id),str(entry_id),body.model_dump(mode='json')],apply)
