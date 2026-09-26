import httpx
from ai.types import AIError

_client = None


def http_client():
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(follow_redirects=False)
    return _client


async def close():
    global _client
    if _client:
        await _client.aclose()
    _client = None


class Provider:
    def __init__(self, transport=None):
        self.transport = transport

    async def request(self, method, url, **kwargs):
        try:
            response = await getattr(self.transport or http_client(), method)(url, **kwargs)
        except httpx.TimeoutException as exc:
            raise AIError('timeout') from exc
        except httpx.HTTPError as exc:
            raise AIError('unavailable') from exc
        if response.status_code >= 400:
            kind = {400: 'invalid_request', 401: 'invalid_key', 403: 'invalid_key',
                    404: 'unavailable', 408: 'timeout', 429: 'rate_limit'}.get(response.status_code, 'unavailable' if response.status_code >= 500 else 'provider_error')
            if response.status_code == 429 and 'quota' in response.text.lower():
                kind = 'quota'
            retry = response.headers.get('retry-after', '30')
            raise AIError(kind, int(retry) if retry.isdigit() else 30)
        try:
            return response.json()
        except ValueError as exc:
            raise AIError('malformed_output') from exc

    async def generate(self, model, key, request):
        raise AIError('unavailable')

    async def generate_structured(self, model, key, request):
        return await self.generate(model, key, request)

    async def generate_with_tools(self, model, key, request):
        return await self.generate(model, key, request)

    async def embed(self, model, key, request):
        raise AIError('unavailable')

    async def transcribe(self, model, key, request):
        raise AIError('unavailable')

    async def synthesize_speech(self, model, key, request):
        raise AIError('unavailable')

    async def healthcheck(self, key):
        # Configuration health is honest: no hidden quota-consuming generation.
        return {'configured': bool(key), 'live_checked': False}
