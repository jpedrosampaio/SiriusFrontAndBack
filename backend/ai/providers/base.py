import httpx
from ai.types import AIError
from ai.provider_diagnostics import rejection_metadata

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
            raise AIError('network_error') from exc
        if response.status_code >= 400:
            incompatibility=None
            provider_rejection=None
            kind = {400: 'invalid_request', 401: 'invalid_key', 403: 'permission_denied',
                    404: 'model_unavailable', 408: 'timeout', 429: 'rate_limit'}.get(response.status_code, 'unavailable' if response.status_code >= 500 else 'provider_error')
            if response.status_code == 400:
                try:
                    error=response.json().get('error',{})
                    provider_rejection=rejection_metadata(error)
                    details = error.get('details', [])
                    if any(d.get('reason') == 'API_KEY_INVALID' for d in details if isinstance(d, dict)):
                        kind = 'invalid_key'
                    if kind=='invalid_request':
                        # Inspect bounded text only to choose an enum. Never
                        # retain/log field paths, response bodies or messages.
                        message=str(error.get('message',''))[:4096].lower()
                        fields=' '.join(str(v.get('field',''))[:256] for d in details if isinstance(d,dict)
                            for v in d.get('fieldViolations',[]) if isinstance(v,dict))[:4096].lower()
                        combined=message+' '+fields
                        format_field=any(word in combined for word in ('responseformat','response_format'))
                        if message.startswith('invalid json schema for response_format:') and '[discriminator_multiple_candidates]' in message:
                            incompatibility='schema_discriminator'
                        elif format_field and any(word in combined for word in ('mimetype','mime_type','application_json')):
                            incompatibility='format_mime'
                        elif format_field and any(word in combined for word in ('unknown name','unknown field','unsupported field','not supported')):
                            incompatibility='format_field'
                        elif any(word in combined for word in ('responsejsonschema','response_json_schema','json_schema','schema')):
                            incompatibility='schema_complexity' if any(w in combined for w in ('too complex','too many states','too deeply','too large')) else 'schema_reference' if '$ref' in combined or 'reference' in combined else 'schema_keyword' if any(w in combined for w in ('unsupported keyword','unknown name','additionalproperties','default','pattern')) else 'schema_rejected'
                        elif 'model' in combined and any(w in combined for w in ('does not support','not supported by','unsupported model')):
                            incompatibility='model_capability'
                        else:incompatibility='request_rejected'
                except (ValueError, AttributeError,TypeError):
                    pass
            if response.status_code == 429 and 'quota' in response.text.lower():
                kind = 'quota'
            retry = response.headers.get('retry-after', '30')
            raise AIError(kind, int(retry) if retry.isdigit() else 30, http_status=response.status_code,
                incompatibility=incompatibility,reason='payload_rejected' if kind=='invalid_request' else None,
                provider_rejection=provider_rejection)
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise AIError('malformed_output')
            return data
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
