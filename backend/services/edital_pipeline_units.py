"""Short transactions for leased semantic checkpoints; never provider IO."""
from dataclasses import dataclass
import json
from datetime import timedelta
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select, exists, and_, or_, literal, text, func
from sqlalchemy.orm import aliased
from db.models.edital_units import EditalUnit
from db.models.files import EditalJob, EditalAnalysis
from db.models.identity import User
from db.session import unit_of_work
from edital_pipeline_contracts import InventoryUnit, ScopeUnit, DetailUnit, VerificationUnit
from services import edital_pipeline_store as store
from services.edital_semantics import validate_unit, EvidenceError, split_batch, unit_key
from ai.schemas import TRANSPORT_VERSION

LEASE_SECONDS = 180
CONTRACTS = {'inventory': InventoryUnit, 'scope': ScopeUnit, 'detail': DetailUnit, 'verify': VerificationUnit}


class LeaseLost(Exception):
    """A cancelled/restarted/expired generation cannot make another AI call."""


@dataclass(frozen=True)
class Claim:
    user_id: UUID
    analysis_id: UUID
    job_id: UUID
    unit_id: UUID
    generation: UUID
    token: UUID
    kind: str
    scope_key: str


def generation(state, unit):
    if unit.scope_key == 'inventory': return state.inventory.generation
    scope = state.scopes.get(unit.scope_key.removeprefix('role:'))
    return scope.generation if scope else None


def record_pause(state,unit):
    if state.status in ('waiting_provider','quota_paused','recoverable_failure'):
        target=state.inventory if unit.scope_key=='inventory' else state.scopes[unit.scope_key.removeprefix('role:')]
        target.status=state.status


def approved(state):
    return state.provider_approval is not None and state.provider_approval.transport_version==TRANSPORT_VERSION and state.provider_approval.mode in ('pilot','full')


def stop_pilot(state,unit,*,validated=False):
    approval=state.provider_approval
    if approval and approval.mode=='pilot':
        approval.mode='paused';approval.pilot_validated=validated
        state.status='waiting_provider'
        if validated:state.error_kind='pilot_review_required'
        record_pause(state,unit)


async def locked(session, claim, require_live=True):
    user = await session.scalar(select(User).where(User.id == claim.user_id).with_for_update())
    if user is None: raise LeaseLost()
    try:
        analysis = await store.owned_analysis(session, claim.user_id, claim.analysis_id, lock=True)
    except HTTPException as error:
        if error.status_code == 404: raise LeaseLost() from None
        raise
    job = await session.scalar(select(EditalJob).where(EditalJob.user_id == claim.user_id,
        EditalJob.id == claim.job_id, EditalJob.analysis_id == claim.analysis_id).with_for_update())
    unit = await session.scalar(select(EditalUnit).where(EditalUnit.user_id == claim.user_id,
        EditalUnit.id == claim.unit_id, EditalUnit.analysis_id == claim.analysis_id,
        EditalUnit.job_id == claim.job_id).with_for_update())
    state = store.manifest(analysis)
    if job is None or unit is None or unit.status != 'running' or unit.lease_token != claim.token or \
            unit.generation != claim.generation or generation(state, unit) != claim.generation or \
            (unit.scope_key!='inventory' and unit.scope_key!=f'role:{state.selected_role_id}') or \
            state.status != 'processing' or (require_live and unit.lease_until <= store.utc_now()):
        raise LeaseLost()
    return analysis, job, unit, state


async def source_blocks(session, uid, analysis_id, ids):
    if not ids: return []
    # Extract only the selected JSON blocks, not the whole PDF/IR on every poll.
    rows = (await session.execute(text('''
        SELECT b.value FROM edital_analyses a
        CROSS JOIN LATERAL jsonb_array_elements(a.pages) p(value)
        CROSS JOIN LATERAL jsonb_array_elements(p.value->'blocks') b(value)
        WHERE a.user_id=:uid AND a.id=:aid AND b.value->>'id'=ANY(CAST(:ids AS text[]))
    '''), {'uid': uid, 'aid': analysis_id, 'ids': ids})).scalars().all()
    by_id = {row['id']: row for row in rows}
    if set(ids) != set(by_id): raise EvidenceError('durable_source_block_missing')
    return [by_id[identity] for identity in ids]


