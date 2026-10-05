from datetime import datetime,timezone,timedelta
from uuid import UUID
from sqlalchemy import select,func
from db.models.agent import Usage
from db.session import unit_of_work
from db.repositories.identity import IdentityRepository


async def record_gemini(user_id,model,delta=1,usage=None,feature='text'):
    if not user_id: return
    async with unit_of_work() as session:
        session.add(Usage(user_id=UUID(str(user_id)),provider='gemini',model=model,task=feature,status='completed',
            duration_ms=0,usage={'count':delta,**{k:v for k,v in (usage or {}).items() if type(v) is int and v >= 0}}))


async def gemini_today(user_id):
    start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    async with unit_of_work() as session:
        rows=(await session.execute(select(Usage.model,func.sum(Usage.usage['count'].as_integer())).where(
            Usage.user_id==UUID(str(user_id)),Usage.provider=='gemini',Usage.status=='completed',Usage.created_at>=start,
            Usage.created_at<start+timedelta(days=1)).group_by(Usage.model))).all()
        return {model:{'used':int(count or 0),'limit':0,'remaining':None} for model,count in rows}


async def reservation_count(session, uid, start):
    return await session.scalar(select(func.count()).select_from(Usage).where(Usage.user_id==uid,
        Usage.task=='internal_reservation', Usage.created_at>=start, Usage.created_at<start+timedelta(days=1)))


async def internal_today(user_id):
    start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    async with unit_of_work() as session:
        return await reservation_count(session,UUID(str(user_id)),start)


async def reserve_internal(user_id, model, limit):
    uid=UUID(str(user_id))
    start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    async with unit_of_work() as session:
        if await IdentityRepository(session).by_id(uid,lock=True) is None:return False
        if await reservation_count(session,uid,start)>=limit:return False
        session.add(Usage(user_id=uid,provider=model.provider,model=model.name,task='internal_reservation',
            status='reserved',duration_ms=0,usage={}))
        return True
