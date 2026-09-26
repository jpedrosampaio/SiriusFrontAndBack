import json
import logging
import time
from collections import OrderedDict
from jsonschema import Draft202012Validator, ValidationError, SchemaError
from pydantic import BaseModel
from ai.config import Settings
from ai.types import AIRequest, AIError
from ai.providers.gemini import GeminiProvider
from ai.providers.groq import GroqProvider


def normalize_schema(value):
    if isinstance(value, list):
        return [normalize_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: normalize_schema(v) for k, v in value.items() if k not in ('propertyOrdering', 'nullable')}
    if isinstance(result.get('type'), str):
        result['type'] = result['type'].lower()
        if value.get('nullable'):
            result['type'] = [result['type'], 'null']
    return result


class AIRouter:
    def __init__(self, settings=None, providers=None, reserve=None):
        self.settings = settings or Settings()
        self.providers = providers or {'gemini': GeminiProvider(), 'groq': GroqProvider()}
        self.cooldowns = OrderedDict()
        self.reserve = reserve

    async def generate(self, *, task, keys, user_id='', prompt='', system='', schema=None, output_type=None, **kwargs):
        schema = normalize_schema(output_type.model_json_schema() if output_type else schema)
        if schema:
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                raise AIError('invalid_request') from exc
        request = AIRequest(task=task, prompt=prompt, system=system, schema=schema, **kwargs)
        required = set()
        if task in ('embedding', 'text_to_speech'): required.add(task)
        if task == 'speech_to_text':
            required.add('audio')  # Gemini audio input and Groq transcription adapters.
        for part in request.parts:
            if 'fileData' in part: required.add('files')
            mime = part.get('inlineData', part.get('fileData', {})).get('mimeType', '')
            if mime: required.add('pdf' if mime == 'application/pdf' else 'image' if mime.startswith('image/') else 'audio')
        if schema: required.add('json')
        if request.tools: required.add('tools')
        if request.tools and schema: raise AIError('invalid_request')
        last = AIError('unavailable')
        attempted = 0
        excluded = set()
        for model in self.settings.route(task):
            key = keys.get(model.provider)
            if not key or model.provider in excluded or not required.issubset(model.capabilities):
                continue
            token = (user_id, model.provider, model.name)
            if self.cooldowns.get(token, 0) > time.monotonic():
                continue
            if self.reserve and not await self.reserve(user_id, model):
                last = AIError('quota'); continue
            started = time.perf_counter()
            attempted += 1
            status = 'success'
            result = None
            try:
                provider = self.providers[model.provider]
                method = {'embedding': 'embed', 'speech_to_text': 'transcribe', 'text_to_speech': 'synthesize_speech'}.get(task, 'generate_structured' if schema else 'generate_with_tools' if request.tools else 'generate')
                result = await getattr(provider, method)(model, key, request)
                if schema:
                    try:
                        parsed = json.loads(result.text)
                        Draft202012Validator(schema).validate(parsed)
                        result.data = output_type.model_validate(parsed) if output_type else parsed
                    except (ValueError, ValidationError) as exc:
                        raise AIError('malformed_output') from exc
                result.fallback = attempted > 1
                return result
            except AIError as exc:
                last, status = exc, exc.kind
                if exc.kind == 'invalid_key':
                    excluded.add(model.provider)
                if exc.kind == 'invalid_request':
                    # Invalid input/schema must not silently become unvalidated output.
                    raise
                if exc.kind in ('quota', 'rate_limit', 'unavailable', 'timeout'):
                    self.cooldowns[token] = time.monotonic() + exc.retry_after
                    while len(self.cooldowns) > 1000: self.cooldowns.popitem(last=False)
            finally:
                logging.info('ai provider=%s model=%s task=%s latency_ms=%.1f fallback=%s status=%s tokens=%s', model.provider, model.name, task, (time.perf_counter()-started)*1000, attempted > 1, status,
                             {k:v for k,v in (result.usage if result else {}).items() if k in ('total_tokens', 'totalTokenCount', 'prompt_tokens', 'completion_tokens')})
        raise last