async def expire_leases():
    now = store.utc_now()
    async with unit_of_work() as session:
        expired = (await session.execute(select(EditalUnit.user_id, EditalUnit.id).where(
            EditalUnit.status == 'running', EditalUnit.lease_until <= now).order_by(EditalUnit.lease_until).limit(20))).all()
    for uid, identity in expired:
        async with unit_of_work() as session:
            user = await session.scalar(select(User).where(User.id == uid).with_for_update(skip_locked=True))
            if user is None: continue
            unit = await session.get(EditalUnit, identity)
            if unit is None: continue
            analysis = await store.owned_analysis(session, uid, unit.analysis_id, lock=True)
            job = await session.scalar(select(EditalJob).where(EditalJob.id == unit.job_id,
                EditalJob.user_id == uid).with_for_update())
            unit = await session.scalar(select(EditalUnit).where(EditalUnit.id == identity,
                EditalUnit.user_id == uid).with_for_update())
            if unit.status != 'running' or unit.lease_until > now: continue
            state = store.manifest(analysis)
            unit.lease_token = unit.lease_until = None
            if generation(state, unit) != unit.generation or state.status == 'cancelled':
                unit.status = 'cancelled'; unit.finished_at = now
            elif unit.diagnostics.get('retry_failures',unit.attempts-1)+1 >= 3:
                unit.status = 'failed'; unit.finished_at = now
                state.status = 'recoverable_failure'; state.error_kind = 'worker_restart_retry_limit'
                record_pause(state,unit)
                store.write_manifest(analysis, state)
            else:
                unit.status = 'pending'; unit.available_at = now + timedelta(seconds=10 * unit.attempts)
            if unit.status != 'cancelled':
                unit.diagnostics = {**unit.diagnostics, 'retry_failures':unit.diagnostics.get('retry_failures',unit.attempts-1)+1,
                    'last_error': 'worker_interrupted', 'reference': str(uuid4())}
                stop_pilot(state,unit)
                store.write_manifest(analysis,state)
            if job:
                job.status = 'queued' if state.status == 'processing' else 'completed'
                job.lease_token = job.lease_until = None


async def claim_next(kind=None):
    await expire_leases()
    now = store.utc_now(); running = aliased(EditalUnit)
    async with unit_of_work() as session:
        busy_owner = exists(select(running.id).where(running.user_id == EditalUnit.user_id,
            running.status == 'running', running.lease_until > now))
        candidates = (await session.execute(select(EditalUnit.user_id, EditalUnit.analysis_id,
            EditalUnit.job_id, EditalUnit.id).join(EditalAnalysis,
                and_(EditalAnalysis.user_id == EditalUnit.user_id, EditalAnalysis.id == EditalUnit.analysis_id))
            .where(EditalUnit.status == 'pending', EditalUnit.available_at <= now, ~busy_owner,
                EditalAnalysis.analysis_version == '6',
                EditalAnalysis.structured_payload['universal']['status'].astext == 'processing',
                or_(EditalUnit.scope_key == 'inventory', EditalUnit.scope_key == literal('role:') +
                    EditalAnalysis.structured_payload['universal']['selected_role_id'].astext),
                *([] if kind is None else [EditalUnit.kind == kind]))
            .order_by(EditalAnalysis.updated_at, EditalUnit.source_blocks[0].astext,
                EditalUnit.created_at, EditalUnit.id).limit(10))).all()
    for uid, aid, jid, identity in candidates:
        async with unit_of_work() as session:
            user = await session.scalar(select(User).where(User.id == uid).with_for_update(skip_locked=True))
            if user is None: continue
            # Recheck owner-wide exclusion after the account lock; the discovery
            # SELECT intentionally holds no locks and may race another process.
            if await session.scalar(select(EditalUnit.id).where(EditalUnit.user_id == uid,
                EditalUnit.status == 'running', EditalUnit.lease_until > now).limit(1)): continue
            try:
                analysis = await store.owned_analysis(session, uid, aid, lock=True)
            except HTTPException as error:
                if error.status_code == 404: continue  # Deleted after candidate discovery.
                raise
            job = await session.scalar(select(EditalJob).where(EditalJob.user_id == uid,
                EditalJob.id == jid, EditalJob.analysis_id == aid,
                EditalJob.storage_provider == store.MARKER).with_for_update())
            unit = await session.scalar(select(EditalUnit).where(EditalUnit.user_id == uid,
                EditalUnit.id == identity).with_for_update())
            state = store.manifest(analysis)
            if job is None or unit is None or unit.status != 'pending' or unit.available_at > now or state.status != 'processing': continue
            if not approved(state):
                state.status='waiting_provider';state.error_kind='provider_approval_required'
                record_pause(state,unit);store.write_manifest(analysis,state)
                job.status='completed';job.phase='Aguardando homologação e autorização da IA';job.finished_at=now
                continue
            if unit.scope_key!='inventory' and unit.scope_key!=f'role:{state.selected_role_id}':continue
            if generation(state, unit) != unit.generation:
                unit.status = 'cancelled'; unit.finished_at = now; continue
            if state.provider_approval.mode=='full':
                from services.edital_pipeline_budget import forecast
                if (await forecast(session,analysis,state))['extension_required']:
                    state.status='quota_paused';state.error_kind='planned_units_exceed_remaining_budget'
                    record_pause(state,unit);store.write_manifest(analysis,state)
                    job.status='completed';job.finished_at=now
                    continue
            if unit.diagnostics.get('retry_failures',unit.attempts) >= 3:
                unit.status = 'failed'; unit.finished_at = now; state.status = 'recoverable_failure'; state.error_kind = 'unit_retry_limit'
                record_pause(state,unit)
                store.write_manifest(analysis, state); continue
            if state.budget.reserved_attempts >= state.budget.provider_limit:
                state.status = 'quota_paused'; state.error_kind = 'analysis_provider_budget'
                record_pause(state,unit)
                store.write_manifest(analysis, state); continue
            token = uuid4(); unit.status = 'running'
            # The historical SQL counter is bounded at three. Explicit owner
            # recovery gets its own monotonic audit counter, never resets it.
            unit.diagnostics={**unit.diagnostics,'claims_total':unit.diagnostics.get('claims_total',unit.attempts)+1}
            unit.attempts = min(3,unit.attempts+1)
            if state.provider_approval.mode=='pilot':state.provider_approval.pilot_unit_id=unit.id
            unit.lease_token = token; unit.lease_until = now + timedelta(seconds=LEASE_SECONDS)
            job.status = 'running'; job.lease_token = token; job.lease_until = unit.lease_until
            analysis.updated_at = now; analysis.revision += 1
            store.write_manifest(analysis,state)
            return Claim(uid, aid, jid, identity, unit.generation, token, unit.kind, unit.scope_key)
    return None


