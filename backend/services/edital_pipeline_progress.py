"""Atomic stage advancement inside the existing owned analysis/job transaction."""
from sqlalchemy import select, func
from db.models.files import EditalAnalysis
from db.models.edital_units import EditalUnit
from edital_pipeline_contracts import InventoryUnit, ScopeUnit, DetailUnit, VerificationUnit
from services.edital_semantics import blocks_from_pages, unit_key
from services import edital_pipeline_compile as compiler
from services.edital_pipeline_specs import scope_specs, detail_specs, UnitSpec


async def unfinished(session, analysis, generation, kind):
    return await session.scalar(select(func.count()).select_from(EditalUnit).where(
        EditalUnit.user_id == analysis.user_id, EditalUnit.analysis_id == analysis.id,
        EditalUnit.generation == generation, EditalUnit.kind == kind,
        EditalUnit.status.notin_(('completed', 'split'))))


async def emit(session, analysis, job_id, state, role_id, specs):
    scope = state.scopes[role_id] if role_id else state.inventory
    scope_key = f'role:{role_id}' if role_id else 'inventory'
    existing = set((await session.scalars(select(EditalUnit.unit_key).where(EditalUnit.user_id == analysis.user_id,
        EditalUnit.analysis_id == analysis.id, EditalUnit.generation == scope.generation))).all())
    # Reanalysis seeds immutable, unaffected leaves in a new generation. Emit
    # only uncovered source intervals, including when old parent lots split.
    covered=set();checked={}
    if any(spec.kind in ('detail','verify') for spec in specs):
        sources=(await session.execute(select(EditalUnit.kind,EditalUnit.source_blocks,EditalUnit.diagnostics).where(EditalUnit.user_id==analysis.user_id,
            EditalUnit.analysis_id==analysis.id,EditalUnit.generation==scope.generation,EditalUnit.kind.in_(('detail','verify')),
            EditalUnit.status!='split'))).all()
        for kind,source,diagnostics in sources:
            if kind=='detail':covered.update(source)
            else:checked.setdefault(diagnostics.get('validation',{}).get('expected_reviewed_unit_key'),set()).update(source)
        residual=[]
        for spec in specs:
            if spec.kind not in ('detail','verify'):residual.append(spec);continue
            excluded=covered if spec.kind=='detail' else checked.get(spec.validation.get('expected_reviewed_unit_key'),set())
            current=[]
            for point in [*spec.primary,None]:
                if point is None or point in excluded:
                    if current:residual.append(UnitSpec(spec.kind,current,spec.context,spec.validation,spec.metadata));current=[]
                else:current.append(point)
        specs=residual
    planned = []
    for spec in specs:
        context = {'validation': spec.validation, 'metadata': spec.metadata}
        key = unit_key(spec.kind, scope_key, spec.primary, spec.context, context)
        if key not in existing:
            planned.append((key, spec, context)); existing.add(key)
    leaves = await session.scalar(select(func.count()).select_from(EditalUnit).where(
        EditalUnit.user_id == analysis.user_id, EditalUnit.analysis_id == analysis.id, EditalUnit.status != 'split'))
    if leaves + len(planned) > state.budget.leaf_unit_limit:
        state.status = scope.status = 'recoverable_failure'; state.error_kind = 'analysis_checkpoint_limit'
        return False
    if state.budget.reserved_attempts + len(planned) > state.budget.provider_limit:
        state.status = scope.status = 'quota_paused'; state.error_kind = 'planned_units_exceed_remaining_budget'
        return False
    for key, spec, context in planned:
        session.add(EditalUnit(user_id=analysis.user_id, analysis_id=analysis.id, job_id=job_id,
            generation=scope.generation, scope_key=scope_key, unit_key=key, kind=spec.kind,
            source_blocks=spec.primary, context_blocks=spec.context, diagnostics=context))
    await session.flush()
    return True


async def ensure_checks(session, analysis, job_id, state, role_id=None):
    scope = state.scopes[role_id] if role_id else state.inventory
    scope_key = f'role:{role_id}' if role_id else 'inventory'
    parent_kind = 'detail' if role_id else 'inventory'
    parents = (await session.execute(select(EditalUnit.unit_key, EditalUnit.source_blocks, EditalUnit.context_blocks).where(
        EditalUnit.user_id == analysis.user_id, EditalUnit.analysis_id == analysis.id,
        EditalUnit.generation == scope.generation, EditalUnit.scope_key == scope_key,
        EditalUnit.kind == parent_kind, EditalUnit.status == 'completed'))).all()
    specs = [UnitSpec('verify', list(primary), list(context), {'expected_reviewed_unit_key': key},
        {'reviewed_kind': parent_kind}) for key, primary, context in parents]
    return await emit(session, analysis, job_id, state, role_id, specs)


