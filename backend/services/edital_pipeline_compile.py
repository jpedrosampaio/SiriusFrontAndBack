"""Deterministic proposal consolidation; corrections remain a separate owner layer."""
from hashlib import sha256
from edital_pipeline_contracts import (CanonicalFact, CanonicalNamedFact, IdentifiedRole, ProgramDiscipline,
    ProgramTopic, ProgramRule, ProposedFact)
from services.edital_semantics import normalized, role_id, merge_fact, discipline_key, EvidenceError


def digest(*parts):
    return sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:24]


def section_key(section):
    return digest(section.block_id, section.end_block_id or section.block_id, section.kind)


def canonical(previous, proposal):
    return CanonicalFact.model_validate(merge_fact(previous.model_dump(mode='json') if previous else None, proposal))


def corrected(fact, correction):
    if correction is None: return fact
    alternatives = list(fact.alternatives)
    if fact.value is not None and fact.sources:
        prior = ProposedFact(value=fact.value, state='ambiguous' if fact.state == 'ambiguous' else 'extracted', sources=fact.sources[:6])
        if not any(a == prior for a in alternatives): alternatives.append(prior)
    return CanonicalFact(value=correction.value, state='corrected_by_user', origin='human_declared',
        verification='confirmed', human_note=correction.note, confirmed_at=correction.recorded_at,
        alternatives=alternatives)


def add_issue(collection, message):
    if message not in collection and len(collection) < 100: collection.append(message)


def inventory(state, proposal):
    """Safe for early partial results; no claim that inventory coverage is complete."""
    for part in proposal.roles:
        identity = role_id(part)
        match = next((role for role in state.roles if role.id == identity), None)
        if match is None and part.code.value:
            matches = [r for r in state.roles if normalized(r.source_code or '') == normalized(part.code.value)
                and normalized(r.source_name or '') == normalized(part.name.value or '')]
            if len(matches) == 1: match = matches[0]
        if match is None:
            match = IdentifiedRole(id=identity, source_name=part.name.value, source_code=part.code.value,
                source_keys=[identity], name=canonical(None, part.name))
            if any(normalized(r.source_name or '') == normalized(part.name.value or '') for r in state.roles):
                add_issue(state.issues, 'Nomes de cargos repetidos em fontes distintas exigem conferência de identidade; não foram fundidos sem código comprovado.')
            state.roles.append(match)
        if identity not in match.source_keys: match.source_keys.append(identity)
        for field in ('name', 'code', 'vacancies', 'salary', 'requirements'):
            fact = canonical(getattr(match, field), getattr(part, field))
            setattr(match, field, corrected(fact, state.corrections.get(f'roles/{match.id}/{field}')))
    by_section = {section_key(s): s for s in state.sections}
    for section in proposal.classifications:
        key = section_key(section)
        if key in by_section and by_section[key] != section:
            add_issue(state.issues, 'Classificações divergentes para o mesmo intervalo requerem conferência.')
        else: by_section[key] = section
    state.sections = sorted(by_section.values(), key=lambda s: s.block_id)
    facts = {fact.id: fact for fact in state.facts}
    for item in proposal.facts:
        # Multiple dates/schedule events remain separate facts, not overwritten
        # just because the semantic field name happens to be the same.
        anchor = item.fact.sources[0] if item.fact.sources else None
        identity = digest(item.key, str(anchor.page) if anchor else '', anchor.block_id if anchor else '',
            normalized(item.fact.value or ''))
        previous = facts.get(identity)
        merged = canonical(previous.fact if previous else None, item.fact)
        singleton = item.key in ('exam_name', 'board', 'exam_date', 'registration_start', 'registration_end')
        conflicts = [f for f in facts.values() if singleton and f.key == item.key and
            normalized(f.fact.value or '') != normalized(item.fact.value or '')]
        if conflicts and item.fact.value is not None:
            merged.state = 'ambiguous'
            for other in conflicts:
                if other.fact.state != 'corrected_by_user': other.fact.state = 'ambiguous'; other.fact.verification = 'awaiting_review'
            add_issue(state.issues, 'Informações gerais divergentes exigem conferência das fontes; nenhum valor foi escolhido automaticamente.')
        facts[identity] = CanonicalNamedFact(id=identity, key=item.key,
            fact=corrected(merged, state.corrections.get(f'facts/{identity}')))
    state.facts = sorted(facts.values(), key=lambda f: (f.fact.sources[0].page if f.fact.sources else 0, f.id))
    state.roles.sort(key=lambda r: (r.name.sources[0].page if r.name.sources else 0, r.id))


