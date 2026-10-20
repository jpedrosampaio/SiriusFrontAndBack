import json
import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import replace
from hashlib import sha256
from uuid import UUID,uuid4
from jsonschema import Draft202012Validator, ValidationError, SchemaError
from pydantic import BaseModel
from ai.config import Settings
from ai.types import AIRequest, AIError
from ai.providers.gemini import GeminiProvider
from ai.providers.groq import GroqProvider
from ai.schemas import transport_schema,TRANSPORT_VERSION


def normalize_schema(value):
    if isinstance(value, list):
        return [normalize_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: ({name: normalize_schema(child) for name, child in v.items()}
                  if k in ('properties', '$defs', 'definitions', 'patternProperties') and isinstance(v,dict)
                  else v if k in ('enum', 'const', 'default', 'examples') else normalize_schema(v))
              for k, v in value.items() if k not in ('propertyOrdering', 'nullable')}
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
        self.cooldown_errors = {}
        self.reserve = reserve
        self.rejections=OrderedDict()

    async def generate(self, *, task, keys, user_id='', prompt='', system='', schema=None, output_type=None, on_attempt=None, diagnostic_context=None, **kwargs):
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
        last_actual = None
        attempted = 0
        excluded = set()
        context=diagnostic_context or {}
        stage=context.get('stage') if context.get('stage') in ('inventory','scope','detail','verify') else None
        try:unit_id=str(UUID(str(context.get('unit_id'))))
        except (ValueError,TypeError,AttributeError):unit_id=None
        for model in self.settings.route(task):
            key = keys.get(model.provider)
            if not key or model.provider in excluded or not required.issubset(model.capabilities):
                continue
            token = (user_id, model.provider, model.name)
            if self.cooldowns.get(token, 0) > time.monotonic():
                last = AIError(self.cooldown_errors.get(token, 'unavailable'),
                    max(1,int(self.cooldowns[token]-time.monotonic())+1),reason='cooldown')
                continue
            adapted=request
            if schema:
                try:adapted=replace(request,transport_schema=transport_schema(schema,model.structured_profile))
                except AIError as error:
                    if error.incompatibility=='model_capability':last=error;continue
                    raise
            fingerprint=(user_id,model.provider,model.name,task,TRANSPORT_VERSION,
                sha256(keys[model.provider].encode()).hexdigest(),sha256(json.dumps(adapted.transport_schema,sort_keys=True).encode()).hexdigest(),
                sha256(json.dumps({'prompt':request.prompt,'system':request.system,'messages':request.messages,
                    'parts':request.parts,'tools':request.tools,'max_tokens':request.max_tokens,'mime':request.mime},
                    sort_keys=True,default=str).encode()).hexdigest())
            rejected=self.rejections.get(fingerprint)
            if rejected and rejected[0]>time.monotonic():
                prior=rejected[1]
                if prior.incompatibility=='model_capability':last=prior;continue
                raise AIError('invalid_request',http_status=prior.http_status,incompatibility=prior.incompatibility,
                    reason='payload_rejected',reference=prior.reference)
            if self.reserve and not await self.reserve(user_id, model):
                last = AIError('quota'); continue
            # Optional durable callers fence/account for each model attempt,
            # including fallback, before any provider IO. No document data/key
            # is passed to this hook and no transaction spans the provider call.
            if on_attempt is not None:
                try:await on_attempt(model)
                except AIError as fence:
                    if fence.kind=='pilot_limit' and last_actual is not None:raise last_actual from None
                    raise
            started = time.perf_counter()
            attempted += 1
            status = 'success'
            result = None
            failure=None;reference=str(uuid4())
            try:
                provider = self.providers[model.provider]
                method = {'embedding': 'embed', 'speech_to_text': 'transcribe', 'text_to_speech': 'synthesize_speech'}.get(task, 'generate_structured' if schema else 'generate_with_tools' if request.tools else 'generate')
                result = await getattr(provider, method)(model, key, adapted)
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
                exc.attempted=True;exc.reference=reference;failure=exc
                last_actual=exc
                last, status = exc, exc.kind
                if exc.kind in ('invalid_key', 'permission_denied'):
                    excluded.add(model.provider)
                if exc.kind == 'invalid_request':
                    # Invalid input/schema must not silently become unvalidated output.
                    # Cache metadata only, never exception tracebacks retaining
                    # private prompts, provider responses or request credentials.
                    cached=AIError(exc.kind,http_status=exc.http_status,incompatibility=exc.incompatibility,
                        reason=exc.reason,reference=exc.reference)
                    self.rejections[fingerprint]=(time.monotonic()+300,cached)
                    while len(self.rejections)>1000:self.rejections.popitem(last=False)
                    if exc.incompatibility!='model_capability':
                        raise
                if exc.kind in ('quota', 'rate_limit', 'unavailable', 'model_unavailable', 'network_error', 'timeout'):
                    self.cooldowns[token] = time.monotonic() + exc.retry_after
                    self.cooldown_errors[token] = exc.kind
                    while len(self.cooldowns) > 1000:
                        expired, _ = self.cooldowns.popitem(last=False)
                        self.cooldown_errors.pop(expired, None)
            except asyncio.CancelledError:
                status = 'cancelled'
                raise
            except Exception:
                status = 'internal_error'
                raise
            finally:
                logging.info('ai provider=%s model=%s task=%s stage=%s unit=%s reference=%s http_status=%s incompatibility=%s latency_ms=%.1f fallback=%s status=%s tokens=%s', model.provider, model.name, task,stage,unit_id,reference,
                             failure.http_status if failure else None,failure.incompatibility if failure else None,(time.perf_counter()-started)*1000, attempted > 1, status,
                             {k:v for k,v in (result.usage if result else {}).items() if k in ('total_tokens', 'totalTokenCount', 'prompt_tokens', 'completion_tokens')})
        if last_actual is not None:raise last_actual
        if not attempted and last.reason is None:last.reason='no_compatible_route'
        raise last
