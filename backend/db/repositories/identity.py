import hashlib
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.identity import User, UserSession


class IdentityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_email(self, email: str):
        return await self.session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    async def by_id(self, user_id: UUID, *, lock=False):
        statement = select(User).where(User.id == user_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def create(self, *, email, name, password_hash, timezone_name='America/Sao_Paulo'):
        user = User(email=email.strip().lower(), name=name, password_hash=password_hash, timezone=timezone_name)
        self.session.add(user)
        await self.session.flush()
        return user

    async def add_session(self, user_id, token, expires_at):
        row = UserSession(user_id=user_id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=expires_at)
        self.session.add(row)
        await self.session.flush()
        return row

    async def authenticated(self, token):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return await self.session.scalar(select(User).join(UserSession).where(
            UserSession.token_hash == token_hash, UserSession.expires_at > datetime.now(timezone.utc)))

    async def revoke(self, token):
        await self.session.execute(delete(UserSession).where(UserSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))

    async def expire_sessions(self, limit=500):
        expired = select(UserSession.id).where(UserSession.expires_at <= datetime.now(timezone.utc)).order_by(UserSession.expires_at).limit(limit)
        result = await self.session.execute(delete(UserSession).where(UserSession.id.in_(expired)))
        return result.rowcount