def program(scope, proposal):
    if proposal.applicability in ('ambiguous', 'other_role'):
        add_issue(scope.program.issues, 'Um lote incluído não comprovou aplicabilidade ao cargo; confira a associação e solicite reanálise.')
        return
    disciplines = {d.id: d for d in scope.program.disciplines}
    for part in proposal.disciplines:
        identity = discipline_key(part)
        discipline = disciplines.get(identity) or ProgramDiscipline(id=identity, name=canonical(None, part.name))
        for field in ('name', 'stage', 'group'):
            value = canonical(getattr(discipline, field), getattr(part, field))
            setattr(discipline, field, corrected(value, scope.corrections.get(f'disciplines/{identity}/{field}')))
        topics = {t.id: t for t in discipline.topics}
        local = {}
        for topic in part.topics:
            source = next((c for c in topic.title.sources if topic.key.startswith(c.block_id)), None)
            if source is None: raise EvidenceError('topic_source_missing')
            canonical_id = digest(identity, str(source.page), source.block_id, topic.key)
            key = f'{identity}|{topic.key}'
            if key in scope.topic_keys and scope.topic_keys[key] != canonical_id:
                raise EvidenceError('topic_key_reused_for_different_source')
            scope.topic_keys[key] = canonical_id; local[topic.key] = canonical_id
        for topic in part.topics:
            canonical_id = local[topic.key]
            parent = local.get(topic.parent_key) or scope.topic_keys.get(f'{identity}|{topic.parent_key}') if topic.parent_key else None
            if topic.parent_key and parent is None: raise EvidenceError('unknown_canonical_topic_parent')
            previous = topics.get(canonical_id)
            if previous and previous.parent_id != parent and canonical_id not in scope.edits.topic_parents:
                raise EvidenceError('conflicting_topic_parent')
            title = canonical(previous.title if previous else None, topic.title)
            topics[canonical_id] = ProgramTopic(id=canonical_id, parent_id=parent, numbering=topic.numbering,
                title=corrected(title, scope.corrections.get(f'topics/{canonical_id}/title')))
        discipline.topics = sorted(topics.values(), key=lambda t: (
            t.title.sources[0].page if t.title.sources else 0,
            t.title.sources[0].block_id if t.title.sources else '', t.id))
        disciplines[identity] = discipline
    scope.program.disciplines = sorted(disciplines.values(), key=lambda d: (
        d.name.sources[0].page if d.name.sources else 0, d.id))
    rules = {r.id: r for r in scope.program.rules}
    for item in proposal.rules:
        identity = digest(item.target_scope, normalized(item.target.value or ''), item.kind)
        previous = rules.get(identity)
        fact = canonical(previous.fact if previous else None, item.fact)
        target = canonical(previous.target if previous else None, item.target)
        rules[identity] = ProgramRule(id=identity, target_scope=item.target_scope, target=target, kind=item.kind,
            fact=corrected(fact, scope.corrections.get(f'rules/{identity}/fact')))
    scope.program.rules = sorted(rules.values(), key=lambda r: r.id)
    overlay(scope)


def overlay(scope):
    """Preserve explicit structural edits without hiding newly extracted facts."""
    disciplines={d.id:d for d in scope.program.disciplines}
    for added in scope.edits.added_disciplines:disciplines.setdefault(added.id,added.model_copy(deep=True))
    for identity,discipline in disciplines.items():
        for field in ('name','stage','group'):
            setattr(discipline,field,corrected(getattr(discipline,field),scope.corrections.get(f'disciplines/{identity}/{field}')))
        topics={t.id:t for t in discipline.topics}
        for added in scope.edits.added_topics.get(identity,[]):topics.setdefault(added.id,added.model_copy(deep=True))
        removed=set(scope.edits.removed_topics)
        for topic in topics.values():
            if topic.id in scope.edits.topic_parents:topic.parent_id=scope.edits.topic_parents[topic.id]
            topic.title=corrected(topic.title,scope.corrections.get(f'topics/{topic.id}/title'))
        changed=True
        while changed:
            descendants={t.id for t in topics.values() if t.parent_id in removed}
            changed=not descendants.issubset(removed);removed.update(descendants)
        discipline.topics=[t for t in topics.values() if t.id not in removed]
    scope.program.disciplines=[d for d in disciplines.values() if d.id not in scope.edits.removed_disciplines]
    rules={r.id:r for r in scope.program.rules}
    for added in scope.edits.added_rules:rules.setdefault(added.id,added.model_copy(deep=True))
    scope.program.rules=[r for r in rules.values() if r.id not in scope.edits.removed_rules]
    for rule in scope.program.rules:
        for field in ('target','fact'):
            setattr(rule,field,corrected(getattr(rule,field),scope.corrections.get(f'rules/{rule.id}/{field}')))
