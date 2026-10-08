from db.study_attempts import answered_attempt
"""Owned lesson lookup and batched study history from normalized facts."""
import os
from collections import defaultdict
from datetime import datetime,time,timedelta,timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request,Query
from sqlalchemy import select,func,Date
from db.models.studies import Notebook,StudyProgram,StudySession,QuestionAttempt
from db.session import unit_of_work
from services.auth_routes import account
from services.studies_catalog import owned
from services.time import local_today
from study_resources import youtube_lessons

router=APIRouter(prefix='/study')


@router.get('/notebooks/{notebook_id}/lessons')
async def lessons(request: Request,notebook_id: UUID,topic: str=Query('',max_length=300)):
    user=await account(request)
    async with unit_of_work() as session:
        book=await owned(session,Notebook,UUID(user['user_id']),notebook_id)
        query=' '.join(f'{book.name} {topic} aula concurso'.split())[:400]
    return await youtube_lessons(query,os.environ.get('YOUTUBE_API_KEY',''))


@router.get('/programs/{program_id}/progress-history')
async def history(request: Request,program_id: UUID,days: int=Query(30,ge=1,le=366)):
    user=await account(request); uid=UUID(user['user_id']); zone=ZoneInfo(user['timezone'])
    today=local_today(user['timezone']); start=today-timedelta(days=days-1)
    lower=datetime.combine(start,time.min,zone).astimezone(timezone.utc)
    upper=datetime.combine(today+timedelta(days=1),time.min,zone).astimezone(timezone.utc)
    async with unit_of_work() as session:
        await owned(session,StudyProgram,uid,program_id)
        books=(await session.scalars(select(Notebook).where(Notebook.user_id==uid,Notebook.program_id==program_id,
            Notebook.archived_at.is_(None)).order_by(Notebook.created_at,Notebook.id))).all()
        ids=[b.id for b in books]
        day=func.timezone(user['timezone'],QuestionAttempt.answered_at).cast(Date)
        questions=(await session.execute(select(day,QuestionAttempt.notebook_id,func.sum(QuestionAttempt.total),func.sum(QuestionAttempt.correct))
            .where(QuestionAttempt.user_id==uid,QuestionAttempt.notebook_id.in_(ids),QuestionAttempt.answered_at>=lower,
                QuestionAttempt.answered_at<upper,answered_attempt()).group_by(day,QuestionAttempt.notebook_id))).all()
        minutes=(await session.execute(select(StudySession.date,StudySession.notebook_id,func.sum(StudySession.duration_minutes))
            .where(StudySession.user_id==uid,StudySession.notebook_id.in_(ids),StudySession.completed.is_(True),
                StudySession.date>=start,StudySession.date<=today).group_by(StudySession.date,StudySession.notebook_id))).all()
        # The existing chart contract uses discipline names as series keys.
        names={b.id:b.name for b in books}; by_day=defaultdict(lambda:defaultdict(lambda:[0,0,0]))
        for d,nid,total,correct in questions:
            value=by_day[d][names[nid]]; value[0]+=total; value[1]+=correct
        for d,nid,total in minutes: by_day[d][names[nid]][2]+=total
        cumulative=defaultdict(lambda:[0,0,0]); chart=[]
        for d,values in sorted(by_day.items()):
            item={'date':d.isoformat()}
            for name in dict.fromkeys(names.values()):
                value=values.get(name,[0,0,0]); acc=cumulative[name]
                for index in range(3): acc[index]+=value[index]
                item.update({f'{name}_questoes':acc[0],f'{name}_acerto':round(acc[1]/acc[0]*100,1) if acc[0] else 0,
                    f'{name}_horas':round(acc[2]/60,1)})
            chart.append(item)
        return {'program_id':str(program_id),'history':chart,'notebooks':[{'name':b.name,'color':b.color,'weight':b.weight} for b in books],'days':days}
