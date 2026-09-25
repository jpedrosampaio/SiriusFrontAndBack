"""Operational checks contain no tokens, query strings, prompts or personal data."""
import logging
import time
import uuid
from pymongo.errors import OperationFailure


async def ensure_query_indexes(db):
    definitions = {
        'transactions': [('user_id', 1), ('date', -1)],
        'workout_logs': [('user_id', 1), ('date', -1)],
        'workout_sessions': [('user_id', 1), ('status', 1)],
        'focus_sessions': [('user_id', 1), ('date', -1)],
        'study_sessions': [('user_id', 1), ('date', -1)],
        'study_streaks': [('user_id', 1)],
        'task_instances': [('user_id', 1), ('date', 1)],
        'notebooks': [('user_id', 1), ('program_id', 1)],
        'study_schedules': [('user_id', 1), ('program_id', 1)],
        'study_dated_plans': [('user_id', 1)],
        'edital_jobs': [('status', 1), ('created_at', 1)],
        'edital_analyses': [('user_id', 1), ('pdf_hash', 1), ('analysis_version', 1)],
        'flashcards': [('user_id', 1), ('next_review', 1)],
        'question_logs': [('user_id', 1), ('notebook_id', 1)],
        'meals': [('user_id', 1), ('date', 1)],
        'water_logs': [('user_id', 1), ('date', 1)],
    }
    for name, keys in definitions.items():
        try:
            await db[name].create_index(keys)
        except OperationFailure as error:
            # Existing equivalent indexes may use different options/names. Never
            # drop production indexes or make startup depend on index privileges.
            logging.warning('index_check collection=%s code=%s', name, error.code)


def install_request_metrics(app):
    @app.middleware('http')
    async def request_metrics(request, call_next):
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:16]
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers['X-Request-ID'] = request_id
            response.headers['Server-Timing'] = f'app;dur={(time.perf_counter() - started) * 1000:.1f}'
            return response
        finally:
            route = request.scope.get('route')
            logging.info('request id=%s method=%s route=%s status=%s duration_ms=%.1f',
                         request_id, request.method, getattr(route, 'path', 'unmatched'), status,
                         (time.perf_counter() - started) * 1000)
