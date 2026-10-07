"""Owned explicit memories with hash-only blocking and serialized limits."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func
from ai.memory import fingerprint
from db.models.agent import Memory
from db.activity import run_activity
from db.session import unit_of_work


def identity(value):
    try: return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, 'Memória não encontrada.') from None


def public(row):
    return {'memory_id':str(row.id), 'user_id':str(row.user_id), 'category':row.kind,
        'content':row.content, 'hash':row.content_hash, 'blocked':row.blocked,
        'created_at':row.created_at.isoformat(), 'updated_at':row.updated_at.isoformat()}


class Memories:
    async def list(self, user_id):
        async with unit_of_work() as session:
            rows = (await session.scalars(select(Memory).where(Memory.user_id==identity(user_id), Memory.blocked.is_(False))
                .order_by(Memory.updated_at.desc(), Memory.id).limit(50))).all()
            return [public(row) for row in rows]

    async def save(self, user_id, body, memory_id=None):
        mid = identity(memory_id) if memory_id else None
        digest = fingerprint(body.content)
        if not body.content.strip(): raise HTTPException(422, 'Informe o conteúdo da memória.')
        async def apply(session, user):
            blocked = await session.scalar(select(Memory.id).where(Memory.user_id==user.id,
                Memory.content_hash==digest, Memory.blocked.is_(True)).limit(1))
            if blocked:
                raise HTTPException(409, 'Esta memória foi bloqueada para não ser lembrada novamente.')
            row = None
            if mid:
                row = await session.scalar(select(Memory).where(Memory.user_id==user.id, Memory.id==mid, Memory.blocked.is_(False)))
                if row is None: raise HTTPException(404, 'Memória não encontrada.')
            duplicate = await session.scalar(select(Memory).where(Memory.user_id==user.id,
                Memory.kind==body.category, Memory.content_hash==digest))
            if duplicate and duplicate.id != mid:
                if mid: raise HTTPException(409, 'Esta memória já existe.')
                return public(duplicate)
            if row is None:
                count = await session.scalar(select(func.count()).select_from(Memory).where(Memory.user_id==user.id, Memory.blocked.is_(False)))
                if count >= 50: raise HTTPException(409, 'Limite de 50 memórias. Edite ou remova uma memória.')
                row = Memory(user_id=user.id, kind=body.category, content=body.content, content_hash=digest)
                session.add(row)
            else:
                row.kind, row.content, row.content_hash = body.category, body.content, digest
            await session.flush()
            await session.refresh(row)
            return public(row)
        return await run_activity(identity(user_id), None, ['save_memory'], apply)

    async def remove(self, user_id, memory_id, block=True):
        mid = identity(memory_id)
        async def apply(session, user):
            row = await session.scalar(select(Memory).where(Memory.user_id==user.id, Memory.id==mid))
            if row is None: raise HTTPException(404, 'Memória não encontrada.')
            if block:
                # Keep the category/hash key but erase personal content and provenance.
                row.blocked, row.content, row.provenance = True, '', {}
            else:
                await session.delete(row)
            return {'removed':True, 'blocked':block}
        return await run_activity(identity(user_id), None, ['remove_memory'], apply)
