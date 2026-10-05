"""Owned scheduled notifications; atomic local-date delivery claims."""
from datetime import datetime,time,timedelta,timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,HTTPException,Request,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,or_,exists
from db.session import unit_of_work
from db.models.notifications import Notification,NotificationDelivery
from db.models.studies import StudyProgram,StudySchedule,Notebook
from db.repositories.identity import IdentityRepository
from services.auth_routes import account

router=APIRouter()
DAYS=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
Channel=Literal['in_app','browser','email','whatsapp','telegram']


class NotificationInput(BaseModel):
    title: str = Field(min_length=1,max_length=300)
    message: str = Field(max_length=10000)
    type: Literal['reminder','achievement','alert','system'] = 'reminder'
    category: str = Field(default='custom',max_length=100)
    scheduled_time: str | None = None
    repeat: Literal['none','daily','weekly','custom'] = 'none'
    repeat_days: list[Literal['monday','tuesday','wednesday','thursday','friday','saturday','sunday']] = Field(default_factory=list,max_length=7)
    channels: list[Channel] = Field(default_factory=lambda:['in_app'],max_length=5)

    @field_validator('scheduled_time')
    @classmethod
    def valid_time(cls,value):
        if value is not None:
            import re
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):raise ValueError('Use HH:MM')
        return value

    def values(self):
        data=self.model_dump();data['scheduled_time']=time.fromisoformat(self.scheduled_time) if self.scheduled_time else None
        data['repeat_days']=list(dict.fromkeys(self.repeat_days));data['channels']=list(dict.fromkeys(self.channels))
        return data


class RemindersInput(BaseModel):
    minutes_before: int = Field(default=5,ge=0,le=1440)
    include_end_reminder: bool = False


def utc_now():return datetime.now(timezone.utc)


def uid_value(value):
    try:return UUID(str(value))
    except (ValueError,TypeError):raise HTTPException(404,'Notification not found')


def public(row):
    return {'notification_id':str(row.id),'user_id':str(row.user_id),'title':row.title,'message':row.message,
        'type':row.type,'category':row.category,'scheduled_time':row.scheduled_time.strftime('%H:%M') if row.scheduled_time else None,
        'repeat':row.repeat,'repeat_days':row.repeat_days,'enabled':row.enabled,'channels':row.channels,
        'last_sent':row.last_sent.isoformat() if row.last_sent else None,'created_at':row.created_at.isoformat(),
        'program_id':str(row.program_id) if row.program_id else None,'schedule_id':str(row.schedule_id) if row.schedule_id else None}


async def owner(request,session,lock=False):
    auth=await account(request);uid=UUID(auth['user_id'])
    user=await IdentityRepository(session).by_id(uid,lock=lock)
    if user is None:raise HTTPException(404,'User not found')
    return user


async def owned(session,uid,nid):
    row=await session.scalar(select(Notification).where(Notification.user_id==uid,Notification.id==uid_value(nid)))
    if row is None:raise HTTPException(404,'Notification not found')
    return row


def active():
    program=exists(select(StudyProgram.id).where(StudyProgram.user_id==Notification.user_id,StudyProgram.id==Notification.program_id,StudyProgram.archived_at.is_(None)))
    schedule=exists(select(StudySchedule.id).join(Notebook,(Notebook.id==StudySchedule.notebook_id)&(Notebook.user_id==StudySchedule.user_id)).where(
        StudySchedule.id==Notification.schedule_id,StudySchedule.user_id==Notification.user_id,Notebook.archived_at.is_(None)))
    return or_(Notification.program_id.is_(None),program),or_(Notification.schedule_id.is_(None),schedule)


@router.get('/notifications')
async def listing(request:Request):
    async with unit_of_work() as session:
        user=await owner(request,session)
        return [public(n) for n in (await session.scalars(select(Notification).where(Notification.user_id==user.id,*active()).order_by(Notification.created_at,Notification.id))).all()]


@router.post('/notifications')
async def create(request:Request,body:NotificationInput):
    async with unit_of_work() as session:
        user=await owner(request,session,True);row=Notification(user_id=user.id,**body.values());session.add(row);await session.flush()
        return public(row)


async def due(request,claim,window):
    async with unit_of_work() as session:
        user=await owner(request,session,claim);now=utc_now();local=now.astimezone(ZoneInfo(user.timezone))
        slots=[local+timedelta(minutes=n) for n in range(-window,window+1)]
        rows=(await session.scalars(select(Notification).where(Notification.user_id==user.id,Notification.enabled.is_(True),
            Notification.scheduled_time.in_([s.time().replace(second=0,microsecond=0,tzinfo=None) for s in slots]),*active()).order_by(Notification.created_at,Notification.id))).all()
        result=[]
        for row in rows:
            slot=next(s for s in slots if s.hour==row.scheduled_time.hour and s.minute==row.scheduled_time.minute)
            if row.repeat=='none' and row.last_sent:continue
            if row.last_occurrence and row.last_occurrence>=slot.date():continue
            if row.repeat in ('weekly','custom') and DAYS[slot.weekday()] not in row.repeat_days:continue
            result.append(public(row))
            if claim:row.last_sent=now;row.last_occurrence=slot.date()
        return result


