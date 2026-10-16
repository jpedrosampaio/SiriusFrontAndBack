"""Bounded selected-role work specifications from the owned documentary IR."""
from dataclasses import dataclass, field
import json
from services.edital_semantics import EvidenceError, batches
from services.edital_pipeline_compile import section_key


@dataclass
class UnitSpec:
    kind: str
    primary: list[str]
    context: list[str] = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


def range_ids(section, positions, blocks):
    first = positions.get(section.block_id); last = positions.get(section.end_block_id or section.block_id)
    if first is None or last is None or first > last: raise EvidenceError('section_source_range_invalid')
    return [b['id'] for b in blocks[first:last + 1]]


def role_sources(role):
    return [citation.block_id for fact in (role.name, role.code) for citation in fact.sources]


def context_ids(primary, by_id, positions, blocks, role):
    candidates = role_sources(role)
    first = positions[primary[0]]
    candidates += [b['id'] for b in blocks[max(0, first - 2):first]]
    parent = by_id[primary[0]].get('parent_heading_hint'); seen = set()
    while parent in by_id and parent not in seen and len(seen) < 8:
        seen.add(parent); candidates.append(parent); parent = by_id[parent].get('parent_heading_hint')
    selected = []; characters = 0
    for identity in dict.fromkeys(candidates):
        if identity in primary or identity not in by_id: continue
        cost = len(by_id[identity]['text'])
        if characters + cost <= 3000: selected.append(identity); characters += cost
    return selected


def selected_sections(state, scope):
    # Unknown classifications are made visible for association review. Owners
    # can include another classified interval explicitly; no title regex or
    # board/page/count assumption decides its meaning.
    return [s for s in state.inventory.sections if s.kind in ('program', 'exam_rules', 'uncertain')
        or section_key(s) in scope.binding_corrections]


def scope_specs(state, role_id, blocks):
    role = next((r for r in state.inventory.roles if r.id == role_id), None)
    if role is None: raise EvidenceError('selected_role_missing')
    scope = state.scopes[role_id]; by_id = {b['id']: b for b in blocks}; positions = {b['id']: i for i, b in enumerate(blocks)}
    result = []; keys = []; metadata = []; primary = []
    def flush():
        nonlocal keys, metadata, primary
        if not keys: return
        ordered = sorted(set(primary), key=positions.__getitem__)
        result.append(UnitSpec('scope', ordered, context_ids(ordered, by_id, positions, blocks, role),
            {'expected_section_keys': keys}, {'sections': metadata}))
        keys = []; metadata = []; primary = []
    for section in selected_sections(state, scope):
        identity = section_key(section)
        if identity in scope.binding_corrections or identity in scope.bindings: continue
        ids = range_ids(section, positions, blocks)
        candidates = [section.block_id, *[c.block_id for c in section.title.sources],
            *[c.block_id for c in section.scope_sources],
            *[c.block_id for fact in section.role_references for c in fact.sources], ids[-1]]
        selected = []; size = 0
        for point in dict.fromkeys(candidates):
            if point not in by_id: raise EvidenceError('section_evidence_source_missing')
            cost = len(by_id[point]['text']) + 80
            if size + cost <= 6000: selected.append(point); size += cost
        if not selected: raise EvidenceError('section_evidence_input_limit')
        info = {'section_key': identity, 'first': section.block_id, 'last': section.end_block_id,
            'kind_proposal': section.kind, 'level_proposal': section.level, 'title_proposal': section.title.value,
            'scope_proposal': section.scope, 'role_reference_proposals': [r.value for r in section.role_references],
            'evidence_window_limited': len(selected) < len(set(candidates))}
        combined = set(primary) | set(selected)
        if keys and (len(keys) >= 8 or sum(len(by_id[i]['text']) + 80 for i in combined) > 6000
                or len(json.dumps([*metadata, info], ensure_ascii=False)) > 8000): flush()
        keys.append(identity); metadata.append(info); primary.extend(selected)
    flush()
    return result


def effective_binding(scope, key):
    correction = scope.binding_corrections.get(key)
    if correction:
        if correction.value not in ('include', 'exclude', 'ambiguous'): raise EvidenceError('invalid_human_binding_decision')
        return correction.value
    binding = scope.bindings.get(key)
    return binding.decision if binding else 'ambiguous'


def detail_specs(state, role_id, blocks):
    role = next((r for r in state.inventory.roles if r.id == role_id), None)
    if role is None: raise EvidenceError('selected_role_missing')
    scope = state.scopes[role_id]; by_id = {b['id']: b for b in blocks}; positions = {b['id']: i for i, b in enumerate(blocks)}
    include = set(); ambiguous = []
    for section in selected_sections(state, scope):
        source_ids = range_ids(section, positions, blocks)
        identity = section_key(section); decision = effective_binding(scope, identity)
        if decision == 'include': include.update(source_ids)
        elif decision == 'ambiguous': ambiguous.append(identity)
    result = []; contiguous = []
    def flush():
        nonlocal contiguous
        for part in batches(contiguous, max_blocks=60):
            ids = [b['id'] for b in part]
            context = context_ids(ids, by_id, positions, blocks, role)
            visible = set(ids + context)
            containers = [s.title.value for s in state.inventory.sections if s.level == 'knowledge_group'
                and s.title.value and any(c.block_id in visible for c in s.title.sources)]
            result.append(UnitSpec('detail', ids, context, {'container_titles': list(dict.fromkeys(containers))}))
        contiguous = []
    for block in blocks:
        if block['id'] in include: contiguous.append(block)
        elif contiguous: flush()
    flush()
    return result, ambiguous
