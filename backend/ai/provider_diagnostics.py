"""Finite public error metadata. Never preserve provider text or arbitrary paths."""
import re

STATUSES = frozenset({'INVALID_ARGUMENT', 'FAILED_PRECONDITION', 'OUT_OF_RANGE',
    'UNIMPLEMENTED', 'NOT_FOUND', 'PERMISSION_DENIED', 'UNAUTHENTICATED',
    'RESOURCE_EXHAUSTED', 'UNAVAILABLE', 'INTERNAL', 'DEADLINE_EXCEEDED'})
CATEGORIES = frozenset({'unknown_field', 'invalid_value', 'missing_field',
    'unsupported', 'output_validation', 'context_limit', 'unspecified'})
# Public protocol constants only. Unknown provider values can contain private
# data and must never be persisted, rendered or copied verbatim.
PROVIDER_CODES = frozenset({'json_validate_failed', 'model_decommissioned',
    'model_not_found', 'context_length_exceeded', 'invalid_api_key',
    'rate_limit_exceeded', 'tool_use_failed'})
PROVIDER_TYPES = frozenset({'invalid_request_error', 'authentication_error',
    'permission_error', 'rate_limit_error', 'server_error'})
FIELDS = frozenset({'model', 'store', 'contents', 'contents.parts',
    'systemInstruction', 'systemInstruction.parts', 'tools', 'toolConfig',
    'generationConfig', 'generationConfig.maxOutputTokens',
    'generationConfig.responseFormat', 'generationConfig.responseFormat.text',
    'generationConfig.responseFormat.text.mimeType',
    'generationConfig.responseFormat.text.schema',
    'generationConfig.responseMimeType', 'generationConfig.responseJsonSchema',
    'generationConfig.responseSchema', 'messages', 'max_completion_tokens',
    'response_format', 'response_format.json_schema', 'response_format.json_schema.schema',
    'response_format.json_schema.strict'})
_ALIASES = {field.replace('_', '').lower(): field for field in FIELDS}


def _public_field(value):
    if not isinstance(value, str) or len(value) > 256:
        return None
    value = re.sub(r'\[\d{1,6}\]', '', value).replace('_', '').lower()
    for prefix in ('request.', 'generaterequest.', 'generatecontentrequest.'):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    # Schema property names/indices may contain private text: collapse them.
    for prefix in ('generationconfig.responseformat.text.schema',
                   'generationconfig.responsejsonschema', 'generationconfig.responseschema',
                   'responseformat.jsonschema.schema'):
        if value.startswith(prefix + '.') or value == prefix:
            return _ALIASES[prefix]
    return _ALIASES.get(value)


def safe_rejection(value):
    """Validate again at cache/persistence/read boundaries, including old JSON."""
    if not isinstance(value, dict):
        return None
    result = {}
    if type(value.get('code')) is int and 100 <= value['code'] <= 599:
        result['code'] = value['code']
    if isinstance(value.get('status'), str) and value['status'] in STATUSES:
        result['status'] = value['status']
    if isinstance(value.get('category'), str) and value['category'] in CATEGORIES:
        result['category'] = value['category']
    for name, allowed in (('provider_code', PROVIDER_CODES), ('provider_type', PROVIDER_TYPES)):
        if isinstance(value.get(name), str) and value[name] in allowed:
            result[name] = value[name]
    fields = value.get('fields')
    if isinstance(fields, (list, tuple)):
        result['fields'] = sorted({field for field in fields[:8]
                                  if isinstance(field, str) and field in FIELDS})
    return result or None


def rejection_metadata(error):
    """Classify bounded messages into constants; never return message fragments."""
    if not isinstance(error, dict):
        return None
    message = error.get('message')
    message = message[:4096] if isinstance(message, str) else ''
    lower = message.lower()
    category = ('output_validation' if error.get('code') == 'json_validate_failed' or
        lower.startswith(('failed to generate json.', 'generated json does not match the expected schema.'))
        else 'context_limit' if error.get('code') == 'context_length_exceeded'
        else 'unknown_field' if any(t in lower for t in ('unknown name', 'unknown field', 'cannot find field'))
        else 'missing_field' if any(t in lower for t in ('missing required', 'required field'))
        else 'unsupported' if any(t in lower for t in ('not supported', 'unsupported'))
        else 'invalid_value' if any(t in lower for t in ('invalid value at', 'out of range'))
        else 'unspecified')
    fields = set()
    field = _public_field(error.get('param'))
    if field:
        fields.add(field)
    details = error.get('details')
    for detail in details[:8] if isinstance(details, list) else []:
        violations = detail.get('fieldViolations') if isinstance(detail, dict) else None
        for violation in violations[:8] if isinstance(violations, list) else []:
            field = _public_field(violation.get('field')) if isinstance(violation, dict) else None
            if field:
                fields.add(field)
    # Known Google parser templates only. Arbitrary quoted/document text is not a path.
    for match in re.finditer(r'unknown (?:name|field) [\"\']([A-Za-z_][A-Za-z0-9_]*)[\"\'](?: at [\"\']([^\"\'\r\n]{1,160})[\"\'])?', message, re.I):
        name, parent = match.groups()
        field = _public_field(f'{parent}.{name}' if parent else name)
        if field:
            fields.add(field)
    for match in re.finditer(r'invalid value at [\"\']?([A-Za-z_][A-Za-z0-9_.\[\]]{0,200})', message, re.I):
        field = _public_field(match.group(1))
        if field:
            fields.add(field)
    return safe_rejection({'code': error.get('code'), 'status': error.get('status'),
        'category': category, 'fields': sorted(fields)[:8],
        'provider_code': error.get('code'), 'provider_type': error.get('type')})
