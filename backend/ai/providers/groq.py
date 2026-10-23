import base64
import json
from hashlib import sha256
from ai.providers.base import Provider
from ai.types import AIError, AIResult
from ai.schemas import transport_schema

BASE = 'https://api.groq.com/openai/v1'


class GroqProvider(Provider):
    async def generate(self, model, key, request):
        messages = ([{'role': 'system', 'content': request.system}] if request.system else []) + list(request.messages)
        content = request.prompt
        if request.parts:
            content = []
            for part in request.parts:
                if 'text' in part:
                    content.append({'type': 'text', 'text': part['text']})
                elif part.get('inlineData', {}).get('mimeType', '').startswith('image/'):
                    image = part['inlineData']
                    content.append({'type': 'image_url', 'image_url': {'url': f"data:{image['mimeType']};base64,{image['data']}"}})
                else:
                    raise AIError('invalid_request')
        messages.append({'role': 'user', 'content': content})
        payload = {'model': model.name, 'messages': messages, 'max_completion_tokens': min(request.max_tokens, 16000)}
        if request.schema:
            # Best effort supports legacy optional fields; local validation is mandatory.
            wire=request.transport_schema if request.transport_schema is not None else transport_schema(request.schema,model.structured_profile)
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'sirius_response', 'strict': False, 'schema': wire}}
        if request.tools:
            payload['tools'] = [{'type': 'function', 'function': t} for t in request.tools]
        try:
            data = await self.request('post', f'{BASE}/chat/completions', headers={'Authorization': f'Bearer {key}'}, json=payload, timeout=request.timeout)
        except AIError as error:
            if request.schema:
                encoded=json.dumps(wire,sort_keys=True,separators=(',',':')).encode()
                error.request_format='groq_json_schema'
                error.schema_sha256=sha256(encoded).hexdigest()
                error.schema_bytes=len(encoded)
            raise
        choice = next(iter(data.get('choices', [])), {})
        if choice.get('finish_reason') == 'length':
            raise AIError('output_truncated')
        if choice.get('finish_reason') == 'content_filter':
            raise AIError('blocked_output')
        message = choice.get('message', {})
        calls = []
        try:
            for call in message.get('tool_calls') or []:
                calls.append({'name': call['function']['name'], 'arguments': json.loads(call['function']['arguments'])})
        except (ValueError, KeyError) as exc:
            raise AIError('malformed_output') from exc
        text = message.get('content') or ''
        if not text and not calls:
            raise AIError('empty_output')
        return AIResult(text, 'groq', model.name, data.get('usage', {}), tool_calls=calls)

    async def transcribe(self, model, key, request):
        data = await self.request('post', f'{BASE}/audio/transcriptions', headers={'Authorization': f'Bearer {key}'},
                                  files={'file': ('voice.webm', request.audio, request.mime)}, data={'model': model.name, 'language': 'pt', 'response_format': 'json'}, timeout=request.timeout)
        if not data.get('text'):
            raise AIError('malformed_output')
        return AIResult(data['text'], 'groq', model.name)