def validation_context(unit, state):
    result = dict(unit.diagnostics.get('validation', {}))
    if unit.kind == 'detail':
        scope = state.scopes[unit.scope_key.removeprefix('role:')]
        owners = {}
        for encoded in scope.topic_keys:
            owner, _, key = encoded.partition('|')
            if key in owners and owners[key] != owner: raise EvidenceError('persisted_topic_key_ownership_conflict')
            owners[key] = owner
        result['known_topic_owners'] = owners
    return result


def previous_topics(unit, state, context):
    if unit.kind != 'detail': return []
    scope = state.scopes[unit.scope_key.removeprefix('role:')]
    nodes = {topic.id: (discipline.id, topic) for discipline in scope.program.disciplines for topic in discipline.topics}
    keys = {}
    for encoded, identity in scope.topic_keys.items(): keys.setdefault(identity, encoded.partition('|')[2])
    context_ids = {b['id'] for b in context}
    candidates = [identity for identity, (_, topic) in nodes.items() if any(c.block_id in context_ids for c in topic.title.sources)]
    ordered = sorted(nodes, key=lambda identity: (
        nodes[identity][1].title.sources[0].page if nodes[identity][1].title.sources else 0,
        nodes[identity][1].title.sources[0].block_id if nodes[identity][1].title.sources else '', identity))
    candidates.extend(reversed(ordered[-16:])); selected = {}; size = 0
    for identity in dict.fromkeys(candidates):
        chain = []; point = identity
        while point in nodes and point not in chain and len(chain) < 8:
            chain.append(point); point = nodes[point][1].parent_id
        for point in reversed(chain):
            if point in selected or point not in keys: continue
            owner, topic = nodes[point]
            item = {'key': keys[point], 'owner': owner, 'title_proposal': (topic.title.value or '')[:120],
                'numbering': topic.numbering, 'origin': topic.title.origin,
                'parent_key': keys.get(topic.parent_id)}
            cost = len(json.dumps(item, ensure_ascii=False))
            if size + cost <= 4500: selected[point] = item; size += cost
    return list(selected.values())


