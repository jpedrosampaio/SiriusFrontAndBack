"""Deterministic batching/evidence gates. No provider, database or planner writes."""
from hashlib import sha256
import json
import re
import unicodedata
from pydantic import BaseModel
from edital_pipeline_contracts import (Citation, ProposedFact, InventoryUnit, ScopeUnit, DetailUnit, VerificationUnit,
    PIPELINE_VERSION, UNIT_CHARACTERS)


class EvidenceError(Exception):
    def __init__(self,code):
        self.code=code
        super().__init__(code)  # Never include document/model contents in logs.


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC',value).replace('\u00ad','').split()).casefold()


def blocks_from_pages(pages):
    return [block for page in pages for block in (page.blocks if isinstance(page,BaseModel) else page.get('blocks',[]))]


def block_dict(block):
    return block.model_dump(mode='json') if isinstance(block,BaseModel) else block


def batches(blocks,characters=UNIT_CHARACTERS,max_blocks=120):
    """Bound by source size and count; keep paragraph/table continuity metadata.

    Source blocks already have bounded text. A large table can span batches;
    each row retains its table ID/header hint and never loses its cell links.
    """
    current=[];size=0
    for raw in blocks:
        block=block_dict(raw);cost=len(block['text'])+len(block['id'])+48
        if current and (size+cost>characters or len(current)>=max_blocks):
            yield current;current=[];size=0
        current.append(block);size+=cost
    if current:yield current


def unit_key(kind,scope,source_blocks,context_blocks=(),semantic_context=None):
    value='\n'.join([PIPELINE_VERSION,kind,scope,*source_blocks,'--context--',*context_blocks])
    if semantic_context:value+='\n--semantic-context--\n'+json.dumps(semantic_context,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    return sha256(value.encode('utf-8')).hexdigest()


def walk(value):
    if isinstance(value,BaseModel):
        yield value
        for name in type(value).model_fields:yield from walk(getattr(value,name))
    elif isinstance(value,dict):
        for entry in value.values():yield from walk(entry)
    elif isinstance(value,(list,tuple)):
        for entry in value:yield from walk(entry)


def validate_citation(citation,source):
    block=source.get(citation.block_id)
    if block is None or block['page']!=citation.page:raise EvidenceError('source_reference_mismatch')
    if normalized(citation.quote) not in normalized(block['text']):raise EvidenceError('source_excerpt_mismatch')


def validate_fact(fact,source):
    for citation in fact.sources:validate_citation(citation,source)
    if fact.value is None:return
    value=normalized(fact.value)
    quotes=normalized(' '.join(c.quote for c in fact.sources))
    # A question count "2" is not supported by a source that only says "12".
    if not re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)',quotes):
        raise EvidenceError('value_not_supported_by_excerpt')


def discipline_key(discipline):
    value='\n'.join(normalized(getattr(discipline,field).value or '') for field in ('stage','group','name'))
    return sha256(value.encode('utf-8')).hexdigest()[:24]


