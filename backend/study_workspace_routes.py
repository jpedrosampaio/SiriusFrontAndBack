"""Owner-scoped study drafts and dated planning, independent of AI generation."""
import hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, HTTPException, Query, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from datetime import date as CalendarDate, timedelta
from study_planner import build_plan
from study_adaptation import adapt_notebooks, next_review
from zoneinfo import ZoneInfo
import uuid


class DraftUpdate(BaseModel):
    text: str = Field(max_length=100000)
    revision: int = Field(ge=0)


class PlanSettings(BaseModel):
    start_date: CalendarDate
    end_date: CalendarDate
    availability: list[int] = Field(min_length=7, max_length=7)
    block_minutes: int = Field(default=50, ge=15, le=120)
    adaptive: bool = False


class TopicPractice(BaseModel):
    topic_key: str = Field(pattern=r'^\d+(?:_\d+)?$')
    total: int = Field(ge=1, le=1000)
    correct: int = Field(ge=0, le=1000)


class PlanEntryUpdate(BaseModel):
    completed: Optional[bool] = None
    date: Optional[CalendarDate] = None


def workspace_router(db, authenticate, mutate):
    router = APIRouter(prefix='/study')

    async def owner(request, token, notebook_id):
        user = await authenticate(authorization=request.headers.get('Authorization'), session_token=token)
        if not await db.notebooks.find_one({'user_id': user.user_id, 'notebook_id': notebook_id}, {'_id': 1}):
            raise HTTPException(404, 'Matéria não encontrada')
        return user.user_id

    def key(user_id, notebook_id, topic_key):
        return hashlib.sha256(f'{user_id}:{notebook_id}:{topic_key}'.encode()).hexdigest()

    @router.get('/notebooks/{notebook_id}/reviews')
    async def reviews(request: Request, notebook_id: str, session_token: Optional[str] = Cookie(None)):
        user_id = await owner(request, session_token, notebook_id)
        return await db.study_topic_reviews.find({'user_id': user_id, 'notebook_id': notebook_id}, {'_id': 0}).sort('due_date', 1).to_list(1000)

    @router.post('/notebooks/{notebook_id}/practice')
    async def practice(request: Request, notebook_id: str, body: TopicPractice, session_token: Optional[str] = Cookie(None)):
        user_id = await owner(request, session_token, notebook_id)
        if body.correct > body.total:
            raise HTTPException(422, 'Acertos não podem superar o total.')
        if not request.headers.get('Idempotency-Key'):
            raise HTTPException(422, 'Idempotency-Key obrigatório.')
        today = datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
        async def apply(session, balance):
            notebook = await db.notebooks.find_one({'user_id': user_id, 'notebook_id': notebook_id}, session=session)
            topics = notebook.get('conteudo_programatico') or notebook.get('topicos') or []
            indexes = [int(value) for value in body.topic_key.split('_')]
            if indexes[0] >= len(topics):
                raise HTTPException(422, 'Assunto não encontrado no conteúdo da disciplina.')
            topic = topics[indexes[0]]
            title = topic.get('assunto', '') if isinstance(topic, dict) else str(topic)
            if len(indexes) == 2:
                children = topic.get('subtopicos', []) if isinstance(topic, dict) else []
                if not isinstance(children, list) or indexes[1] >= len(children):
                    raise HTTPException(422, 'Subtópico não encontrado.')
                title = children[indexes[1]]
            values = {'user_id': user_id, 'notebook_id': notebook_id, 'program_id': notebook.get('program_id'),
                      'topic_key': body.topic_key, 'title': title, 'total': body.total, 'correct': body.correct,
                      'incorrect': body.total - body.correct, 'date': today, 'source': 'topic_practice',
                      'created_at': datetime.now(timezone.utc).isoformat()}
            await db.question_logs.insert_one({**values, 'log_id': 'qlog_' + uuid.uuid4().hex}, session=session)
            review = {**values, 'due_date': next_review(today, body.total, body.correct),
                      'accuracy': round(body.correct / body.total * 100, 1)}
            await db.study_topic_reviews.replace_one({'_id': key(user_id, notebook_id, body.topic_key)}, review, upsert=True, session=session)
            await db.notebooks.update_one({'user_id': user_id, 'notebook_id': notebook_id}, {'$inc': {'total_questions': body.total, 'correct_questions': body.correct}}, session=session)
            return review
        return await mutate(user_id, request.headers.get('Idempotency-Key'), ['topic-practice', notebook_id, body.model_dump()], apply)

    @router.get('/notebooks/{notebook_id}/learning-summary')
    async def learning_summary(request: Request, notebook_id: str, session_token: Optional[str] = Cookie(None)):
        user_id = await owner(request, session_token, notebook_id)
        from dashboard_service import aggregate_one
        totals = await aggregate_one(db.question_logs, {'user_id': user_id, 'notebook_id': notebook_id},
                                     {'answered': {'$sum': '$total'}, 'correct': {'$sum': '$correct'}})
        answered, correct = totals.get('answered', 0), totals.get('correct', 0)
        return {'answered': answered, 'correct': correct, 'accuracy': round(correct / answered * 100, 1) if answered else None}

    @router.get('/notebooks/{notebook_id}/draft')
    async def get_draft(request: Request, notebook_id: str,
                        topic_key: str = Query('general', pattern=r'^(general|\d+(?:_\d+)?)$'),
                        session_token: Optional[str] = Cookie(None)):
        user_id = await owner(request, session_token, notebook_id)
        doc = await db.study_drafts.find_one({'_id': key(user_id, notebook_id, topic_key)}, {'_id': 0})
        return doc or {'text': '', 'revision': 0}

    @router.put('/notebooks/{notebook_id}/draft')
    async def save_draft(request: Request, notebook_id: str, body: DraftUpdate,
                         topic_key: str = Query('general', pattern=r'^(general|\d+(?:_\d+)?)$'),
                         session_token: Optional[str] = Cookie(None)):
        user_id = await owner(request, session_token, notebook_id)
        doc_id = key(user_id, notebook_id, topic_key)
        values = {'user_id': user_id, 'notebook_id': notebook_id, 'topic_key': topic_key,
                  'text': body.text, 'updated_at': datetime.now(timezone.utc).isoformat()}
        if body.revision == 0:
            try:
                await db.study_drafts.insert_one({'_id': doc_id, **values, 'revision': 1})
                return {**values, 'revision': 1}
            except DuplicateKeyError:
                pass
        else:
            saved = await db.study_drafts.find_one_and_update(
                {'_id': doc_id, 'revision': body.revision}, {'$set': values, '$inc': {'revision': 1}},
                return_document=ReturnDocument.AFTER, projection={'_id': 0})
            if saved:
                return saved
        # A response may have been lost after a successful save; equal text is safe.
        previous = await db.study_drafts.find_one({'_id': doc_id}, {'_id': 0})
        if previous and previous['text'] == body.text:
            return previous
        raise HTTPException(409, 'Esta anotação foi alterada em outra sessão. Recarregue antes de substituir.')

    async def program_owner(request, token, program_id):
        user = await authenticate(authorization=request.headers.get('Authorization'), session_token=token)
        program = await db.study_programs.find_one({'user_id': user.user_id, 'program_id': program_id}, {'_id': 0})
        if not program:
            raise HTTPException(404, 'Programa não encontrado')
        return user.user_id, program

    @router.get('/programs/{program_id}/dated-plan')
    async def get_plan(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
        user_id, _ = await program_owner(request, session_token, program_id)
        return await db.study_dated_plans.find_one({'_id': f'{user_id}:{program_id}'}, {'_id': 0}) or {'entries': [], 'settings': None}

    @router.post('/programs/{program_id}/dated-plan')
    async def create_plan(request: Request, program_id: str, body: PlanSettings, session_token: Optional[str] = Cookie(None)):
        user_id, program = await program_owner(request, session_token, program_id)
        if any(minutes < 0 or minutes > 720 for minutes in body.availability) or not any(minutes >= 15 for minutes in body.availability):
            raise HTTPException(422, 'Informe de 15 a 720 minutos em pelo menos um dia.')
        if not 0 <= (body.end_date - body.start_date).days <= 180:
            raise HTTPException(422, 'Escolha um período de até 181 dias.')
        target = str(program.get('target_date') or '')[:10]
        if target and body.end_date.isoformat() > target:
            raise HTTPException(422, 'O cronograma deve terminar até a data da prova/meta.')
        settings = body.model_dump(mode='json')
        async def apply(session, balance):
            own = {'user_id': user_id, 'program_id': program_id}
            notebooks = await db.notebooks.find(own, {'_id': 0, 'notebook_id': 1, 'name': 1, 'weight': 1}, session=session).to_list(500)
            if not notebooks:
                raise HTTPException(422, 'Adicione disciplinas antes de planejar.')
            previous = await db.study_dated_plans.find_one({'_id': f'{user_id}:{program_id}'}, session=session) or {}
            completed = [e for e in previous.get('entries', []) if e.get('completed')]
            if body.adaptive:
                rows = await db.question_logs.aggregate([
                    {'$match': {'user_id': user_id, 'program_id': program_id}},
                    {'$group': {'_id': '$notebook_id', 'total': {'$sum': '$total'}, 'correct': {'$sum': '$correct'}}}
                ], session=session).to_list(None)
                overdue = {e.get('notebook_id') for e in previous.get('entries', []) if not e.get('completed') and e['date'] < body.start_date.isoformat()}
                notebooks = adapt_notebooks(notebooks, {r['_id']: r for r in rows}, overdue)
            entries = build_plan(program_id, notebooks, body.availability, body.start_date.isoformat(), body.end_date.isoformat(), body.block_minutes, completed)
            result = {**own, 'settings': settings, 'entries': entries, 'updated_at': datetime.now(timezone.utc).isoformat()}
            await db.study_dated_plans.replace_one({'_id': f'{user_id}:{program_id}'}, result, upsert=True, session=session)
            return result
        return await mutate(user_id, request.headers.get('Idempotency-Key'), ['dated-plan', program_id, settings], apply)

    @router.patch('/programs/{program_id}/dated-plan/{entry_id}')
    async def update_plan_entry(request: Request, program_id: str, entry_id: str, body: PlanEntryUpdate, session_token: Optional[str] = Cookie(None)):
        user_id, program = await program_owner(request, session_token, program_id)
        async def apply(session, balance):
            query = {'_id': f'{user_id}:{program_id}'}
            doc = await db.study_dated_plans.find_one(query, session=session)
            entry = next((e for e in (doc or {}).get('entries', []) if e['entry_id'] == entry_id), None)
            if not entry:
                raise HTTPException(404, 'Bloco não encontrado')
            if body.date:
                if entry.get('completed'):
                    raise HTTPException(409, 'O histórico concluído não pode ser remarcado.')
                settings = doc['settings']
                iso = body.date.isoformat()
                if not settings['start_date'] <= iso <= settings['end_date']:
                    raise HTTPException(422, 'Data fora do período planejado.')
                occupied = sum(e['minutes'] for e in doc['entries'] if e['date'] == iso and e['entry_id'] != entry_id)
                if occupied + entry['minutes'] > settings['availability'][body.date.weekday()]:
                    raise HTTPException(422, 'Este dia não tem tempo disponível para o bloco.')
                entry['date'] = iso
            if body.completed is not None:
                entry['completed'] = body.completed
            await db.study_dated_plans.update_one(query, {'$set': {'entries': doc['entries']}}, session=session)
            return entry
        return await mutate(user_id, request.headers.get('Idempotency-Key'), ['dated-entry', program_id, entry_id, body.model_dump(mode='json')], apply)

    return router
