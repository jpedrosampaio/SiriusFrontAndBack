"""Operational checks contain no tokens, query strings, prompts or personal data."""
import logging
import time
import uuid
import re
import httpx


class RedactTelegramToken(logging.Filter):
    """Keep logging argument contracts while removing transport URL credentials."""
    def filter(self,record):
        def clean(value):
            if isinstance(value,tuple):return tuple(clean(item) for item in value)
            if isinstance(value,dict):return {key:clean(item) for key,item in value.items()}
            if isinstance(value,httpx.URL):value=str(value)
            if not isinstance(value,str):return value
            value=re.sub(r'(api\.telegram\.org/bot)[^/\s]+',r'\1[redacted]',value)
            value=re.sub(r'(https?://)[^/\s]+@',r'\1[redacted]@',value)
            return re.sub(r'\?[^\s\"\']*','?[redacted]',value)
        record.msg=clean(record.msg)
        record.args=clean(record.args)
        return True


logging.getLogger('httpx').addFilter(RedactTelegramToken())
logging.getLogger('uvicorn.access').addFilter(RedactTelegramToken())
# Transport DEBUG traces can include headers; business diagnostics remain enabled.
logging.getLogger('httpcore').setLevel(logging.WARNING)
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
