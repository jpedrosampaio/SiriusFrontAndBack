"""Operational checks contain no tokens, query strings, prompts or personal data."""
import logging
import time
import uuid
import re


class RedactTelegramToken(logging.Filter):
    def filter(self,record):
        message=record.getMessage()
        clean=re.sub(r'(api\.telegram\.org/bot)[^/\s]+',r'\1[redacted]',message)
        if clean!=message:record.msg=clean;record.args=()
        return True


logging.getLogger('httpx').addFilter(RedactTelegramToken())
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
