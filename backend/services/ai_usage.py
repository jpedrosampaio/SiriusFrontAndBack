from datetime import datetime,timezone,timedelta
from uuid import UUID
from sqlalchemy import select,func
from db.models.agent import Usage
from db.session import unit_of_work


async def record_gemini(user_id,model,delta=1,usage=None,feature='text'):
    if not user_id: return
    async with unit_of_work() as session:
        session.add(Usage(user_id=UUID(str(user_id)),provider='gemini',model=model,task=feature,status='completed',
            duration_ms=0,usage={'count':delta,**{k:v for k,v in (usage or {}).items() if type(v) is int and v >= 0}}))


async def gemini_today(user_id):
    start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    async with unit_of_work() as session:
        rows=(await session.execute(select(Usage.model,func.sum(Usage.usage['count'].as_integer())).where(
            Usage.user_id==UUID(str(user_id)),Usage.provider=='gemini',Usage.created_at>=start,
            Usage.created_at<start+timedelta(days=1)).group_by(Usage.model))).all()
        return {model:{'used':int(count or 0),'limit':0,'remaining':None} for model,count in rows}