async def snapshot(claim):
    async with unit_of_work() as session:
        analysis, _, unit, state = await locked(session, claim)
        if not approved(state):raise LeaseLost()
        approval=state.provider_approval
        if approval.mode=='pilot' and state.budget.reserved_attempts>=approval.pilot_stop_after:
            from ai.types import AIError
            raise AIError('pilot_limit',reason='pilot_limit')
        primary = await source_blocks(session, claim.user_id, claim.analysis_id, unit.source_blocks)
        context = await source_blocks(session, claim.user_id, claim.analysis_id, unit.context_blocks)
        metadata = dict(unit.diagnostics.get('metadata', {}))
        metadata['previous_topic_proposals'] = previous_topics(unit, state, context)
        if unit.kind == 'verify':
            target = unit.diagnostics.get('validation', {}).get('expected_reviewed_unit_key')
            proposal = await session.scalar(select(EditalUnit.result).where(EditalUnit.user_id == claim.user_id,
                EditalUnit.analysis_id == claim.analysis_id, EditalUnit.generation == claim.generation,
                EditalUnit.scope_key == claim.scope_key, EditalUnit.unit_key == target,
                EditalUnit.kind.in_(('inventory','detail')), EditalUnit.status == 'completed'))
            if proposal is None: raise EvidenceError('verification_target_unavailable')
            metadata['reviewed_unit_key'] = target; metadata['proposal_to_compare'] = proposal
        return {'primary': primary, 'context': context, 'manifest': state,
            'validation': validation_context(unit, state), 'metadata': metadata}


async def renew(claim):
    async with unit_of_work() as session:
        _, job, unit, _ = await locked(session, claim)
        unit.lease_until = store.utc_now() + timedelta(seconds=LEASE_SECONDS); job.lease_until = unit.lease_until


async def provider_attempt(claim, model, input_hash=None):
    async with unit_of_work() as session:
        analysis, _, unit, state = await locked(session, claim)
        if not approved(state):raise LeaseLost()
        if state.provider_approval.mode=='pilot' and state.budget.reserved_attempts>=state.provider_approval.pilot_stop_after:
            from ai.types import AIError
            raise AIError('pilot_limit',reason='pilot_limit')
        if unit.provider_calls >= 12 or state.budget.reserved_attempts >= state.budget.provider_limit:
            # Raising rolls back the short transaction; the worker then pauses
            # the checkpoint through fail(), before any provider IO occurs.
            from ai.types import AIError
            raise AIError('quota')
        unit.provider_calls += 1; state.budget.reserved_attempts += 1
        history = unit.diagnostics.get('attempts', [])
        unit.diagnostics = {**unit.diagnostics, 'attempts': [*history, {'provider': model.provider,
            'model': model.name, 'at': store.utc_now().isoformat(), 'input_hash': input_hash}]}
        record_pause(state,unit)
        store.write_manifest(analysis, state)


