"""Owned document retrieval. Lexical fallback is explicit, never called vector search."""
import hashlib
import re
import unicodedata
import os
from ai.types import AIError
from pymongo.errors import PyMongoError
from fastapi import HTTPException


def terms(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return set(re.findall(r'[a-z0-9]{3,}', text)) - {'para', 'como', 'uma', 'que', 'com', 'por', 'dos', 'das'}


def chunks(pages, size=1400):
    for number, page in enumerate(pages, 1):
        text = page.get('text', '') if isinstance(page, dict) else str(page)
        page_number = page.get('page', number) if isinstance(page, dict) else number
        for start in range(0, len(text), size-150):
            content = text[start:start+size].strip()
            if content:
                yield {'page': page_number, 'text': content, 'hash': hashlib.sha256(content.encode()).hexdigest(), 'terms': sorted(terms(content))[:250]}


class Retrieval:
    def __init__(self, db, router=None, credentials=None):
        self.db, self.router, self.credentials = db, router, credentials
        self.vector_index = os.getenv('AI_ATLAS_VECTOR_INDEX', '')

    async def embedding(self, user_id, text):
        if not self.vector_index or not self.router or not self.credentials: return None
        from ai.config import MODELS
        model = MODELS['embedding'].name
        key = hashlib.sha256(f'{user_id}:{model}:768:{text}'.encode()).hexdigest()
        existing = await self.db.ai_embeddings.find_one({'_id': key, 'user_id': user_id})
        if existing: return existing['vector']
        keys = await self.credentials.get(user_id)
        if not keys.get('gemini'): return None
        result = await self.router.generate(task='embedding', keys=keys, user_id=user_id, prompt=text)
        await self.db.ai_embeddings.update_one({'_id': key, 'user_id': user_id}, {'$setOnInsert': {'vector': result.data, 'model': model, 'dimensions': 768}}, upsert=True)
        return result.data

    async def index_edital(self, user_id, source_id):
        from services.edital_analyses import get
        source = await get(user_id, source_id, include_source=True)
        pages = source.get('pdf_pages') or [source.get('pdf_text', '')]
        return await self.index_pages(user_id, source_id, 'edital', pages, source)

    async def index_notebook(self, user_id, source_id):
        source = await self.db.notebooks.find_one({'user_id': user_id, 'notebook_id': source_id})
        if not source: raise HTTPException(404, 'Caderno não encontrado.')
        drafts = await self.db.study_drafts.find({'user_id': user_id, 'notebook_id': source_id}, {'text': 1, '_id': 0}).to_list(100)
        notes = await self.db.study_notes.find({'user_id': user_id, 'notebook_id': source_id}, {'content': 1, 'title': 1, '_id': 0}).to_list(100)
        pages = [source.get('notes') or '', *[d.get('text', '') for d in drafts], *[(n.get('title', '') + '\n' + n.get('content', '')) for n in notes]]
        pages = [re.sub(r'<[^>]+>', ' ', str(p)) for p in pages]
        return await self.index_pages(user_id, source_id, 'notebook', pages, source)

    async def ensure_selection(self, user_id, selection):
        for key, field in [('analysis', 'analysis_id'), ('notebook', 'notebook_id')]:
            if key not in selection: continue
            source_id = selection[key][field]
            if key == 'analysis' and await self.db.ai_chunks.find_one({'user_id': user_id, 'source_id': source_id}, {'_id': 1}): continue
            if key == 'analysis': await self.index_edital(user_id, source_id)
            else: await self.index_notebook(user_id, source_id)

    async def index_pages(self, user_id, source_id, source_type, pages, source):
        batch = list(chunks(pages))[:2000]
        generation = hashlib.sha256(''.join(c['hash'] for c in batch).encode()).hexdigest()
        existing = await self.db.ai_chunks.count_documents({'user_id': user_id, 'source_id': source_id, 'source_type': source_type, 'generation': generation}, limit=len(batch) + 1)
        if batch and existing == len(batch):
            await self.db.ai_chunks.delete_many({'user_id': user_id, 'source_id': source_id, 'source_type': source_type, 'generation': {'$ne': generation}})
            return {'chunks': len(batch), 'method': 'lexical', 'source_id': source_id, 'unchanged': True}
        embed_available = bool(self.vector_index)
        for i, chunk in enumerate(batch):
            key = hashlib.sha256(f'{user_id}:{source_type}:{source_id}:{generation}:{i}'.encode()).hexdigest()
            await self.db.ai_chunks.update_one({'_id': key, 'user_id': user_id}, {'$setOnInsert': {**chunk, 'source_id': source_id, 'source_type': source_type, 'generation': generation, 'section': 'PDF' if source_type == 'edital' else 'Anotações', 'program_id': source.get('program_id'), 'notebook_id': source.get('notebook_id')}}, upsert=True)
            if embed_available:
                try:
                    vector = await self.embedding(user_id, chunk['text'])
                    if vector: await self.db.ai_chunks.update_one({'_id': key, 'user_id': user_id}, {'$set': {'vector': vector}})
                except (AIError, PyMongoError):
                    # Continue lexical indexing; quotas never prevent document access.
                    embed_available = False
        await self.db.ai_chunks.delete_many({'user_id': user_id, 'source_id': source_id, 'source_type': source_type, 'generation': {'$ne': generation}})
        return {'chunks': len(batch), 'method': 'lexical', 'source_id': source_id, 'truncated': sum(len(str(p)) for p in pages) > 2500000}

    async def search(self, user_id, query, source_id=None):
        tokens = sorted(terms(query))[:30]
        if not tokens: return {'method': 'lexical', 'citations': []}
        own = {'user_id': user_id, 'terms': {'$in': tokens}}
        if source_id: own['source_id'] = source_id
        ranked, method = [], 'lexical'
        if self.vector_index:
            try:
                vector = await self.embedding(user_id, query)
                if vector:
                    scope = {'user_id': user_id}
                    if source_id: scope['source_id'] = source_id
                    ranked = await self.db.ai_chunks.aggregate([{'$vectorSearch': {'index': self.vector_index, 'path': 'vector', 'queryVector': vector, 'numCandidates': 80, 'limit': 5, 'filter': scope}}, {'$match': scope}, {'$project': {'vector': 0, '_id': 0}}]).to_list(5)
                    if ranked: method = 'atlas_vector'
            except (AIError, PyMongoError): pass
        if not ranked:
            rows = await self.db.ai_chunks.find(own, {'_id': 0, 'vector': 0}).limit(150).to_list(150)
            ranked = sorted(rows, key=lambda r: len(set(tokens) & set(r.get('terms', []))) / max(1, len(set(r.get('terms', []))) ** .5), reverse=True)
            if not ranked and source_id:
                ranked = await self.db.ai_chunks.find({'user_id': user_id, 'source_id': source_id}, {'_id': 0, 'vector': 0}).sort('page', 1).to_list(5)
        citations = []
        for r in ranked[:5]:
            # Deleting an edital revokes retrieval immediately, even before cleanup.
            collection, field = {'notebook': ('notebooks', 'notebook_id'), 'attachment': ('ai_attachments', 'attachment_id')}.get(r.get('source_type'), ('edital_analyses', 'analysis_id'))
            if collection == 'edital_analyses':
                from services.edital_analyses import get
                try: exists = await get(user_id,r['source_id'])
                except HTTPException as error:
                    if error.status_code != 404: raise
                    exists = None
            else:
                exists = await self.db[collection].find_one({'user_id': user_id, field: r['source_id']}, {'_id': 1})
            if exists: citations.append({k: r.get(k) for k in ('source_id', 'source_type', 'page', 'section', 'hash', 'text')})
        return {'method': method, 'citations': citations}
