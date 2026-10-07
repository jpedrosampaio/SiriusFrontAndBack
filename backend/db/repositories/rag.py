from sqlalchemy import delete, select, func, Integer
from db.models.files import RagSource, RagChunk
from db.models.studies import Notebook


def live_source():
    return (RagSource.notebook_id.is_(None) | select(Notebook.id).where(
        Notebook.user_id==RagSource.user_id, Notebook.id==RagSource.notebook_id,
        Notebook.archived_at.is_(None)).exists())


class RagRepository:
    """Owned SQL lexical retrieval. Vector mode is not silently simulated."""
    def __init__(self,session):
        self.session = session

    async def source(self,user_id,source_id):
        return await self.session.scalar(select(RagSource).where(RagSource.user_id == user_id,RagSource.id == source_id))

    async def replace_chunks(self,user_id,source_id,generation,chunks):
        source = await self.session.scalar(select(RagSource).where(RagSource.user_id == user_id,
            RagSource.id == source_id).with_for_update())
        if source is None:
            raise LookupError('Source not found')
        if source.generation == generation:
            count = await self.session.scalar(select(func.count()).select_from(RagChunk).where(RagChunk.user_id == user_id,RagChunk.source_id == source_id))
            if count == len(chunks):
                return {'chunks':count,'unchanged':True}
        await self.session.execute(delete(RagChunk).where(RagChunk.user_id == user_id,RagChunk.source_id == source_id))
        for i,item in enumerate(chunks):
            self.session.add(RagChunk(user_id=user_id,source_id=source_id,chunk_index=i,content=item['text'],
                content_hash=item['hash'],terms=item['terms'],details={'page':item.get('page')}))
        source.generation = generation
        await self.session.flush()
        return {'chunks':len(chunks),'unchanged':False}

    async def lexical_search(self,user_id,tokens,source_id=None,limit=5):
        if not tokens:
            return []
        # Both ends of the join are scoped; deleting a source immediately revokes retrieval.
        query = select(RagChunk).join(RagSource,(RagChunk.source_id == RagSource.id) & (RagChunk.user_id == RagSource.user_id))
        query = query.where(RagChunk.user_id == user_id,RagSource.user_id == user_id,live_source(),RagChunk.terms.overlap(list(tokens)[:30]))
        if source_id:
            query = query.where(RagSource.id == source_id)
        score = sum(func.coalesce(RagChunk.terms.any(token),False).cast(Integer) for token in list(tokens)[:30])
        return list((await self.session.scalars(query.order_by(score.desc(),RagChunk.id).limit(min(max(limit,1),20)))).all())

    async def remove_source(self,user_id,source_id):
        await self.session.execute(delete(RagSource).where(RagSource.user_id == user_id,RagSource.id == source_id))
