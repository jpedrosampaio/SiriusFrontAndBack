"""Deterministic grading and atomic evidence ingestion for owned simulations."""
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from study_mastery import adaptive_review


def grade(questions, answers):
    if not questions or len(questions) > 500: raise HTTPException(422, 'Simulado sem questões válidas ou acima do limite.')
    selected = {}
    for answer in answers:
        index = answer.get('question_idx')
        value = answer.get('selected_answer')
        if type(index) is not int or not 0 <= index < len(questions) or index in selected or not isinstance(value, str) or len(value) > 100:
            raise HTTPException(422, 'Respostas duplicadas ou inválidas.')
        selected[index] = value.strip()
    results, disciplines, topics = [], defaultdict(lambda: {'total': 0, 'correct': 0}), defaultdict(lambda: {'total': 0, 'correct': 0})
    earned = total_weight = 0
    for index, q in enumerate(questions):
        expected = str(q.get('correct_answer') or '').strip()
        if not expected: raise HTTPException(422, 'Uma questão não tem gabarito. Confira a prova antes de responder.')
        answer = selected.get(index, '')
        correct = bool(answer) and answer.upper() == expected.upper()
        weight = max(.1, min(float(q.get('weight') or 1), 100))
        total_weight += weight
        if correct: earned += weight
        disc = q.get('disciplina') or 'Geral'
        topic = q.get('subdisciplina') or 'Sem tópico vinculado'
        for counter, key in [(disciplines, disc), (topics, topic)]:
            counter[key]['total'] += 1
            counter[key]['correct'] += int(correct)
        results.append({'question_idx': index, 'question_number': q.get('question_number', index + 1), 'selected_answer': answer,
                        'correct_answer': expected, 'is_correct': correct, 'answered': bool(answer), 'explanation': q.get('explanation', ''),
                        'disciplina': disc, 'topic': topic, 'weight': weight})
    for counter in (disciplines, topics):
        for v in counter.values(): v['accuracy'] = round(v['correct'] / v['total'] * 100, 1)
    return {'answers': results, 'correct_count': sum(r['is_correct'] for r in results), 'total_questions': len(questions),
            'total_answered': sum(r['answered'] for r in results), 'unanswered': sum(not r['answered'] for r in results),
            'score': round(100 * earned / total_weight, 1), 'accuracy': round(100 * sum(r['is_correct'] for r in results) / len(questions), 1),
            'by_disciplina': dict(disciplines), 'by_topic': dict(topics), 'score_basis': 'all_questions_weighted'}


async def submit_exam(db, user_id, simulado_id, submission, request, mutate, award_xp, update_streak):
    key = request.headers.get('Idempotency-Key')
    if not key: raise HTTPException(422, 'Idempotency-Key obrigatório para concluir o simulado.')
    async def apply(session, balance):
        own = {'user_id': user_id}
        exam = await db.simulados.find_one({**own, 'simulado_id': simulado_id}, {'_id': 0}, session=session)
        if not exam: raise HTTPException(404, 'Simulado não encontrado.')
        questions = exam.get('questions', [])
        result = grade(questions, submission.answers)
        previous = await db.simulado_attempts.find_one({**own, 'simulado_id': simulado_id}, sort=[('completed_at', -1)], session=session)
        now = datetime.now(timezone.utc).isoformat()
        day = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        attempt_id = 'sattempt_' + uuid4().hex
        doc = {**own, **result, 'attempt_id': attempt_id, 'simulado_id': simulado_id, 'title': exam.get('title', ''),
               'program_id': exam.get('program_id'), 'banca': exam.get('banca'), 'disciplina': exam.get('disciplina'), 'concurso': exam.get('concurso'),
               'time_spent_seconds': submission.time_spent_seconds, 'completed_at': now,
               'change_since_previous': round(result['score'] - previous['score'], 1) if previous else None}
        grouped = defaultdict(list)
        for answer in result['answers']:
            q = questions[answer['question_idx']]
            notebook_id, topic_key = q.get('notebook_id'), q.get('topic_key')
            if not answer['answered'] or not notebook_id or topic_key is None: continue
            notebook = await db.notebooks.find_one({**own, 'notebook_id': notebook_id, 'program_id': exam.get('program_id')}, session=session)
            if not notebook: continue
            from studies_v2 import topic_title
            import re
            if not re.fullmatch(r'\d+(?:_\d+)?', str(topic_key)): continue
            try: title = topic_title(notebook, str(topic_key))
            except HTTPException: continue  # Old questions without a stable match never invent one.
            evidence = {**own, 'attempt_id': f"{attempt_id}:{answer['question_idx']}", 'simulado_id': simulado_id, 'exam': exam.get('title', ''),
                'notebook_id': notebook_id, 'program_id': exam.get('program_id'), 'topic_key': str(topic_key), 'title': title,
                'question': str(q.get('question_text', ''))[:12000], 'answer': answer['selected_answer'], 'correct': answer['is_correct'],
                'board': exam.get('banca'), 'source': 'simulado', 'date': day.isoformat(), 'created_at': now, 'seconds': None, 'error_reason': None}
            await db.study_attempts.insert_one(dict(evidence), session=session)
            grouped[(notebook_id, str(topic_key))].append(evidence)
        for (notebook_id, topic_key), records in grouped.items():
            from hashlib import sha256
            topic_own = {**own, 'notebook_id': notebook_id, 'topic_key': topic_key}
            history = await db.study_attempts.find(topic_own, {'_id': 0}, session=session).sort('created_at', -1).to_list(500)
            review = adaptive_review(history, day)
            await db.study_topic_reviews.update_one({'_id': sha256(f'{user_id}:{notebook_id}:{topic_key}'.encode()).hexdigest()}, {'$set': {
                **topic_own, 'program_id': exam.get('program_id'), 'title': records[0]['title'], 'date': day.isoformat(),
                'due_date': review['due_date'], 'reason': review['reason'], 'mastery': review['mastery'], 'total': len(history),
                'correct': sum(r['correct'] for r in history), 'accuracy': review['mastery']['accuracy']}}, upsert=True, session=session)
            await db.notebooks.update_one({**own, 'notebook_id': notebook_id}, {'$inc': {'total_questions': len(records), 'correct_questions': sum(r['correct'] for r in records)}}, session=session)
        doc['mastery_answers_linked'] = sum(len(r) for r in grouped.values())
        doc['xp_earned'] = result['correct_count'] * 2
        doc['new_xp'], _ = await award_xp(user_id, doc['xp_earned'], session=session)
        await update_streak(user_id, session=session)
        await db.simulado_attempts.insert_one(dict(doc), session=session)
        await db.question_logs.insert_one({**own, 'log_id': attempt_id, 'simulado_id': simulado_id, 'program_id': exam.get('program_id'),
            'notebook_id': None, 'total': result['total_answered'], 'correct': result['correct_count'], 'source': 'simulado',
            'banca': exam.get('banca'), 'disciplina': exam.get('disciplina'), 'concurso': exam.get('concurso'), 'date': day.isoformat(), 'created_at': now}, session=session)
        return doc
    return await mutate(user_id, key, ['submit-simulado', simulado_id, submission.model_dump()], apply)
