"""Finite post-response diagnostics; never retain inputs, messages or exceptions."""
import re

FIELDS = set(('roles name code vacancies salary requirements value state sources page block_id quote '
    'classifications end_block_id kind level title scope role_references scope_sources facts key fact warnings '
    'classes coverage bindings section_key decision reason applicability covered_block_ids disciplines stage group topics '
    'parent_key numbering rules target_scope target reviewed_unit_key findings severity subject description').split())
CODES = {
    'documentary': {'value_not_supported_by_excerpt', 'source_excerpt_mismatch', 'documentary_rejected', 'role_identity_missing', 'source_reference_mismatch', 'classification_outside_unit', 'reversed_section_range', 'inventory_coverage_mismatch'},
    'json_decode': {'invalid_json', 'markdown_fence'},
    'json_schema': {'required', 'type', 'enum', 'const', 'additionalProperties', 'minItems', 'maxItems',
        'minLength', 'maxLength', 'pattern', 'format', 'minimum', 'maximum', 'anyOf', 'oneOf', 'allOf', 'schema_rejected'},
    'pydantic': {'value_error', 'missing', 'extra_forbidden', 'string_type', 'string_too_short', 'string_too_long',
        'string_pattern_mismatch', 'int_type', 'int_parsing', 'float_type', 'float_parsing', 'finite_number',
        'bool_type', 'bool_parsing', 'list_type', 'dict_type', 'model_type', 'model_attributes_type', 'literal_error',
        'too_short', 'too_long', 'greater_than', 'greater_than_equal', 'less_than', 'less_than_equal', 'contract_rejected'},
}
# Compare in memory to constants only. Unknown validator messages never escape.
INVARIANTS = {
    'Coverage must match every primary block': 'inventory_coverage_missing',
    'Coverage must use exactly the supplied class indexes': 'inventory_assignment_invalid',
    'Missing information is not zero or a sourced value': 'fact_missing_inconsistent',
    'A proposed value requires documentary evidence': 'fact_evidence_missing',
    'A semantic heading requires its sourced title': 'heading_title_missing',
    'Semantic applicability requires source evidence': 'scope_evidence_missing',
    'Named-role applicability requires documentary references': 'scope_roles_missing',
    'A proposed scope decision requires evidence': 'decision_evidence_missing',
    'Ambiguous/other-role content cannot become selected-role facts': 'role_applicability_invalid',
    'Role applicability requires documentary evidence': 'applicability_evidence_missing',
    'Topic keys must be unique within a unit': 'topic_key_duplicate',
    'Cyclic or unbounded topic hierarchy': 'topic_hierarchy_invalid',
}


def location_path(location):
    path = '$'
    for part in tuple(location)[:10]:
        if type(part) is int:
            path += '[]'
        elif isinstance(part, str) and part in FIELDS:
            path += '.' + part
        else:
            path += '.*'
            break
    return path


def safe_validation(value):
    if not isinstance(value, dict): return None
    stage, code = value.get('stage'), value.get('code')
    if not isinstance(stage, str) or stage not in CODES or not isinstance(code, str) or code not in CODES[stage]: return None
    result = {'stage': stage, 'code': code, 'path': '$'}
    path = value.get('path')
    if (isinstance(path, str) and len(path) <= 200 and
        re.fullmatch(r'\$(?:\[\]){0,10}(?:\.(?:[a-z_]+|\*)(?:\[\]){0,10}){0,10}', path) and
        all(field in FIELDS for field in re.findall(r'[a-z_]+', path))):
        result['path'] = path
    rule = value.get('rule')
    if isinstance(rule, str) and rule in INVARIANTS.values(): result['rule'] = rule
    return result


def json_failure(text):
    return {'stage': 'json_decode', 'code': 'markdown_fence' if isinstance(text, str) and text.lstrip().startswith('```') else 'invalid_json', 'path': '$'}


def schema_failure(error):
    code = error.validator if error.validator in CODES['json_schema'] else 'schema_rejected'
    location = list(error.absolute_path)
    if code == 'required' and isinstance(error.instance, dict):
        missing = next((name for name in error.validator_value if name not in error.instance), None)
        if missing is not None: location.append(missing)
    return {'stage': 'json_schema', 'code': code, 'path': location_path(location)}


def pydantic_failure(error):
    result = {'stage': 'pydantic', 'code': 'contract_rejected', 'path': '$'}
    # No input, URL or raw message is propagated. Context is used only for the
    # fixed invariant lookup, never stored in the returned metadata.
    if not hasattr(error, 'errors'): return result
    errors = error.errors(include_url=False, include_input=False)
    if not errors: return result
    first = errors[0]
    code = first.get('type')
    if code in CODES['pydantic']: result['code'] = code
    result['path'] = location_path(first.get('loc', ()))
    rule = INVARIANTS.get(str(first.get('ctx', {}).get('error', ''))[:200])
    if rule: result['rule'] = rule
    return result


def documentary_failure(error):
    """Only finite rule names, never citations, IDs, exception text or output."""
    code = getattr(error, 'code', None)
    return {'stage': 'documentary', 'code': code if isinstance(code, str) and code in CODES['documentary'] else 'documentary_rejected', 'path': location_path(getattr(error,'location',()))}
