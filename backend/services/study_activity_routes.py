from datetime import date as Date,datetime,timezone,timedelta
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,Field,StrictBool
from sqlalchemy import select,func,Date as SQLDate
from db.activity import run_activity
from db.session import unit_of_work
from db.models.studies import Notebook,StudySession,QuestionAttempt,StudyTopic,TopicProgress,ReviewEvent,FlashcardReview,StudyTaskCheck
from db.repositories.studies import StudiesRepository
from services.auth_routes import account
from services.studies_catalog import owned
from services.time import local_today
from services.planning import apply_xp,streaks
from services.core_writes import CoreWrites

router=APIRouter(prefix='/study')


class FocusBody(BaseModel):
    notebook_id: UUID | None = None
    focus_minutes: int = Field(default=25,ge=1,le=120)
    break_minutes: int = Field(default=5,ge=1,le=30)
    notes: str | None = Field(default=None,max_length=110000)


class SessionBody(BaseModel):
    notebook_id: UUID
    duration_minutes: int = Field(ge=1,le=720)
    date: Date
    notes: str | None = Field(default=None,max_length=2000)


class QuestionsBody(BaseModel):
    notebook_id: UUID
    total: int = Field(ge=1,le=10000)
    correct: int = Field(ge=0,le=10000)
    source: str = Field(default='manual',min_length=1,max_length=100)


class ProgressBody(BaseModel):
    topic_key: str = Field(pattern=r'^\d+(?:_\d+)?$')
    status: Literal['studied','reviewed','mastered'] = 'studied'
    checked: StrictBool = True


async def mutate(request,fingerprint,apply):
    user=await account(request)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),fingerprint,apply)


