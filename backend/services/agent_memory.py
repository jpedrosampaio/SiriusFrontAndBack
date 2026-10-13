"""Owned explicit memories with hash-only blocking and serialized limits."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func
from ai.memory import fingerprint
from db.models.agent import Memory
from db.activity import run_activity
from db.session import unit_of_work
import hashlib
import json
from services.command_audit import record


def version(row):
    return hashlib.sha256(json.dumps([str(row.id), row.kind, row.content_hash,
        row.updated_at.isoformat(), row.provenance], sort_keys=True).encode()).hexdigest()


def identity(value):
    try: return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, 'Memória não encontrada.') from None


def public(row):
    return {'memory_id':str(row.id), 'user_id':str(row.user_id), 'category':row.kind,
        'content':row.content, 'hash':row.content_hash, 'blocked':row.blocked,
        'created_at':row.created_at.isoformat(), 'updated_at':row.updated_at.isoformat(),
        'version':version(row), 'provenance':row.provenance or {'origin':'legacy_unknown'},
        'scope':(row.provenance or {}).get('scope','global')}


class Memories:
    async def list(self, user_id):
        async with unit_of_work() as session:
            rows = (await session.scalars(select(Memory).where(Memory.user_id==identity(user_id), Memory.blocked.is_(False))
                .order_by(Memory.updated_at.desc(), Memory.id).limit(50))).all()
            return [public(row) for row in rows]

    async def save(self, user_id, body, memory_id=None, *, request_key=None, expected_version=None):
        mid = identity(memory_id) if memory_id else None
        if not request_key:raise HTTPException(428,'Idempotency-Key obrigatório.')
        if mid and not expected_version:raise HTTPException(428,'Versão atual obrigatória.')
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
                if expected_version is not None and version(row) != expected_version:
                    raise HTTPException(409, 'Memória alterada. Recarregue antes de corrigir.')
            duplicate = await session.scalar(select(Memory).where(Memory.user_id==user.id,
                Memory.kind==body.category, Memory.content_hash==digest))
            if duplicate and duplicate.id != mid:
                if mid: raise HTTPException(409, 'Esta memória já existe.')
                if (duplicate.provenance or {}).get('scope','global') != body.scope:
                    raise HTTPException(409,'A memória já existe em outro escopo; corrija o registro existente.')
                return {'memory_id':str(duplicate.id),'version':version(duplicate)}
            if row is None:
                count = await session.scalar(select(func.count()).select_from(Memory).where(Memory.user_id==user.id, Memory.blocked.is_(False)))
                if count >= 50: raise HTTPException(409, 'Limite de 50 memórias. Edite ou remova uma memória.')
                row = Memory(user_id=user.id, kind=body.category, content=body.content, content_hash=digest)
                session.add(row)
            else:
                row.kind, row.content, row.content_hash = body.category, body.content, digest
            # Only a user-confirmed endpoint writes memory. A declared fact is not verified.
            row.provenance = {'origin':'user_declared', 'source':'explicit_memory_editor',
                'scope':body.scope, 'verified':False}
            await session.flush()
            await session.refresh(row)
            await record(session,user.id,event='memory.updated' if mid else 'memory.created',
                action='update' if mid else 'create',entity_type='memory',entity_id=row.id,
                evidence=['Informação declarada explicitamente pelo proprietário.'],
                limitations=['Não verificada pelo sistema; nenhuma inferência foi salva como fato.'],
                after={'category':row.kind,'scope':body.scope,'version':version(row)})
            return {'memory_id':str(row.id),'version':version(row)}
        return await run_activity(identity(user_id), request_key,
            ['save_memory',str(mid),body.model_dump(),expected_version], apply)

    async def remove(self, user_id, memory_id, block=True, *, request_key=None, expected_version=None):
        mid = identity(memory_id)
        if not request_key:raise HTTPException(428,'Idempotency-Key obrigatório.')
        if not expected_version:raise HTTPException(428,'Versão atual obrigatória.')
        async def apply(session, user):
            row = await session.scalar(select(Memory).where(Memory.user_id==user.id, Memory.id==mid))
            if row is None: raise HTTPException(404, 'Memória não encontrada.')
            if expected_version is not None and version(row) != expected_version:
                raise HTTPException(409, 'Memória alterada. Recarregue antes de remover.')
            if block:
                # Keep the category/hash key but erase personal content and provenance.
                row.blocked, row.content, row.provenance = True, '', {}
                await session.flush();await session.refresh(row)
            else:
                await session.delete(row)
            await record(session,user.id,event='memory.removed',action='remove',entity_type='memory',
                entity_id=mid,evidence=['Remoção explícita solicitada pelo proprietário.'],
                limitations=['Conteúdo removido não é copiado para a auditoria nem oferece desfazer.'])
            return {'removed':True, 'blocked':block,'version':version(row) if block else None}
        return await run_activity(identity(user_id),request_key,['remove_memory',str(mid),block,expected_version],apply)
