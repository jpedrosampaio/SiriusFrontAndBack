"""Additive preparations, individual evidence and unified review queue.

Existing programs are canonical; a target adds identity/capabilities without
copying notebooks, schedules or edital content.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Cookie, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from study_mastery import mastery, adaptive_review

ERROR_REASONS = Literal['unknown', 'forgot', 'interpretation', 'attention', 'concepts', 'calculation', 'legislation', 'other']


class TargetInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=180)
    kind: Literal['contest', 'certification', 'academic', 'course', 'custom'] = 'custom'
    program_id: Optional[str] = Field(default=None, max_length=100)
    institution: str = Field(default='', max_length=180)
    board: str = Field(default='', max_length=100)
    edition: str = Field(default='', max_length=80)
    position: str = Field(default='', max_length=180)
    exam_date: Optional[date] = None


class AttemptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    notebook_id: str = Field(min_length=1, max_length=100)
    topic_key: str = Field(pattern=r'^\d+(?:_\d+)?$')
    question: str = Field(min_length=1, max_length=12000)
    answer: str = Field(default='', max_length=4000)
    correct: StrictBool
    seconds: int = Field(default=0, ge=0, le=86400)
    source: str = Field(default='manual', max_length=200)
    board: str = Field(default='', max_length=100)
    exam: str = Field(default='', max_length=180)
    position: str = Field(default='', max_length=180)
    question_id: Optional[str] = Field(default=None, max_length=100)
    error_reason: Optional[ERROR_REASONS] = None
    difficulty: Optional[Literal['easy', 'medium', 'hard']] = None


class ErrorUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: ERROR_REASONS


class BlueprintInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=180)
    duration_minutes: int = Field(ge=1, le=600)


def topic_title(notebook, key):
    topics = notebook.get('conteudo_programatico') or notebook.get('topicos') or []
    indexes = [int(v) for v in key.split('_')]
    if indexes[0] >= len(topics):
        raise HTTPException(422, 'Assunto não encontrado.')
    item = topics[indexes[0]]
    if len(indexes) == 2:
        children = item.get('subtopicos', []) if isinstance(item, dict) else []
        if indexes[1] >= len(children): raise HTTPException(422, 'Subtópico não encontrado.')
        return str(children[indexes[1]])[:500]
    return str(item.get('assunto', '') if isinstance(item, dict) else item)[:500]


def studies_v2_router(db, authenticate, mutate):
    router = APIRouter(prefix='/study/v2')

    async def user(request, token):
        return (await authenticate(authorization=request.headers.get('Authorization'), session_token=token)).user_id

    @router.get('/targets')
    async def targets(request: Request, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        rows = await db.study_targets.find({'user_id': uid}, {'_id': 0}).sort('created_at', -1).to_list(500)
        programs = await db.study_programs.find({'user_id': uid}, {'_id': 0, 'program_id': 1, 'name': 1, 'target_date': 1, 'source_type': 1}).to_list(500)
        linked = {t.get('program_id') for t in rows}
        # Virtual legacy identities preserve all existing data; no write-on-read migration.
        return rows + [{'target_id': 'program:' + p['program_id'], 'program_id': p['program_id'], 'name': p.get('name', ''),
                        'kind': 'contest' if p.get('source_type') == 'edital_import' else 'custom',
                        'exam_date': p.get('target_date'), 'legacy': True, 'provenance': 'extracted' if p.get('source_type') == 'edital_import' else 'user_provided'}
                       for p in programs if p['program_id'] not in linked]

    @router.get('/today')
    async def today_view(request: Request, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        day = datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
        plans = await db.study_dated_plans.find({'user_id': uid}, {'_id': 0, 'program_id': 1, 'entries': 1}).to_list(100)
        entries = [{**e, 'program_id': p['program_id']} for p in plans for e in p.get('entries', []) if e.get('date') == day]
        pending = [e for e in entries if not e.get('completed')]
        sessions = await db.study_sessions.find({'user_id': uid, 'date': day}, {'duration_minutes': 1}).to_list(1000)
        focus = await db.focus_sessions.find({'user_id': uid, 'date': day}, {'focus_minutes': 1}).to_list(1000)
        return {'date': day, 'next_session': pending[0] if pending else None, 'pending': pending[:20],
                'planned_minutes': sum(e.get('minutes', 0) for e in entries),
                'studied_minutes': sum(s.get('duration_minutes', 0) for s in sessions) + sum(s.get('focus_minutes', 0) for s in focus)}

    async def owned_program(uid, program_id, session=None):
        result = await db.study_programs.find_one({'user_id': uid, 'program_id': program_id}, {'_id': 0}, session=session)
        if not result: raise HTTPException(404, 'Programa não encontrado.')
        return result

    @router.get('/programs/{program_id}/blueprint')
    async def get_blueprint(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        await owned_program(uid, program_id)
        from study_blueprint import blueprint
        notebooks = await db.notebooks.find({'user_id': uid, 'program_id': program_id}, {'_id': 0}).to_list(200)
        return blueprint(notebooks)

    @router.post('/programs/{program_id}/blueprint/simulado')
    async def create_blueprint_exam(request: Request, program_id: str, body: BlueprintInput, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        if not request.headers.get('Idempotency-Key'): raise HTTPException(422, 'Idempotency-Key obrigatório.')
        async def apply(session, balance):
            program = await owned_program(uid, program_id, session)
            from study_blueprint import blueprint, assemble
            notebooks = await db.notebooks.find({'user_id': uid, 'program_id': program_id}, {'_id': 0}, session=session).to_list(200)
            plan = blueprint(notebooks)
            if not plan['complete'] or not 1 <= plan['total'] <= 200:
                raise HTTPException(422, 'Distribuição incompleta ou fora do limite de 1 a 200 questões. Confira a análise do edital.')
            exams = await db.simulados.find({'user_id': uid, 'program_id': program_id}, {'_id': 0}, session=session).to_list(200)
            questions = assemble(plan['distribution'], exams, request.headers['Idempotency-Key'])
            # Only retain a stable topic key if it belongs to the selected notebook.
            for question in questions:
                nb = next(n for n in notebooks if n['notebook_id'] == question['notebook_id'])
                topic = question.get('topic_key')
                if topic is None or not isinstance(topic, str): question.pop('topic_key', None)
                else:
                    import re
                    try:
                        if not re.fullmatch(r'\d+(?:_\d+)?', topic): raise HTTPException(422)
                        topic_title(nb, topic)
                    except HTTPException: question.pop('topic_key', None)
            doc = {'simulado_id': 'sim_' + uuid4().hex, 'user_id': uid, 'program_id': program_id, 'area_id': program.get('area_id'),
                   'title': body.title, 'description': 'Montado com questões existentes conforme a distribuição extraída do edital.',
                   'source_type': 'edital_blueprint', 'questions': questions, 'total_questions': len(questions), 'question_type': 'misto',
                   'duration_minutes': body.duration_minutes, 'duration_provenance': 'user_provided', 'blueprint': plan, 'created_at': datetime.now(timezone.utc).isoformat()}
            await db.simulados.insert_one(dict(doc), session=session)
            return doc
        return await mutate(uid, request.headers.get('Idempotency-Key'), ['blueprint-simulado', program_id, body.model_dump()], apply)

    @router.post('/targets')
    async def create_target(request: Request, body: TargetInput, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        if not request.headers.get('Idempotency-Key'): raise HTTPException(422, 'Idempotency-Key obrigatório.')
        if not body.name.strip(): raise HTTPException(422, 'Informe o nome.')
        async def apply(session, balance):
            program_id = body.program_id
            if program_id:
                if not await db.study_programs.find_one({'user_id': uid, 'program_id': program_id}, session=session):
                    raise HTTPException(404, 'Programa não encontrado.')
                existing = await db.study_targets.find_one({'user_id': uid, 'program_id': program_id}, {'_id': 0}, session=session)
                if existing: return existing
            else:
                program_id, area_id = 'prog_' + uuid4().hex, 'area_' + uuid4().hex
                now = datetime.now(timezone.utc).isoformat()
                await db.study_areas.insert_one({'user_id': uid, 'area_id': area_id, 'name': body.name.strip(), 'icon': 'book', 'color': '#ad9bff', 'created_at': now}, session=session)
                await db.study_programs.insert_one({'user_id': uid, 'program_id': program_id, 'area_id': area_id, 'name': body.name.strip(), 'target_date': body.exam_date.isoformat() if body.exam_date else None, 'status': 'active', 'created_at': now}, session=session)
            data = {**body.model_dump(mode='json'), 'name': body.name.strip(), 'program_id': program_id,
                    'target_id': 'target_' + uuid4().hex, 'user_id': uid, 'provenance': 'user_provided', 'created_at': datetime.now(timezone.utc).isoformat()}
            await db.study_targets.insert_one(dict(data), session=session)
            return data
        return await mutate(uid, request.headers.get('Idempotency-Key'), ['create-study-target', body.model_dump(mode='json')], apply)

    @router.post('/attempts')
    async def record_attempt(request: Request, body: AttemptInput, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        if not request.headers.get('Idempotency-Key'): raise HTTPException(422, 'Idempotency-Key obrigatório.')
        async def apply(session, balance):
            notebook = await db.notebooks.find_one({'user_id': uid, 'notebook_id': body.notebook_id}, session=session)
            if not notebook: raise HTTPException(404, 'Matéria não encontrada.')
            title = topic_title(notebook, body.topic_key)
            now = datetime.now(timezone.utc).isoformat()
            day = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
            own = {'user_id': uid, 'notebook_id': body.notebook_id, 'topic_key': body.topic_key}
            row = {**body.model_dump(), **own, 'program_id': notebook.get('program_id'), 'title': title,
                   'attempt_id': 'attempt_' + uuid4().hex, 'date': day.isoformat(), 'created_at': now,
                   'error_reason': None if body.correct else body.error_reason}
            evidence = await db.study_attempts.find(own, {'_id': 0}, session=session).sort('created_at', -1).to_list(499)
            evidence.append(row)
            review = adaptive_review(evidence, day, difficulty=body.difficulty)
            await db.study_attempts.insert_one(dict(row), session=session)
            await db.question_logs.insert_one({**own, 'program_id': notebook.get('program_id'), 'log_id': row['attempt_id'], 'total': 1, 'correct': int(body.correct), 'incorrect': int(not body.correct), 'source': 'individual_attempt', 'date': day.isoformat(), 'created_at': now}, session=session)
            await db.notebooks.update_one({'user_id': uid, 'notebook_id': body.notebook_id}, {'$inc': {'total_questions': 1, 'correct_questions': int(body.correct)}}, session=session)
            from hashlib import sha256
            review_id = sha256(f'{uid}:{body.notebook_id}:{body.topic_key}'.encode()).hexdigest()
            await db.study_topic_reviews.update_one({'_id': review_id}, {'$set': {**own, 'program_id': notebook.get('program_id'), 'title': title,
                'due_date': review['due_date'], 'reason': review['reason'], 'total': len(evidence), 'correct': sum(r['correct'] for r in evidence),
                'accuracy': review['mastery']['accuracy'], 'date': day.isoformat(), 'mastery': review['mastery']}}, upsert=True, session=session)
            return {**row, 'review': review}
        return await mutate(uid, request.headers.get('Idempotency-Key'), ['study-attempt', body.model_dump()], apply)

    @router.patch('/attempts/{attempt_id}/error')
    async def classify_error(request: Request, attempt_id: str, body: ErrorUpdate, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        result = await db.study_attempts.update_one({'user_id': uid, 'attempt_id': attempt_id, 'correct': False}, {'$set': {'error_reason': body.reason}})
        if not result.matched_count: raise HTTPException(404, 'Erro não encontrado.')
        return {'reason': body.reason}

    @router.get('/performance')
    async def performance(request: Request, program_id: Optional[str] = None, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        own = {'user_id': uid}
        if program_id:
            if not await db.study_programs.find_one({**own, 'program_id': program_id}): raise HTTPException(404, 'Programa não encontrado.')
            own['program_id'] = program_id
        rows = await db.study_attempts.find(own, {'_id': 0}).sort('created_at', -1).to_list(5000)
        groups = defaultdict(list)
        for r in rows: groups[(r['notebook_id'], r['topic_key'])].append(r)
        day = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        topics = [{'notebook_id': key[0], 'topic_key': key[1], 'title': evidence[0]['title'], **mastery(evidence, day)} for key, evidence in groups.items()]
        errors = [r for r in rows if not r['correct']]
        days = defaultdict(lambda: {'total': 0, 'correct': 0})
        for row in rows:
            days[row['date'][:10]]['total'] += 1
            days[row['date'][:10]]['correct'] += int(row['correct'])
        trend = [{'date': day, **counts, 'accuracy': round(100 * counts['correct'] / counts['total'], 1)} for day, counts in sorted(days.items())[-30:]]
        return {'topics': topics, 'summary': mastery(rows, day), 'error_causes': dict(Counter(r.get('error_reason') or 'unclassified' for r in errors)),
                'errors': errors[:100], 'trend': trend, 'truncated': len(rows) == 5000, 'sample_limit': 5000}

    @router.get('/library')
    async def library(request: Request, program_id: Optional[str] = None, notebook_id: Optional[str] = None, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        own = {'user_id': uid}
        if program_id: await owned_program(uid, program_id)
        notebooks = await db.notebooks.find({**own, **({'program_id': program_id} if program_id else {}), **({'notebook_id': notebook_id} if notebook_id else {})}, {'_id': 0, 'notebook_id': 1, 'program_id': 1, 'name': 1}).to_list(500)
        ids = [n['notebook_id'] for n in notebooks]
        scope = {**own, 'notebook_id': {'$in': ids}}
        rows = []
        for collection, kind, id_field, title_field, content_field in [('study_notes', 'note', 'note_id', 'title', 'content'), ('study_drafts', 'summary', 'topic_key', 'topic_key', 'text'), ('flashcards', 'flashcard', 'flashcard_id', 'front', 'back')]:
            documents = await db[collection].find(scope, {'_id': 0}).to_list(300)
            for doc in documents:
                rows.append({'id': f"{kind}:{doc.get('notebook_id')}:{doc.get(id_field)}", 'kind': kind, 'title': str(doc.get(title_field) or 'Anotação')[:200],
                             'excerpt': str(doc.get(content_field) or '')[:1500], 'notebook_id': doc.get('notebook_id'), 'topic_key': doc.get('topic_key'), 'provenance': 'user_provided'})
                for link in doc.get('links', [])[:30]:
                    url = str(link.get('url', ''))
                    if url.startswith('https://'):
                        rows.append({'id': f'link:{len(rows)}', 'kind': 'link', 'title': str(link.get('title') or url)[:200], 'url': url, 'notebook_id': doc.get('notebook_id'), 'provenance': 'external'})
        if not program_id and not notebook_id:
            attachments = await db.ai_attachments.find(own, {'_id': 0}).to_list(100)
            rows.extend({'id': a['attachment_id'], 'kind': 'file', 'title': a.get('filename', 'Arquivo'), 'attachment_id': a['attachment_id'], 'provenance': a.get('provenance', 'extracted')} for a in attachments)
            editais = await db.edital_analyses.find(own, {'_id': 0, 'analysis_id': 1, 'pdf_filename': 1}).to_list(100)
            rows.extend({'id': a['analysis_id'], 'kind': 'edital', 'title': a.get('pdf_filename', 'Edital'), 'analysis_id': a['analysis_id'], 'provenance': 'extracted'} for a in editais)
        return {'items': rows[:1000], 'notebooks': notebooks, 'truncated': len(rows) >= 1000, 'scope': 'materiais indexados e notas; fontes externas identificadas separadamente'}

    @router.get('/programs/{program_id}/recommendations')
    async def recommendations(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        program = await owned_program(uid, program_id)
        from study_mastery import topic_priority
        own = {'user_id': uid, 'program_id': program_id}
        notebooks = await db.notebooks.find(own, {'_id': 0}).to_list(200)
        attempts = await db.study_attempts.find(own, {'_id': 0}).sort('created_at', -1).to_list(5000)
        reviews = await db.study_topic_reviews.find(own, {'_id': 0}).to_list(1000)
        progress = await db.topic_progress.find({'user_id': uid, 'notebook_id': {'$in': [n['notebook_id'] for n in notebooks]}}, {'_id': 0}).to_list(200)
        studied = {p['notebook_id']: p.get('topics', {}) for p in progress}
        groups = defaultdict(list)
        for a in attempts: groups[(a['notebook_id'], a['topic_key'])].append(a)
        day = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        overdue = {(r['notebook_id'], r['topic_key']) for r in reviews if r.get('due_date', '9999') <= day.isoformat()}
        try: days_left = (date.fromisoformat(str(program.get('target_date'))[:10]) - day).days
        except ValueError: days_left = None
        suggestions = []
        for nb in notebooks:
            topics = nb.get('conteudo_programatico') or nb.get('topicos') or []
            for i, topic in enumerate(topics):
                key = str(i)
                evidence = groups[(nb['notebook_id'], key)]
                estimate = mastery(evidence, day)
                priority = topic_priority(weight=nb.get('weight'), question_count=nb.get('num_questoes_edital'), estimate=estimate['score'],
                    errors=sum(not e['correct'] for e in evidence), overdue=(nb['notebook_id'], key) in overdue,
                    studied=bool(studied.get(nb['notebook_id'], {}).get(key, {}).get('studied')), days_left=days_left)
                suggestions.append({'notebook_id': nb['notebook_id'], 'topic_key': key, 'title': topic.get('assunto', '') if isinstance(topic, dict) else str(topic),
                    'discipline': nb.get('name'), 'mastery': estimate, **priority})
        return {'items': sorted(suggestions, key=lambda r: (-r['priority'], r['title']))[:10], 'requires_confirmation': True,
                'notice': 'Sugestões calculadas com pesos registrados, respostas e revisões. O plano atual não foi alterado.'}

    @router.get('/programs/{program_id}/overview')
    async def overview(request: Request, program_id: str, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        program = await owned_program(uid, program_id)
        own = {'user_id': uid, 'program_id': program_id}
        target = await db.study_targets.find_one(own, {'_id': 0}) or {}
        notebooks = await db.notebooks.find(own, {'_id': 0}).to_list(200)
        progress = await db.topic_progress.find({'user_id': uid, 'notebook_id': {'$in': [n['notebook_id'] for n in notebooks]}}, {'_id': 0}).to_list(200)
        by_notebook = {p['notebook_id']: p.get('topics', {}) for p in progress}
        total = covered = 0
        for nb in notebooks:
            for i, topic in enumerate(nb.get('conteudo_programatico') or nb.get('topicos') or []):
                keys = [str(i)] + [f'{i}_{j}' for j, _ in enumerate(topic.get('subtopicos', []))] if isinstance(topic, dict) else [str(i)]
                total += len(keys)
                covered += sum(bool(by_notebook.get(nb['notebook_id'], {}).get(key, {}).get('studied')) for key in keys)
        attempts = await db.study_attempts.find(own, {'_id': 0}).sort('created_at', -1).to_list(5000)
        day = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        from dashboard_service import aggregate_one
        counts = await aggregate_one(db.question_logs, own, {'total': {'$sum': '$total'}, 'correct': {'$sum': '$correct'}})
        groups = defaultdict(list)
        for a in attempts: groups[(a['notebook_id'], a['topic_key'])].append(a)
        topics = [{'title': rows[0]['title'], 'notebook_id': key[0], 'topic_key': key[1], **mastery(rows, day)} for key, rows in groups.items()]
        plan = await db.study_dated_plans.find_one(own, {'_id': 0}) or {}
        upcoming = sorted([e for e in plan.get('entries', []) if not e.get('completed') and e.get('date', '') >= day.isoformat()], key=lambda e: e['date'])
        target_date = target.get('exam_date') or program.get('target_date')
        try: remaining = (date.fromisoformat(str(target_date)[:10]) - day).days
        except ValueError: remaining = None
        return {'target': target, 'target_date': target_date, 'days_remaining': remaining, 'coverage': {'studied': covered, 'total': total, 'percent': round(100 * covered / total) if total else None},
            'mastery': mastery(attempts, day), 'questions': counts.get('total', 0), 'accuracy': round(100 * counts.get('correct', 0) / counts['total'], 1) if counts.get('total') else None,
            'study_minutes': sum(n.get('total_study_time_minutes', 0) for n in notebooks), 'weakest': min(topics, key=lambda t: t['score']) if topics else None,
            'next_session': upcoming[0] if upcoming else None}

    @router.get('/reviews')
    async def reviews(request: Request, program_id: Optional[str] = None, session_token: Optional[str] = Cookie(None)):
        uid = await user(request, session_token)
        own = {'user_id': uid}
        if program_id:
            if not await db.study_programs.find_one({**own, 'program_id': program_id}): raise HTTPException(404, 'Programa não encontrado.')
            own['program_id'] = program_id
        day = datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
        rows = await db.study_topic_reviews.find({**own, 'due_date': {'$lte': day}}, {'_id': 0}).sort('due_date', 1).to_list(300)
        queue = [{**r, 'kind': 'topic', 'reason': r.get('reason') or f"{r.get('accuracy', 0)}% de acertos; revisão prevista para {r['due_date']}"} for r in rows]
        due_topics = {(r['notebook_id'], r['topic_key']): r['due_date'] for r in rows}
        recent = await db.study_attempts.find(own, {'_id': 0}).sort('created_at', -1).to_list(2000)
        seen = set()
        for attempt in recent:
            key = (attempt['notebook_id'], attempt['topic_key'], attempt.get('question_id') or attempt.get('question'))
            if key in seen: continue
            seen.add(key)
            due_date = due_topics.get(key[:2])
            if attempt.get('correct') is False and due_date:
                queue.append({**attempt, 'kind': 'wrong_question', 'due_date': due_date, 'reason': 'Última resposta incorreta; refaça a questão e revise o assunto.'})
                if sum(r['kind'] == 'wrong_question' for r in queue) >= 100: break
        notebooks = await db.notebooks.find(own, {'notebook_id': 1}).to_list(500)
        ids = [n['notebook_id'] for n in notebooks]
        cards = await db.flashcards.find({'user_id': uid, 'notebook_id': {'$in': ids}, 'next_review': {'$lte': day}}, {'_id': 0}).sort('next_review', 1).to_list(100)
        queue.extend({'kind': 'flashcard', 'title': c.get('front', c.get('question', 'Flashcard')), 'notebook_id': c['notebook_id'], 'card_id': c.get('flashcard_id'), 'due_date': c['next_review'], 'reason': 'Revisão do cartão agendada para hoje ou antes.'} for c in cards)
        return {'items': sorted(queue, key=lambda r: r['due_date']), 'date': day}

    return router