async def complete(claim, result, usage=None, consolidate=None, *, provider=None, model=None):
    async with unit_of_work() as session:
        analysis, job, unit, state = await locked(session, claim)
        primary = await source_blocks(session, claim.user_id, claim.analysis_id, unit.source_blocks)
        context = await source_blocks(session, claim.user_id, claim.analysis_id, unit.context_blocks)
        proposal = CONTRACTS[unit.kind].model_validate(result)
        validate_unit(proposal, primary, context, **validation_context(unit, state))
        unit.result = proposal.model_dump(mode='json'); unit.status = 'completed'; unit.finished_at = store.utc_now()
        unit.lease_token = unit.lease_until = None
        if provider and model:
            unit.diagnostics={**unit.diagnostics,'completed_model':{'provider':provider,'model':model,
                'at':unit.finished_at.isoformat()}}
        allowed = {'total_tokens', 'prompt_tokens', 'completion_tokens', 'totalTokenCount', 'promptTokenCount', 'candidatesTokenCount'}
        reported = {k: v for k, v in (usage or {}).items() if k in allowed and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
        for name, count in reported.items(): state.budget.reported_usage[name] = state.budget.reported_usage.get(name, 0) + count
        if not reported or unit.provider_calls > 1: state.budget.usage_incomplete = True
        state.error_kind = None; state.retry_at = None
        # The shared session factory deliberately disables autoflush. Stage
        # coverage queries must see this checkpoint as completed in this same
        # transaction, rather than leave the last unit looking unfinished.
        await session.flush()
        if consolidate: await consolidate(session, analysis, unit, state)
        stop_pilot(state,unit,validated=bool(unit.provider_calls and provider and model))
        store.write_manifest(analysis, state)
        job.status = 'queued' if state.status == 'processing' else 'completed'
        job.lease_token = job.lease_until = None
        if job.status == 'completed': job.finished_at = store.utc_now()


async def fail(claim, kind, retry_after=30, *, error=None):
    """Safe categories only: no provider body, prompt or exception string."""
    from ai.errors import FAILURES
    known = set(FAILURES) | {'input_limit','evidence_invalid','internal_error','pilot_limit'}
    if kind not in known: kind = 'internal_error'
    async with unit_of_work() as session:
        analysis, job, unit, state = await locked(session, claim)
        now = store.utc_now(); unit.lease_token = unit.lease_until = None
        failure={'http_status':error.http_status,'incompatibility':error.incompatibility,'reason':error.reason,
            'provider_attempted':error.attempted} if error else {}
        retry_failures=unit.diagnostics.get('retry_failures',max(0,unit.attempts-1))+(1 if error is None or error.attempted else 0)
        unit.diagnostics = {**unit.diagnostics, 'last_error': kind, 'reference': error.reference if error else str(uuid4()),
            'failed_at': now.isoformat(),'last_failure':failure,'retry_failures':retry_failures}
        state.error_kind = kind
        if unit.provider_calls: state.budget.usage_incomplete = True
        if kind in ('malformed_output', 'output_truncated', 'input_limit') and unit.kind != 'scope' and len(unit.source_blocks) > 1:
            count = await session.scalar(select(func.count()).select_from(EditalUnit).where(
                EditalUnit.user_id == claim.user_id, EditalUnit.analysis_id == claim.analysis_id,
                EditalUnit.generation == claim.generation, EditalUnit.status != 'split'))
            if count + 1 <= state.budget.leaf_unit_limit:
                unit.status = 'split'; unit.finished_at = now
                parent_source = await source_blocks(session, claim.user_id, claim.analysis_id,
                    [*unit.source_blocks, *unit.context_blocks])
                by_id = {block['id']: block for block in parent_source}
                prior = []
                for ids in split_batch(unit.source_blocks):
                    # A right-hand child still needs the preceding lines and
                    # headings; a smaller output must not erase continuity.
                    candidates = [*prior[-2:], *unit.context_blocks]
                    parent = by_id[ids[0]].get('parent_heading_hint')
                    seen = set()
                    while parent in by_id and parent not in seen and len(seen) < 8:
                        seen.add(parent); candidates.append(parent); parent = by_id[parent].get('parent_heading_hint')
                    context = []; characters = 0
                    for identity in dict.fromkeys(candidates):
                        if identity in ids: continue
                        cost = len(by_id[identity]['text'])
                        if characters + cost <= 3000: context.append(identity); characters += cost
                    session.add(EditalUnit(user_id=claim.user_id, analysis_id=claim.analysis_id, job_id=claim.job_id,
                        generation=claim.generation, scope_key=claim.scope_key, kind=claim.kind,
                        unit_key=unit_key(claim.kind, claim.scope_key, ids, context,
                            {k: unit.diagnostics[k] for k in ('validation', 'metadata') if k in unit.diagnostics}), source_blocks=ids,
                        context_blocks=context, diagnostics={**{k:unit.diagnostics[k] for k in ('validation','metadata') if k in unit.diagnostics},
                            'split_from':str(unit.id)}))
                    prior = ids
            else:
                unit.status = 'failed'; unit.finished_at = now; state.status = 'recoverable_failure'; state.error_kind = 'leaf_unit_limit'
        elif kind in ('quota', 'rate_limit'):
            unit.status = 'quota'; state.status = 'quota_paused'; state.retry_at = now + timedelta(seconds=max(1, min(300, retry_after)))
        elif kind in ('invalid_key', 'permission_denied', 'model_unavailable', 'invalid_request','pilot_limit') or (error is not None and not error.attempted and error.reason in ('cooldown','no_compatible_route')):
            unit.status = 'waiting_provider'; state.status = 'waiting_provider'
            if error and error.reason=='cooldown':state.retry_at=now+timedelta(seconds=error.retry_after)
        elif retry_failures < 3 and kind in ('timeout', 'network_error', 'unavailable'):
            unit.status = 'pending'; unit.available_at = now + timedelta(seconds=max(10 * 2 ** (unit.attempts - 1), min(300, retry_after)))
        else:
            unit.status = 'failed'; unit.finished_at = now; state.status = 'recoverable_failure'
        record_pause(state,unit)
        stop_pilot(state,unit)
        store.write_manifest(analysis, state)
        job.status = 'queued' if state.status == 'processing' else 'completed'
        job.lease_token = job.lease_until = None
        if job.status == 'completed': job.finished_at = now