@router.get('/notifications/pending')
async def pending(request:Request):return await due(request,False,0)


@router.get('/notifications/check')
async def check(request:Request,timezone_offset:int=0):
    # Compatibility parameter: persisted IANA timezone handles DST consistently.
    return await due(request,True,1)


@router.patch('/notifications/{notification_id}')
async def update(request:Request,notification_id:str,body:NotificationInput):
    async with unit_of_work() as session:
        user=await owner(request,session,True);row=await owned(session,user.id,notification_id)
        for key,value in body.values().items():setattr(row,key,value)
        return {'message':'Notification updated'}


@router.patch('/notifications/{notification_id}/toggle')
async def toggle(request:Request,notification_id:str):
    async with unit_of_work() as session:
        user=await owner(request,session,True);row=await owned(session,user.id,notification_id);row.enabled=not row.enabled
        return {'message':'Notification toggled','enabled':row.enabled}


@router.delete('/notifications/{notification_id}')
async def remove(request:Request,notification_id:str):
    async with unit_of_work() as session:
        user=await owner(request,session,True);row=await owned(session,user.id,notification_id);await session.delete(row)
        return {'message':'Notification deleted'}


@router.post('/notifications/{notification_id}/send')
async def sent(request:Request,notification_id:str,channel:Channel=Query(...)):
    async with unit_of_work() as session:
        user=await owner(request,session,True);row=await owned(session,user.id,notification_id);now=utc_now()
        occurrence=max(row.last_occurrence or now.astimezone(ZoneInfo(user.timezone)).date(),now.astimezone(ZoneInfo(user.timezone)).date())
        log=await session.scalar(select(NotificationDelivery).where(NotificationDelivery.user_id==user.id,
            NotificationDelivery.notification_id==row.id,NotificationDelivery.occurrence==occurrence,NotificationDelivery.channel==channel))
        if log is None:
            log=NotificationDelivery(user_id=user.id,notification_id=row.id,occurrence=occurrence,sent_at=now,channel=channel);session.add(log)
        row.last_sent=now;row.last_occurrence=occurrence;await session.flush()
        return {'message':'Notification marked as sent','log_id':str(log.id)}


@router.post('/study/programs/{program_id}/create-reminders')
async def reminders(request:Request,program_id:str,body:RemindersInput):
    async with unit_of_work() as session:
        user=await owner(request,session,True);pid=uid_value(program_id)
        program=await session.scalar(select(StudyProgram).where(StudyProgram.user_id==user.id,StudyProgram.id==pid,StudyProgram.archived_at.is_(None)))
        if program is None:raise HTTPException(404,'Programa não encontrado')
        schedules=(await session.execute(select(StudySchedule,Notebook.name).join(Notebook,
            (Notebook.id==StudySchedule.notebook_id)&(Notebook.user_id==StudySchedule.user_id)).where(
                StudySchedule.user_id==user.id,Notebook.program_id==pid,Notebook.archived_at.is_(None)))).all()
        count=0
        for schedule,name in schedules:
            kinds=['start','end'] if body.include_end_reminder else ['start']
            for kind in kinds:
                row=await session.scalar(select(Notification).where(Notification.user_id==user.id,Notification.schedule_id==schedule.id,Notification.reminder_kind==kind))
                if row is None:
                    row=Notification(user_id=user.id,program_id=pid,schedule_id=schedule.id,reminder_kind=kind);session.add(row);count+=1
                point=schedule.start_time if kind=='start' else schedule.end_time
                minute=point.hour*60+point.minute-(body.minutes_before if kind=='start' else 0)
                day=(DAYS.index(schedule.day_of_week)+minute//1440)%7;minute%=1440
                row.title=f'Hora de estudar: {name}' if kind=='start' else f'Fim do estudo: {name}'
                row.message=f'{schedule.day_of_week} {schedule.start_time:%H:%M} - {schedule.end_time:%H:%M} | {schedule.tipo_estudo}'
                row.type='reminder';row.category='study';row.scheduled_time=time(minute//60,minute%60)
                row.repeat='weekly';row.repeat_days=[DAYS[day]];row.channels=['in_app','browser'];row.enabled=True
                await session.flush()
        return {'success':True,'created':count,'message':f'{count} lembretes criados para o cronograma de estudos!'}
