"""Source-bound transport enums; never change canonical models or repair output."""
from copy import deepcopy


def source_contract(output_type, primary, context=()):
    schema = deepcopy(output_type.model_json_schema())
    source = {block['id']: block for block in [*primary, *context]}
    if source:
        citation = schema.get('$defs', {}).get('Citation', {}).get('properties', {})
        if citation:
            citation['block_id']['enum'] = sorted(source)
            citation['page']['enum'] = sorted({block['page'] for block in source.values()})
    # Coverage spans may refer only to primary blocks, never context-only IDs.
    ids = list(dict.fromkeys(block['id'] for block in primary))
    if ids:
        classification = schema.get('$defs', {}).get('ClassificationTransport', {}).get('properties', {})
        if classification:
            classification['block_id']['enum'] = ids
            for branch in classification['end_block_id'].get('anyOf', []):
                if branch.get('type') == 'string': branch['enum'] = ids
        covered = schema.get('properties', {}).get('covered_block_ids', {}).get('items')
        if covered is not None: covered['enum'] = ids
    return schema