async def inventory_ready(session, analysis, job_id, state):
    if not await ensure_checks(session, analysis, job_id, state): return False
    if await unfinished(session, analysis, state.inventory.generation, 'inventory'):
        state.inventory.status = 'processing'; state.phase = 'inventory'; return False
    if await unfinished(session, analysis, state.inventory.generation, 'verify'):
        state.inventory.status = 'processing'; state.phase = 'evidence'; return False
    state.inventory.status = 'awaiting_review'
    return True


async def advance_selected(session, analysis, job_id, state):
    if not await inventory_ready(session, analysis, job_id, state): return
    role_id = state.selected_role_id
    if not role_id:
        state.status = 'awaiting_review'; state.phase = 'selection'; return
    scope = state.scopes[role_id]
    if scope.status == 'completed':
        state.status = 'completed'; state.phase = 'result'; return
    pages = await session.scalar(select(EditalAnalysis.pages).where(EditalAnalysis.user_id == analysis.user_id,
        EditalAnalysis.id == analysis.id))
    blocks = blocks_from_pages(pages or [])
    # Existing bindings are skipped by scope_specs; completed work is not sent
    # again just because a request/worker is resumed.
    bindings = scope_specs(state, role_id, blocks)
    if not await emit(session, analysis, job_id, state, role_id, bindings): return
    if await unfinished(session, analysis, scope.generation, 'scope'):
        state.status = scope.status = 'processing'; state.phase = 'disciplines'; return
    details, ambiguous = detail_specs(state, role_id, blocks)
    if not await emit(session, analysis, job_id, state, role_id, details): return
    if await unfinished(session, analysis, scope.generation, 'detail'):
        state.status = scope.status = 'processing'; state.phase = 'program'; return
    if not await ensure_checks(session, analysis, job_id, state, role_id): return
    if await unfinished(session, analysis, scope.generation, 'verify'):
        state.status = scope.status = 'processing'; state.phase = 'evidence'; return
    state.status = scope.status = 'awaiting_review'; state.phase = 'review'
    compiler.review_integrity(scope)
    if ambiguous:
        state.error_kind = 'section_associations_require_review'
    elif not scope.program.disciplines:
        state.error_kind = 'selected_program_not_identified'
    elif any(key not in scope.finding_resolutions for key in scope.findings):
        state.error_kind = 'verification_findings_require_review'
    elif any(key not in state.inventory.finding_resolutions for key in state.inventory.findings):
        state.error_kind = 'inventory_findings_require_review'
    elif scope.program.issues:
        state.error_kind = 'program_issues_require_review'
    else: state.error_kind = None


async def consolidate(session, analysis, unit, state):
    """The state argument comes from the commit-time lock, never a claim snapshot."""
    if unit.kind == 'inventory':
        compiler.inventory(state.inventory, InventoryUnit.model_validate(unit.result))
        if not await inventory_ready(session, analysis, unit.job_id, state): return
    elif unit.kind == 'verify':
        target = state.inventory if unit.scope_key == 'inventory' else state.scopes[unit.scope_key.removeprefix('role:')]
        checked = VerificationUnit.model_validate(unit.result)
        for finding in checked.findings:
            first = finding.sources[0]
            identity = compiler.digest(checked.reviewed_unit_key, finding.kind, finding.subject.value or '',
                first.block_id, first.quote)
            target.findings[identity] = finding
    else:
        role_id = unit.scope_key.removeprefix('role:'); scope = state.scopes[role_id]
        if unit.kind == 'scope':
            for binding in ScopeUnit.model_validate(unit.result).bindings:
                previous = scope.bindings.get(binding.section_key)
                if previous and previous.decision != binding.decision:
                    scope.bindings[binding.section_key] = binding.model_copy(update={
                        'decision': 'ambiguous', 'reason': 'Propostas divergentes de associação exigem conferência.'})
                else: scope.bindings[binding.section_key] = binding
        else: compiler.program(scope, DetailUnit.model_validate(unit.result))
    if not state.inventory.roles and not await unfinished(session, analysis, state.inventory.generation, 'inventory'):
        state.status = 'recoverable_failure'; state.error_kind = 'role_inventory_not_identified'; return
    await advance_selected(session, analysis, unit.job_id, state)
