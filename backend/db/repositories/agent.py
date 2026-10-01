from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from db.models.agent import Action, ActionAudit, Preferences


class AgentRepository:
    def __init__(self,session):
        self.session = session

    async def preferences(self,user_id):
        row = await self.session.scalar(select(Preferences).where(Preferences.user_id == user_id))
        return row.settings if row else {}

    async def action(self,user_id,action_id):
        return await self.session.scalar(select(Action).where(Action.user_id == user_id,Action.id == action_id))

    async def propose(self,user_id,fingerprint,values):
        await self.session.execute(insert(Action).values(user_id=user_id,request_fingerprint=fingerprint,**values)
            .on_conflict_do_nothing(index_elements=['user_id','request_fingerprint']))
        return await self.session.scalar(select(Action).where(Action.user_id == user_id,Action.request_fingerprint == fingerprint))

    def audit(self,user_id,action):
        self.session.add(ActionAudit(user_id=user_id,action_id=action.id,tool=action.tool,version=action.version,status=action.status))
