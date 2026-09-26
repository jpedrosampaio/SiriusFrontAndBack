import hashlib
import uuid
from datetime import datetime, timezone
from typing import Literal
from pydantic import Field
from fastapi import HTTPException
from ai.types import StrictModel


class MemoryInput(StrictModel):
    category: Literal['preference', 'rule', 'goal', 'context']
    content: str = Field(min_length=1, max_length=1000)


def fingerprint(content):
    return hashlib.sha256(' '.join(content.casefold().split()).encode()).hexdigest()


class Memory:
    def __init__(self, db): self.db = db

    async def list(self, user_id):
        return await self.db.ai_memory.find({'user_id': user_id, 'blocked': False}, {'_id': 0}).sort('updated_at', -1).to_list(50)

    async def save(self, user_id, body, memory_id=None):
        digest = fingerprint(body.content)
        if await self.db.ai_memory.find_one({'user_id': user_id, 'hash': digest, 'blocked': True}):
            raise HTTPException(409, 'Esta memória foi bloqueada para não ser lembrada novamente.')
        now = datetime.now(timezone.utc).isoformat()
        fields = {**body.model_dump(), 'hash': digest, 'blocked': False, 'updated_at': now}
        if memory_id:
            result = await self.db.ai_memory.update_one({'user_id': user_id, 'memory_id': memory_id, 'blocked': False}, {'$set': fields})
            if not result.matched_count: raise HTTPException(404, 'Memória não encontrada.')
        else:
            if await self.db.ai_memory.count_documents({'user_id': user_id, 'blocked': False}) >= 50: raise HTTPException(409, 'Limite de 50 memórias. Edite ou remova uma memória.')
            memory_id = uuid.uuid4().hex
            await self.db.ai_memory.insert_one({**fields, 'memory_id': memory_id, 'user_id': user_id, 'created_at': now})
        return {'memory_id': memory_id, **fields}

    async def remove(self, user_id, memory_id, block=True):
        query = {'user_id': user_id, 'memory_id': memory_id}
        if block:
            # Retain only hash tombstone, not deleted personal content.
            result = await self.db.ai_memory.update_one(query, {'$set': {'blocked': True}, '$unset': {'content': '', 'category': ''}})
            found = result.matched_count
        else:
            found = (await self.db.ai_memory.delete_one(query)).deleted_count
        if not found: raise HTTPException(404, 'Memória não encontrada.')
        return {'removed': True, 'blocked': block}
