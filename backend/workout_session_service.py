"""Workout mutations run inside the same transaction as their XP and receipts."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
from fastapi import HTTPException

async def start_session(db, user, body, mongo_session):
    plan_id = body.get('plan_id')
    day_index = body.get('day_index', 0)
    rest_timer_seconds = body.get('rest_timer_seconds', 60)
    if not plan_id:
        raise HTTPException(status_code=400, detail='plan_id é obrigatório')
    active = await db.workout_sessions.find_one({'user_id': user.user_id, 'status': 'active'}, {'_id': 0}, session=mongo_session)
    if active:
        raise HTTPException(status_code=409, detail='Já existe uma sessão de treino ativa. Finalize ou abandone a sessão atual.')
    plan = await db.workout_plans.find_one({'plan_id': plan_id, 'user_id': user.user_id}, {'_id': 0}, session=mongo_session)
    if not plan:
        raise HTTPException(status_code=404, detail='Plano de treino não encontrado')
    days = plan.get('days') or []
    if type(day_index) is not int or day_index < 0 or (days and day_index >= len(days)) or (not days and day_index != 0):
        raise HTTPException(status_code=422, detail='Dia de treino invalido. Selecione um dia existente.')
    if days:
        session_exercises = days[day_index].get('exercises', [])
        day_label = days[day_index].get('day_label', f'Dia {day_index + 1}')
    else:
        session_exercises = plan.get('exercises', [])
        day_label = plan.get('name', 'Treino')
    exercises = []
    for ex in session_exercises:
        exercises.append({'name': ex.get('name', ''), 'sets': ex.get('sets', 3), 'reps': ex.get('reps', 12), 'weight': ex.get('weight', ''), 'rest_seconds': ex.get('rest_seconds', rest_timer_seconds), 'muscle_group': ex.get('muscle_group', ''), 'tutorial': ex.get('tutorial', ''), 'video_url': ex.get('video_url', ''), 'completed': False, 'sets_completed': 0, 'time_spent_seconds': 0})
    session_id = f'session_{uuid.uuid4().hex[:12]}'
    session_doc = {'session_id': session_id, 'user_id': user.user_id, 'plan_id': plan_id, 'plan_name': f"{plan.get('name', 'Treino')} - {day_label}", 'status': 'active', 'started_at': datetime.now(timezone.utc).isoformat(), 'completed_at': None, 'total_duration_seconds': 0, 'exercises': exercises, 'current_exercise_idx': 0, 'rest_timer_seconds': rest_timer_seconds, 'feedback': None, 'day_index': day_index}
    await db.workout_sessions.insert_one(session_doc, session=mongo_session)
    session_doc.pop('_id', None)
    return session_doc


async def update_exercise(db, user, body, mongo_session, session_id, exercise_idx):
    session = await db.workout_sessions.find_one({'session_id': session_id, 'user_id': user.user_id, 'status': 'active'}, {'_id': 0}, session=mongo_session)
    if not session:
        raise HTTPException(status_code=404, detail='Sessão não encontrada ou já finalizada')
    if 'revision' in body and body['revision'] != session.get('revision', 0):
        raise HTTPException(409, 'O treino mudou em outra tela. Atualize antes de registrar.')
    if 'completed' in body and type(body['completed']) is not bool:
        raise HTTPException(422, 'Estado do exercício inválido')
    exercises = session.get('exercises', [])
    if exercise_idx < 0 or exercise_idx >= len(exercises):
        raise HTTPException(status_code=400, detail='Índice de exercício inválido')
    if 'sets_data' in body and (not isinstance(body['sets_data'], list) or len(body['sets_data']) > int(exercises[exercise_idx].get('sets') or 1) or any(not isinstance(item, dict) for item in body['sets_data'])):
        raise HTTPException(422, 'Quantidade ou registro de séries inválido')
    if 'completed' in body:
        exercises[exercise_idx]['completed'] = body['completed']
    if 'sets_completed' in body:
        exercises[exercise_idx]['sets_completed'] = body['sets_completed']
    if 'sets_data' in body:
        exercises[exercise_idx]['sets_data'] = body['sets_data']
        completed_sets = sum((1 for s in body['sets_data'] if s.get('completed')))
        exercises[exercise_idx]['sets_completed'] = completed_sets
    if 'time_spent_seconds' in body:
        exercises[exercise_idx]['time_spent_seconds'] = body['time_spent_seconds']
    if 'weight' in body:
        exercises[exercise_idx]['weight'] = body['weight']
    if 'sets_data' in body:
        for sd in body['sets_data']:
            if 'rpe' in sd:
                pass
    session['revision'] = session.get('revision', 0) + 1
    update_fields = {'exercises': exercises, 'revision': session['revision']}
    if 'current_exercise_idx' in body:
        update_fields['current_exercise_idx'] = body['current_exercise_idx']
    await db.workout_sessions.update_one({'session_id': session_id}, {'$set': update_fields}, session=mongo_session)
    session['exercises'] = exercises
    if 'current_exercise_idx' in body:
        session['current_exercise_idx'] = body['current_exercise_idx']
    return session


async def complete_session(db, user, body, mongo_session, session_id, award_xp):
    session = await db.workout_sessions.find_one({'session_id': session_id, 'user_id': user.user_id, 'status': 'active'}, {'_id': 0}, session=mongo_session)
    if not session:
        raise HTTPException(status_code=404, detail='Sessão não encontrada ou já finalizada')
    completed_at = datetime.now(timezone.utc).isoformat()
    started_at = session.get('started_at', completed_at)
    start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
    total_duration_seconds = int((end_time - start_time).total_seconds())
    exercises = session.get('exercises', [])
    completed_count = sum((1 for ex in exercises if ex.get('completed')))
    total_count = len(exercises)
    feedback = {'difficulty': body.get('difficulty', 3), 'feeling': body.get('feeling', ''), 'notes': body.get('notes', ''), 'completed_exercises': completed_count, 'total_exercises': total_count}
    base_xp = 10
    exercise_bonus = completed_count * 2
    duration_bonus = total_duration_seconds // 900 * 5
    xp_earned = base_xp + exercise_bonus + duration_bonus
    await db.workout_sessions.update_one({'session_id': session_id}, {'$set': {'status': 'completed', 'completed_at': completed_at, 'total_duration_seconds': total_duration_seconds, 'feedback': feedback}}, session=mongo_session)
    log_id = f'workout_{uuid.uuid4().hex[:12]}'
    duration_minutes = max(1, total_duration_seconds // 60)
    workout_doc = {'log_id': log_id, 'user_id': user.user_id, 'plan_id': session.get('plan_id'), 'activity_type': 'weightlifting', 'name': session.get('plan_name', 'Treino'), 'duration_minutes': duration_minutes, 'calories': int(duration_minutes * 6), 'exercises_completed': [{**ex, 'completed': ex.get('completed', False)} for ex in exercises], 'notes': feedback.get('notes', ''), 'xp_earned': xp_earned, 'completed': True, 'date': datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d'), 'session_id': session_id, 'created_at': completed_at}
    await db.workout_logs.insert_one(workout_doc, session=mongo_session)
    new_xp, new_rank = await award_xp(user.user_id, xp_earned, session=mongo_session)
    return {'success': True, 'session_id': session_id, 'total_duration_seconds': total_duration_seconds, 'total_duration_minutes': duration_minutes, 'completed_exercises': completed_count, 'total_exercises': total_count, 'xp_earned': xp_earned, 'new_xp': new_xp, 'new_rank': new_rank, 'feedback': feedback}


async def abandon_session(db, user, body, mongo_session, session_id):
    result = await db.workout_sessions.update_one({'session_id': session_id, 'user_id': user.user_id, 'status': 'active'}, {'$set': {'status': 'abandoned', 'completed_at': datetime.now(timezone.utc).isoformat()}}, session=mongo_session)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='Sessão não encontrada')
    return {'message': 'Sessão abandonada'}
