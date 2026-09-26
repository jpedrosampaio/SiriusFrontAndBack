"""Compatibility facade. Provider HTTP and model selection live in ai/."""
import asyncio
import base64
from ai.providers.base import http_client, close
from ai.providers.gemini import GeminiProvider
from ai.router import AIRouter
from ai.types import AIError

_router = None


def configure(router):
    global _router
    _router = router


async def call_gemini(prompt, system_message, api_key, timeout_override=None, user_id=None, response_schema=None, usage_callback=None, parts=None, config_options=None, task='structured_extraction', keys=None):
    router = _router or AIRouter(providers={'gemini': GeminiProvider(http_client())})
    options = config_options or {}
    schema = response_schema
    if schema is None and options.get('responseMimeType') == 'application/json':
        schema = {'type': ['object', 'array']}
    try:
        result = await router.generate(task=task, keys=keys or {'gemini': api_key}, user_id=user_id or '', prompt=prompt, system=system_message,
            schema=schema, parts=parts or [], timeout=timeout_override or 90, max_tokens=options.get('maxOutputTokens', 8192))
        if usage_callback:
            await usage_callback(user_id, result.model, usage=result.usage, feature=task)
        return result.text, None
    except AIError as error:
        return None, {'rate_limit': 'quota', 'quota': 'quota', 'invalid_key': 'invalid', 'invalid_request': 'invalid', 'timeout': 'timeout'}.get(error.kind, 'other')


async def upload_to_gemini(content, api_key, mime_type='application/pdf'):
    try:
        return await GeminiProvider(http_client()).upload(content, api_key, mime_type)
    except AIError:
        return None


async def call_gemini_with_pdf(pdf_content, prompt_text, system_message, api_key, timeout=120, response_schema=None, user_id=None, inline_max_bytes=15*1024*1024, usage_callback=None, task='edital_extract', keys=None):
    if len(pdf_content) <= inline_max_bytes:
        part = {'inlineData': {'mimeType': 'application/pdf', 'data': base64.b64encode(pdf_content).decode()}}
    else:
        uri = await upload_to_gemini(pdf_content, api_key)
        if not uri: return None, 'other'
        part = {'fileData': {'mimeType': 'application/pdf', 'fileUri': uri}}
    return await call_gemini(prompt_text, system_message, api_key, timeout, user_id, response_schema, usage_callback,
                             parts=[part, {'text': prompt_text}], task=task, keys=keys)