@router.post('/focus/complete')
async def focus_complete(request: Request,body: FocusBody):
    async def apply(session,user):
        if body.notebook_id: await owned(session,Notebook,user.id,body.notebook_id)
        xp=max(3,body.focus_minutes//25*5)
        row=StudySession(user_id=user.id,notebook_id=body.notebook_id,date=local_today(user.timezone),
            duration_minutes=body.focus_minutes,break_minutes=body.break_minutes,source='focus',notes=body.notes,
            completed=True,completed_at=datetime.now(timezone.utc),xp_earned=xp)
        session.add(row); apply_xp(user,xp); await session.flush()
        return {'focus_id':str(row.id),'user_id':str(user.id),'notebook_id':str(body.notebook_id) if body.notebook_id else None,
            'date':row.date.isoformat(),'focus_minutes':body.focus_minutes,'break_minutes':body.break_minutes,
            'completed':True,'notes':body.notes,'xp_earned':xp,'new_xp':user.xp,'new_rank':user.rank,'created_at':row.created_at.isoformat()}
    return await mutate(request,['focus',body.model_dump(mode='json')],apply)


@router.get('/focus/stats')
async def focus_stats(request: Request):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        counts=select(func.count(),func.coalesce(func.sum(StudySession.duration_minutes),0),func.coalesce(func.sum(StudySession.xp_earned),0))
        counts=counts.where(StudySession.user_id==uid,StudySession.source=='focus',StudySession.completed.is_(True))
        total=(await session.execute(counts)).one()
        current=(await session.execute(counts.where(StudySession.date==today))).one()
        days=(await session.execute(select(StudySession.date,func.count(),func.sum(StudySession.duration_minutes))
            .where(StudySession.user_id==uid,StudySession.source=='focus',StudySession.completed.is_(True),
                StudySession.date.between(today-timedelta(days=6),today)).group_by(StudySession.date))).all()
    return {'today':dict(zip(('sessions','total_minutes','xp_earned'),current)),
        'week':{'sessions':sum(row[1] for row in days),'total_minutes':sum(row[2] for row in days),'daily_minutes':{row[0].isoformat():row[2] for row in days}},
        'all_time':{'sessions':total[0],'total_minutes':total[1],'total_hours':round(total[1]/60,1)}}


@router.post('/sessions')
async def session_create(request: Request,body: SessionBody):
    args=body.model_dump(mode='json'); args['notes']=args['notes'] or ''
    async def apply(session,user):
        result=await CoreWrites().execute('record_study_session',user,args,session)
        return {**result,'new_xp':user.xp,'new_rank':user.rank}
    return await mutate(request,['study_session',args],apply)


@router.get('/sessions')
async def sessions(request: Request,notebook_id: UUID | None = None,date: Date | None = None):
    user=await account(request); uid=UUID(user['user_id'])
    query=select(StudySession).where(StudySession.user_id==uid)
    if notebook_id: query=query.where(StudySession.notebook_id==notebook_id)
    if date: query=query.where(StudySession.date==date)
    async with unit_of_work() as session:
        rows=(await session.scalars(query.order_by(StudySession.date.desc(),StudySession.id))).all()
        return [{'session_id':str(row.id),'user_id':str(uid),'notebook_id':str(row.notebook_id) if row.notebook_id else None,
            'date':row.date.isoformat(),'duration_minutes':row.duration_minutes,'notes':row.notes,'xp_earned':row.xp_earned,
            'completed':row.completed,'source':row.source,'created_at':row.created_at.isoformat()} for row in rows]


@router.post('/questions/log')
async def questions_log(request: Request,body: QuestionsBody):
    if body.correct>body.total: raise HTTPException(422,'Acertos não podem superar o total.')
    async def apply(session,user):
        notebook=await owned(session,Notebook,user.id,body.notebook_id)
        row=await StudiesRepository(session).add_attempt(user.id,notebook_id=body.notebook_id,total=body.total,correct=body.correct,
            source=body.source,answered_at=datetime.now(timezone.utc))
        apply_xp(user,body.correct)
        return {'log_id':str(row.id),'user_id':str(user.id),'notebook_id':str(notebook.id),
            'program_id':str(notebook.program_id) if notebook.program_id else None,'total':body.total,'correct':body.correct,
            'incorrect':body.total-body.correct,'source':body.source,'date':local_today(user.timezone).isoformat(),
            'created_at':row.created_at.isoformat(),'xp_earned':body.correct,'new_xp':user.xp}
    return await mutate(request,['question_log',body.model_dump(mode='json')],apply)


@router.get('/questions/stats')
async def question_stats(request: Request,notebook_id: UUID | None = None,program_id: UUID | None = None):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    conditions=[QuestionAttempt.user_id==uid]
    if notebook_id: conditions.append(QuestionAttempt.notebook_id==notebook_id)
    if program_id: conditions.append(QuestionAttempt.notebook_id.in_(select(Notebook.id).where(Notebook.user_id==uid,Notebook.program_id==program_id)))
    total=func.coalesce(func.sum(QuestionAttempt.total),0); correct=func.coalesce(func.sum(QuestionAttempt.correct),0)
    day=func.timezone(user['timezone'],QuestionAttempt.answered_at).cast(SQLDate)
    async with unit_of_work() as session:
        totals=(await session.execute(select(total,correct).where(*conditions))).one()
        daily=(await session.execute(select(day,total,correct).where(*conditions,day.between(today-timedelta(days=29),today)).group_by(day))).all()
        grouped=(await session.execute(select(QuestionAttempt.notebook_id,total,correct).where(*conditions).group_by(QuestionAttempt.notebook_id))).all()
    def values(t,c): return {'total':t,'correct':c,'incorrect':t-c}
    return {'total_questions':totals[0],'correct':totals[1],'incorrect':totals[0]-totals[1],
        'accuracy':round(totals[1]/totals[0]*100,1) if totals[0] else 0,
        'daily_stats':{d.isoformat():values(t,c) for d,t,c in daily},
        'by_notebook':{str(n) if n else '':values(t,c) for n,t,c in grouped}}


async def progress_data(session,uid,notebook_id):
    rows=(await session.execute(select(StudyTopic.topic_key,TopicProgress).join(TopicProgress,
        (TopicProgress.topic_id==StudyTopic.id)&(TopicProgress.user_id==StudyTopic.user_id))
        .where(StudyTopic.user_id==uid,StudyTopic.notebook_id==notebook_id,StudyTopic.archived_at.is_(None)))).all()
    return {'notebook_id':str(notebook_id),'user_id':str(uid),'topics':{
        key:{name:True for name,value in (('studied',row.studied),('reviewed',row.reviewed),('mastered',row.confident)) if value}
        for key,row in rows}}


@router.get('/notebooks/{notebook_id}/topic-progress')
async def progress(request: Request,notebook_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await owned(session,Notebook,uid,notebook_id)
        return await progress_data(session,uid,notebook_id)


@router.post('/notebooks/{notebook_id}/topic-progress')
async def progress_update(request: Request,notebook_id: UUID,body: ProgressBody):
    async def apply(session,user):
        await owned(session,Notebook,user.id,notebook_id)
        topic=await StudiesRepository(session).topic(user.id,notebook_id,body.topic_key)
        if topic is None: raise HTTPException(422,'Assunto não encontrado no conteúdo da disciplina.')
        row=await session.scalar(select(TopicProgress).where(TopicProgress.user_id==user.id,TopicProgress.topic_id==topic.id))
        if row is None: row=TopicProgress(user_id=user.id,topic_id=topic.id); session.add(row)
        setattr(row,'confident' if body.status=='mastered' else body.status,body.checked)
        await session.flush()
        return await progress_data(session,user.id,notebook_id)
    return await mutate(request,['topic_progress',str(notebook_id),body.model_dump()],apply)


@router.get('/streak')
async def study_streak(request: Request):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        return await streak_summary(session,uid,user['timezone'])


async def streak_summary(session,uid,zone):
    today=local_today(zone)
    days=select(StudySession.date.label('day')).where(StudySession.user_id==uid,StudySession.completed.is_(True))
    other=[select(StudyTaskCheck.date.label('day')).where(StudyTaskCheck.user_id==uid)]
    for model,column in ((QuestionAttempt,QuestionAttempt.answered_at),(ReviewEvent,ReviewEvent.reviewed_at),(FlashcardReview,FlashcardReview.reviewed_at)):
        other.append(select(func.timezone(zone,column).cast(SQLDate).label('day')).where(model.user_id==uid))
    union=days.union(*other).subquery()
    dates=(await session.scalars(select(union.c.day).where(union.c.day<=today).order_by(union.c.day))).all()
    current,best=streaks(dates,today)
    return {'current_streak':current,'best_streak':best,'total_study_days':len(dates),'last_study_date':dates[-1].isoformat() if dates else None}