def validate_unit(result,primary,context=(),known_topic_owners=None,container_titles=(),expected_section_keys=(),expected_reviewed_unit_key=None):
    primary=[block_dict(b) for b in primary];context=[block_dict(b) for b in context]
    source={b['id']:b for b in [*primary,*context]}
    ids=[b['id'] for b in primary]
    if len(set(ids))!=len(ids):raise EvidenceError('duplicate_source_input')
    for item in walk(result):
        if isinstance(item,ProposedFact):validate_fact(item,source)
        elif isinstance(item,Citation):validate_citation(item,source)
    if isinstance(result,InventoryUnit):
        coverage=[]
        for span in result.classifications:
            try:
                start=ids.index(span.block_id);end=ids.index(span.end_block_id or span.block_id)
            except ValueError:raise EvidenceError('classification_outside_unit') from None
            if end<start:raise EvidenceError('reversed_section_range')
            coverage.extend(ids[start:end+1])
        if sorted(coverage)!=sorted(ids):raise EvidenceError('inventory_coverage_mismatch')
        for role in result.roles:
            if not (role.name.value or role.code.value):raise EvidenceError('role_identity_missing')
    elif isinstance(result,ScopeUnit):
        if sorted(b.section_key for b in result.bindings)!=sorted(expected_section_keys):raise EvidenceError('scope_binding_coverage_mismatch')
    elif isinstance(result,DetailUnit):
        if sorted(result.covered_block_ids)!=sorted(ids):raise EvidenceError('detail_coverage_mismatch')
        containers={normalized(title) for title in container_titles}
        owners=dict(known_topic_owners or {})
        for discipline in result.disciplines:
            if not discipline.name.value:raise EvidenceError('discipline_identity_missing')
            owner=discipline_key(discipline)
            if normalized(discipline.name.value or '') in containers:raise EvidenceError('container_as_discipline')
            for topic in discipline.topics:owners[topic.key]=owner
        for discipline in result.disciplines:
            owner=discipline_key(discipline)
            for topic in discipline.topics:
                primary_sources=[c for c in topic.title.sources if c.block_id in ids]
                if not primary_sources or not topic.title.value:raise EvidenceError('topic_outside_primary_scope')
                validate_fact(topic.title.model_copy(update={'sources':primary_sources}),source)
                if not any(topic.key.startswith(c.block_id) for c in primary_sources):raise EvidenceError('topic_key_without_source_anchor')
                if topic.parent_key and owners.get(topic.parent_key)!=owner:raise EvidenceError('unknown_or_foreign_topic_parent')
                if topic.numbering and not any(re.match(r'^\s*'+re.escape(topic.numbering)+r'(?=\s|[.)])',source.quote) for source in topic.title.sources):
                    raise EvidenceError('numbering_not_supported_by_source')
        for rule in result.rules:
            if rule.fact.value is not None:
                primary_sources=[c for c in rule.fact.sources if c.block_id in ids]
                if not primary_sources:raise EvidenceError('rule_outside_primary_scope')
                validate_fact(rule.fact.model_copy(update={'sources':primary_sources}),source)
    elif isinstance(result,VerificationUnit):
        if result.reviewed_unit_key!=expected_reviewed_unit_key:raise EvidenceError('verification_target_mismatch')
        if sorted(result.covered_block_ids)!=sorted(ids):raise EvidenceError('verification_coverage_mismatch')
        if any(not any(c.block_id in ids for c in finding.sources) for finding in result.findings):
            raise EvidenceError('verification_finding_outside_primary_scope')
    else:raise EvidenceError('unknown_unit_contract')
    return result


def split_batch(primary):
    if len(primary)<2:raise EvidenceError('unit_cannot_split_further')
    point=len(primary)//2
    return primary[:point],primary[point:]


def role_id(role):
    """Source identity is stable when the owner later corrects a display name."""
    sources=role.name.sources or role.code.sources
    if not sources:raise EvidenceError('role_identity_missing')
    anchor=sources[0]
    identity=normalized(role.name.value or role.code.value)
    return sha256(f'{anchor.page}:{anchor.block_id}:{normalized(anchor.quote)}:{identity}'.encode('utf-8')).hexdigest()[:24]


def source_key(source):
    return source['page'],source['block_id'],normalized(source['quote'])


def merge_fact(previous,incoming):
    """Merge proposals only. Human decisions are applied in a separate layer."""
    if isinstance(incoming,ProposedFact):incoming=incoming.model_dump(mode='json')
    if previous is None:return {**incoming,'verification':'awaiting_review','alternatives':[]}
    if incoming['value'] is None:return previous
    if previous.get('value') is None:return {**incoming,'verification':'awaiting_review','alternatives':[]}
    if normalized(previous['value'])==normalized(incoming['value']):
        sources={source_key(s):s for s in [*previous.get('sources',[]),*incoming['sources']]}
        return {**previous,'sources':list(sources.values()),
            'state':'ambiguous' if 'ambiguous' in (previous['state'],incoming['state']) else 'extracted'}
    alternatives=[*previous.get('alternatives',[])]
    if not any(normalized(a['value'])==normalized(incoming['value']) for a in alternatives):alternatives.append(incoming)
    return {**previous,'state':'ambiguous','verification':'awaiting_review','alternatives':alternatives}
