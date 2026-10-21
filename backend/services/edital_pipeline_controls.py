"""Owned, revision-checked controls; immutable checkpoints survive user actions."""
from uuid import uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import Field,field_validator
from sqlalchemy import select,func,update,or_
from db.activity import run_activity
from db.models.command import CommandAudit
from db.models.edital_units import EditalUnit
from db.models.files import EditalJob,EditalAnalysis
from edital_pipeline_contracts import (Contract,ContentScope,MAX_PROVIDER_ATTEMPTS,HumanCorrection,ProviderApproval,
    CanonicalFact,CanonicalNamedFact,ProgramDiscipline,ProgramTopic,ProgramRule)
from services import edital_pipeline_store as store,edital_pipeline_progress as progress
from services import edital_pipeline_compile as compiler
from services import edital_pipeline_budget as planning
from ai.schemas import TRANSPORT_VERSION


class Version(Contract):
    revision:int=Field(ge=0)


class SelectRole(Version):
    role_id:str=Field(min_length=1,max_length=64)


class Resume(Version):
    provider_limit:int|None=Field(default=None,ge=1,le=MAX_PROVIDER_ATTEMPTS)
    mode:Literal['pilot','full']|None=None
    diagnostic_case:Literal['text','json','inventory']|None=None


async def owned_job(session,uid,analysis_id):
    row=await session.scalar(select(EditalJob).where(EditalJob.user_id==uid,EditalJob.analysis_id==analysis_id,
        EditalJob.storage_provider==store.MARKER).order_by(EditalJob.created_at.desc(),EditalJob.id.desc()).limit(1).with_for_update())
    if row is None:raise HTTPException(409,{'code':'missing_job','message':'O registro do processamento precisa de conferência técnica; as fontes foram preservadas.'})
    return row


async def capacity(session,uid,job_id):
    active=await session.scalar(select(func.count()).select_from(EditalJob).where(EditalJob.user_id==uid,
        EditalJob.id!=job_id,EditalJob.status.in_(('queued','running'))))
    if active>=2:raise HTTPException(429,{'code':'analysis_concurrency','message':'Aguarde uma das suas duas análises em andamento.'})


async def mutate(user_id,analysis_id,key,body,operation,change):
    uid=store.uuid(user_id);identity=store.uuid(analysis_id);key=store.request_key(key)
    async def apply(session,user):
        analysis=await store.owned_analysis(session,uid,identity,lock=True)
        if analysis.revision!=body.revision:
            raise HTTPException(409,{'code':'stale_revision','message':'A análise mudou. Atualize antes de confirmar esta alteração.'})
        state=store.manifest(analysis);job=await owned_job(session,uid,identity)
        before={'revision':analysis.revision,'status':state.status,'selected_role_id':state.selected_role_id}
        details=await change(session,analysis,job,state)
        store.write_manifest(analysis,state)
        job.status='queued' if state.status=='processing' else 'completed'
        job.lease_token=job.lease_until=None
        labels={'inventory':'Identificando cargos e estrutura','selection':'Escolha um cargo para aprofundar',
            'disciplines':'Conferindo associações do cargo','program':'Extraindo conteúdo do cargo',
            'evidence':'Comparando propostas com as fontes','review':'Disponível para conferência humana',
            'result':'Cargo conferido pelo proprietário','layout':'Texto requer processamento adicional','ingest':'Validando PDF'}
        job.phase=labels[state.phase] if state.status!='cancelled' else 'Cancelado pelo proprietário; fontes e checkpoints preservados'
        job.finished_at=None if job.status=='queued' else store.utc_now()
        session.add(CommandAudit(user_id=uid,event='edital.updated',action=operation,entity_type='edital_analysis',
            entity_id=identity,reason={'basis':'explicit_owner_request'},before=before,
            after={'revision':analysis.revision,'status':state.status,'selected_role_id':state.selected_role_id,**(details or {})}))
        return {'analysis_id':str(identity),'user_id':str(uid),'revision':analysis.revision,'status':state.status,
            'selected_role_id':state.selected_role_id,**(details or {})}
    payload=body.model_dump(mode='json')
    # New optional diagnostics must not invalidate pre-deployment resume receipts.
    if operation=='resume' and payload.get('diagnostic_case') is None:payload.pop('diagnostic_case',None)
    return await run_activity(uid,key,['edital_pipeline',operation,str(identity),payload],apply)


class Reviewed(Version):
    note:str=Field(min_length=3,max_length=1000)

    @field_validator('note')
    @classmethod
    def meaningful_note(cls,value):
        if len(value.strip())<3:raise ValueError('Descreva a conferência realizada.')
        return value.strip()


class FactEdit(Reviewed):
    target:Literal['role','general','discipline','topic','rule']
    identity:str=Field(min_length=1,max_length=64)
    field:Literal['name','code','vacancies','salary','requirements','fact','stage','group','title','target']
    value:str|None=Field(max_length=2000)


class AddGeneral(Reviewed):
    field:Literal['exam_name','board','exam_date','registration_start','registration_end','fee','schedule_event','external_reference']
    value:str=Field(min_length=1,max_length=2000)


class RuleChange(Reviewed):
    action:Literal['add','remove']
    rule_id:str|None=Field(default=None,max_length=64)
    target_scope:Literal['stage','group','discipline']|None=None
    kind:Literal['question_count','weight','penalty','blank_score','time_limit','evaluation_criterion']|None=None
    target:str|None=Field(default=None,min_length=1,max_length=2000)
    value:str|None=Field(default=None,min_length=1,max_length=2000)


class StructureEdit(Reviewed):
    action:Literal['add_discipline','remove_discipline','add_topic','remove_topic','move_topic']
    discipline_id:str|None=Field(default=None,max_length=64)
    topic_id:str|None=Field(default=None,max_length=64)
    parent_id:str|None=Field(default=None,max_length=64)
    title:str|None=Field(default=None,max_length=2000)


class Resolve(Reviewed):
    target:Literal['inventory','scope']
    kind:Literal['finding','issue']
    identity:str=Field(min_length=1,max_length=64)


class BindingEdit(Reviewed):
    section_key:str=Field(min_length=1,max_length=64)
    decision:Literal['include','exclude','ambiguous']


class Confirm(Reviewed):
    acknowledge_document_limits:Literal[True]


class Reanalyze(Reviewed):
    section_keys:list[str]=Field(min_length=1,max_length=60)


def correction(value,note):return HumanCorrection(value=value,note=note.strip(),recorded_at=store.utc_now())


def selected(state):
    if state.selected_role_id not in state.scopes:raise HTTPException(409,'Selecione um cargo primeiro.')
    return state.scopes[state.selected_role_id]


def editable(state):
    scope=selected(state)
    if scope.status!='awaiting_review' or state.status!='awaiting_review':
        raise HTTPException(409,{'code':'review_not_ready','message':'Aguarde os checkpoints de conferência ou reabra a revisão do cargo confirmado.'})
    return scope


def find(items,identity):
    value=next((item for item in items if item.id==identity),None)
    if value is None:raise HTTPException(404,'Informação não encontrada nesta análise.')
    return value


def snapshot(session,analysis,action,before,after):
    session.add(CommandAudit(user_id=analysis.user_id,event='edital.reviewed',action=action,
        entity_type='edital_analysis',entity_id=analysis.id,reason={'basis':'explicit_owner_review'},before=before,after=after))


def invalidate_confirmations(state,role_ids):
    for identity in role_ids:
        scope=state.scopes.get(identity)
        if scope and scope.status=='completed':
            scope.previous_confirmed=scope.program.model_copy(deep=True)
            scope.status='awaiting_review';scope.confirmed_at=None;scope.confirmed_digest=None


async def edit_fact(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        scope=editable(state)
        if body.target=='role':
            item=find(state.inventory.roles,body.identity);allowed=('name','code','vacancies','salary','requirements')
            path=f'roles/{item.id}/{body.field}';corrections=state.inventory.corrections
        elif body.target=='general':
            item=find(state.inventory.facts,body.identity);allowed=('fact',)
            path=f'facts/{item.id}';corrections=state.inventory.corrections
        elif body.target=='discipline':
            item=find(scope.program.disciplines,body.identity);allowed=('name','stage','group')
            path=f'disciplines/{item.id}/{body.field}';corrections=scope.corrections
        elif body.target=='topic':
            item=find([t for d in scope.program.disciplines for t in d.topics],body.identity);allowed=('title',)
            path=f'topics/{item.id}/title';corrections=scope.corrections
        else:
            item=find(scope.program.rules,body.identity);allowed=('fact','target')
            path=f'rules/{item.id}/{body.field}';corrections=scope.corrections
        if body.field not in allowed:raise HTTPException(422,'Campo incompatível com o tipo de informação.')
        if body.field in ('name','title','target') and not(body.value or '').strip():raise HTTPException(422,'A identificação não pode ficar vazia.')
        previous=getattr(item,body.field);record=correction(body.value,body.note)
        corrections[path]=record;setattr(item,body.field,compiler.corrected(previous,record))
        if body.target in ('role','general'):
            invalidate_confirmations(state,[body.identity] if body.target=='role' else state.scopes)
        snapshot(session,analysis,'correct_fact',{'path':path,'fact':previous.model_dump(mode='json')},
            {'path':path,'fact':getattr(item,body.field).model_dump(mode='json')})
        return {'path':path}
    return await mutate(user_id,analysis_id,key,body,'correct_fact',change)


async def add_general(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        editable(state);identity='human-'+uuid4().hex;record=correction(body.value,body.note)
        fact=CanonicalNamedFact(id=identity,key=body.field,fact=compiler.corrected(CanonicalFact(),record))
        state.inventory.facts.append(fact);state.inventory.corrections[f'facts/{identity}']=record
        invalidate_confirmations(state,state.scopes)
        snapshot(session,analysis,'add_general_fact',None,{'fact':fact.model_dump(mode='json')})
        return {'fact_id':identity}
    return await mutate(user_id,analysis_id,key,body,'add_general_fact',change)


async def change_rule(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        scope=editable(state)
        if body.action=='remove':
            rule=find(scope.program.rules,body.rule_id);before=rule.model_dump(mode='json')
            scope.edits.removed_rules.append(rule.id);identity=rule.id
        else:
            if not all((body.target_scope,body.kind,(body.target or '').strip(),(body.value or '').strip())):
                raise HTTPException(422,'Informe a aplicação, o tipo, o destino e o valor da regra.')
            identity='human-'+uuid4().hex;before=None
            rule=ProgramRule(id=identity,target_scope=body.target_scope,kind=body.kind,
                target=compiler.corrected(CanonicalFact(),correction(body.target,body.note)),
                fact=compiler.corrected(CanonicalFact(),correction(body.value,body.note)))
            scope.edits.added_rules.append(rule)
        compiler.overlay(scope)
        snapshot(session,analysis,'edit_exam_rule',{'rule':before},{'action':body.action,'rule':rule.model_dump(mode='json'),'note':body.note})
        return {'rule_id':identity}
    return await mutate(user_id,analysis_id,key,body,'edit_exam_rule',change)


def validate_tree(program):
    seen=set()
    for discipline in program.disciplines:
        nodes={t.id:t for t in discipline.topics}
        for topic in discipline.topics:
            if topic.id in seen:raise HTTPException(422,'Um assunto não pode pertencer a duas disciplinas.')
            seen.add(topic.id);trail=set();point=topic
            while point:
                if point.id in trail or len(trail)>8:raise HTTPException(422,'A hierarquia contém um ciclo ou excede oito níveis.')
                trail.add(point.id)
                if point.parent_id and point.parent_id not in nodes:raise HTTPException(422,'O assunto pai precisa pertencer à mesma disciplina.')
                point=nodes.get(point.parent_id)


async def edit_structure(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        scope=editable(state);before=None;after=None
        if body.action in ('add_discipline','add_topic') and not(body.title or '').strip():raise HTTPException(422,'Informe o nome.')
        if body.action=='add_discipline':
            identity='human-'+uuid4().hex
            added=ProgramDiscipline(id=identity,name=compiler.corrected(CanonicalFact(),correction(body.title,body.note)))
            scope.edits.added_disciplines.append(added);after=added.model_dump(mode='json')
        else:
            discipline=find(scope.program.disciplines,body.discipline_id)
            if body.action=='remove_discipline':
                before=discipline.model_dump(mode='json');scope.edits.removed_disciplines.append(discipline.id)
                scope.edits.removed_topics.extend(t.id for t in discipline.topics if t.id not in scope.edits.removed_topics)
            elif body.action=='add_topic':
                if body.parent_id:find(discipline.topics,body.parent_id)
                added=ProgramTopic(id='human-'+uuid4().hex,parent_id=body.parent_id,
                    title=compiler.corrected(CanonicalFact(),correction(body.title,body.note)))
                scope.edits.added_topics.setdefault(discipline.id,[]).append(added);after=added.model_dump(mode='json')
            else:
                topic=find(discipline.topics,body.topic_id);before=topic.model_dump(mode='json')
                if body.action=='remove_topic':
                    removed={topic.id}
                    while True:
                        expanded=removed|{t.id for t in discipline.topics if t.parent_id in removed}
                        if expanded==removed:break
                        removed=expanded
                    scope.edits.removed_topics.extend(identity for identity in sorted(removed) if identity not in scope.edits.removed_topics)
                else:
                    if body.parent_id:find(discipline.topics,body.parent_id)
                    scope.edits.topic_parents[topic.id]=body.parent_id
                    after={**before,'parent_id':body.parent_id}
        compiler.overlay(scope);validate_tree(scope.program)
        snapshot(session,analysis,'edit_program_structure',{'entity':before},
            {'entity':after,'request':body.model_dump(mode='json'),'note':body.note})
        return {'structure_changed':True}
    return await mutate(user_id,analysis_id,key,body,'edit_program_structure',change)


async def resolve(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        editable(state);target=state.inventory if body.target=='inventory' else selected(state)
        if body.kind=='finding':
            if body.identity not in target.findings:raise HTTPException(404,'Pendência não encontrada.')
            resolutions=target.finding_resolutions
        else:
            issues=target.issues if body.target=='inventory' else target.program.issues
            if body.identity not in {compiler.digest(issue) for issue in issues}:raise HTTPException(404,'Pendência não encontrada.')
            resolutions=target.issue_resolutions
        prior=resolutions.get(body.identity);record=correction('reviewed',body.note);resolutions[body.identity]=record
        snapshot(session,analysis,'resolve_review_issue',{'resolution':prior.model_dump(mode='json') if prior else None},
            {'target':body.target,'kind':body.kind,'identity':body.identity,'resolution':record.model_dump(mode='json')})
        return {'resolved_id':body.identity}
    return await mutate(user_id,analysis_id,key,body,'resolve_review_issue',change)


async def reopen(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        scope=selected(state)
        if scope.status!='completed':raise HTTPException(409,'Este cargo ainda não foi confirmado.')
        snapshot(session,analysis,'reopen_confirmed_review',{'confirmed_digest':scope.confirmed_digest,
            'program':scope.program.model_dump(mode='json'),'inventory':state.inventory.model_dump(mode='json')},{'note':body.note})
        scope.previous_confirmed=scope.program.model_copy(deep=True);scope.confirmed_at=None;scope.confirmed_digest=None
        state.status=scope.status='awaiting_review';state.phase='review'
        return {'previous_confirmation_preserved':True}
    return await mutate(user_id,analysis_id,key,body,'reopen_confirmed_review',change)


def content_digest(state,role_id):
    from db.activity import activity_digest
    role=find(state.inventory.roles,role_id);scope=state.scopes[role_id]
    # Exclude confirmation timestamps and receipts; this identifies factual content.
    def fact(f):return {'value':f.value,'state':f.state,'sources':[s.model_dump(mode='json') for s in f.sources],
        'origin':f.origin,'note':f.human_note}
    return activity_digest({'source':state.source.hash,'role':{k:fact(getattr(role,k)) for k in ('name','code','vacancies','salary','requirements')},
        'general':[{'id':f.id,'key':f.key,'fact':fact(f.fact)} for f in state.inventory.facts],
        'disciplines':[{'id':d.id,'name':fact(d.name),'stage':fact(d.stage),'group':fact(d.group),
            'topics':[{'id':t.id,'parent_id':t.parent_id,'numbering':t.numbering,'title':fact(t.title)} for t in d.topics]} for d in scope.program.disciplines],
        'rules':[{'id':r.id,'target_scope':r.target_scope,'kind':r.kind,'target':fact(r.target),'fact':fact(r.fact)} for r in scope.program.rules]})


async def confirm(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        from services.edital_pipeline_specs import detail_specs
        from services.edital_semantics import blocks_from_pages
        scope=editable(state)
        compiler.review_integrity(scope)
        if state.inventory.status not in ('awaiting_review','completed') or state.source.ocr_required_pages:
            raise HTTPException(409,'A cobertura do documento ainda exige processamento.')
        generations=[state.inventory.generation,scope.generation]
        pending=await session.scalar(select(EditalUnit.id).where(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,
            EditalUnit.generation.in_(generations),EditalUnit.status.notin_(('completed','split'))).limit(1))
        if pending:raise HTTPException(409,'Ainda existem lotes não concluídos; retome ou reanalise antes de confirmar.')
        pages=await session.scalar(select(EditalAnalysis.pages).where(EditalAnalysis.id==analysis.id,EditalAnalysis.user_id==analysis.user_id))
        _,ambiguous=detail_specs(state,state.selected_role_id,blocks_from_pages(pages))
        if ambiguous:raise HTTPException(409,'Confira as associações ambíguas de seções com o cargo.')
        for target,issues in ((state.inventory,state.inventory.issues),(scope,scope.program.issues)):
            if any(k not in target.finding_resolutions for k in target.findings) or any(compiler.digest(i) not in target.issue_resolutions for i in issues):
                raise HTTPException(409,'Resolva as pendências de verificação com uma justificativa antes de confirmar.')
        if not scope.program.disciplines or any(not d.topics for d in scope.program.disciplines):
            raise HTTPException(409,'Confira as disciplinas e seus conteúdos; o programa ainda está incompleto.')
        validate_tree(scope.program);role=find(state.inventory.roles,state.selected_role_id)
        facts=[getattr(role,k) for k in ('name','code','vacancies','salary','requirements')]+[f.fact for f in state.inventory.facts]
        for d in scope.program.disciplines:facts.extend([d.name,d.stage,d.group,*[t.title for t in d.topics]])
        for r in scope.program.rules:facts.extend([r.target,r.fact])
        now=store.utc_now()
        for fact in facts:
            if fact.state=='ambiguous':raise HTTPException(409,'Existem valores ambíguos; escolha ou corrija o valor antes de confirmar.')
            if fact.value is not None and fact.origin=='document' and not fact.sources:raise HTTPException(409,'Um valor documental está sem fonte.')
            fact.verification='confirmed';fact.confirmed_at=now
        scope.confirmed_digest=content_digest(state,state.selected_role_id);scope.confirmed_at=now
        analysis.reviewed_at=now
        state.status=scope.status='completed';state.phase='result';state.error_kind=None
        snapshot(session,analysis,'confirm_role',None,{'role_id':state.selected_role_id,'digest':scope.confirmed_digest,
            'program':scope.program.model_dump(mode='json'),'inventory':state.inventory.model_dump(mode='json'),'note':body.note,
            'acknowledged_document_limits':True})
        return {'confirmed_digest':scope.confirmed_digest}
    return await mutate(user_id,analysis_id,key,body,'confirm_role',change)


async def regenerate(session,analysis,job,state,section_keys,note,*,keep_binding_decisions=False):
    from copy import deepcopy
    from services.edital_pipeline_specs import selected_sections,range_ids
    from services.edital_semantics import blocks_from_pages,discipline_key
    from edital_pipeline_contracts import CompiledProgram,DetailUnit,VerificationUnit
    scope=selected(state)
    if state.inventory.status not in ('awaiting_review','completed'):
        raise HTTPException(409,'Aguarde a descoberta estrutural antes de reanalisar uma seção.')
    sections={compiler.section_key(s):s for s in selected_sections(state,scope)}
    if set(section_keys)-sections.keys():raise HTTPException(404,'Seção não encontrada no conteúdo revisável deste cargo.')
    count=await session.scalar(select(func.count(func.distinct(EditalUnit.generation))).where(EditalUnit.user_id==analysis.user_id,
        EditalUnit.analysis_id==analysis.id,EditalUnit.scope_key==f'role:{state.selected_role_id}'))
    if count>=8:raise HTTPException(409,{'code':'generation_limit','message':'O limite de oito gerações deste cargo foi atingido. Os resultados e o histórico foram preservados.'})
    await capacity(session,analysis.user_id,job.id)
    pages=await session.scalar(select(EditalAnalysis.pages).where(EditalAnalysis.user_id==analysis.user_id,EditalAnalysis.id==analysis.id))
    blocks=blocks_from_pages(pages);positions={b['id']:i for i,b in enumerate(blocks)}
    affected={point for key in section_keys for point in range_ids(sections[key],positions,blocks)}
    old_generation=scope.generation
    before={'role_id':state.selected_role_id,'scope':scope.model_dump(mode='json')}
    old=(await session.scalars(select(EditalUnit).where(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,
        EditalUnit.generation==old_generation,EditalUnit.status=='completed').order_by(EditalUnit.created_at,EditalUnit.id))).all()
    await session.execute(update(EditalUnit).where(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,
        EditalUnit.generation==old_generation,EditalUnit.status.in_(('pending','running','waiting_provider','quota','failed')))
        .values(status='cancelled',lease_token=None,lease_until=None,finished_at=store.utc_now()))
    if scope.confirmed_at:scope.previous_confirmed=scope.program.model_copy(deep=True)
    scope.generation=uuid4();scope.program=CompiledProgram();scope.topic_keys={};scope.observed_rule_ids=[];scope.findings={}
    scope.confirmed_at=None;scope.confirmed_digest=None;scope.status=state.status='processing'
    if not keep_binding_decisions:
        for identity in section_keys:
            if identity not in scope.binding_corrections:scope.bindings.pop(identity,None)
    state.error_kind=None;state.retry_at=None
    reusable=sorted([u for u in old if u.kind=='detail' and not affected.intersection(u.source_blocks)],key=lambda u:u.source_blocks[0])
    # A later untouched window may depend on a parent in the changed section.
    # Recompute the transitive dependency closure rather than reuse an orphan.
    def topic_dependencies(unit):
        detail=DetailUnit.model_validate(unit.result)
        provided={(discipline_key(d),t.key) for d in detail.disciplines for t in d.topics}
        needed={(discipline_key(d),t.parent_key) for d in detail.disciplines for t in d.topics if t.parent_key}
        return provided,needed
    dependencies={u.id:topic_dependencies(u) for u in reusable}
    while reusable:
        available=set().union(*(dependencies[u.id][0] for u in reusable))
        retained=[u for u in reusable if dependencies[u.id][1].issubset(available)]
        if len(retained)==len(reusable):break
        reusable=retained
    ordered=[];known=set()
    while reusable:
        ready=next((u for u in reusable if dependencies[u.id][1].issubset(known|dependencies[u.id][0])),None)
        if ready is None:break # inconsistent old hierarchy is reprocessed, not trusted
        ordered.append(ready);known.update(dependencies[ready.id][0]);reusable.remove(ready)
    reusable=ordered
    keys={u.unit_key for u in reusable}
    reusable.extend(u for u in old if u.kind=='verify' and u.result.get('reviewed_unit_key') in keys)
    for prior in reusable:
        diagnostics=deepcopy(prior.diagnostics);diagnostics.update(reused_from=str(prior.id),reused_at=store.utc_now().isoformat())
        session.add(EditalUnit(user_id=analysis.user_id,analysis_id=analysis.id,job_id=job.id,generation=scope.generation,
            scope_key=prior.scope_key,unit_key=prior.unit_key,kind=prior.kind,status='completed',source_blocks=prior.source_blocks,
            context_blocks=prior.context_blocks,result=prior.result,diagnostics=diagnostics,finished_at=prior.finished_at))
        if prior.kind=='detail':compiler.program(scope,DetailUnit.model_validate(prior.result))
        else:
            checked=VerificationUnit.model_validate(prior.result)
            for finding in checked.findings:
                first=finding.sources[0];identity=compiler.digest(checked.reviewed_unit_key,finding.kind,finding.subject.value or '',first.block_id,first.quote)
                scope.findings[identity]=finding
    compiler.overlay(scope);await session.flush()
    await progress.advance_selected(session,analysis,job.id,state)
    snapshot(session,analysis,'reanalyze_sections',before,{'generation':str(scope.generation),'section_keys':section_keys,
        'note':note,'reused_completed_units':len(reusable),'provider_attempts_preserved':state.budget.reserved_attempts})
    return {'reused_completed_units':len(reusable),'generation':str(scope.generation)}


async def reanalyze(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        return await regenerate(session,analysis,job,state,body.section_keys,body.note)
    return await mutate(user_id,analysis_id,key,body,'reanalyze_sections',change)


async def edit_binding(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        scope=editable(state)
        if body.section_key not in {compiler.section_key(s) for s in state.inventory.sections}:raise HTTPException(404,'Seção não encontrada.')
        before=scope.binding_corrections.get(body.section_key);record=correction(body.decision,body.note)
        scope.binding_corrections[body.section_key]=record
        details=await regenerate(session,analysis,job,state,[body.section_key],body.note,keep_binding_decisions=True)
        snapshot(session,analysis,'correct_section_association',{'section_key':body.section_key,'correction':before.model_dump(mode='json') if before else None},
            {'section_key':body.section_key,'correction':record.model_dump(mode='json')})
        return details
    return await mutate(user_id,analysis_id,key,body,'correct_section_association',change)


async def select_role(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        role=next((r for r in state.inventory.roles if r.id==body.role_id),None)
        if role is None:raise HTTPException(404,'Cargo não encontrado nesta análise.')
        if not(role.name.value or role.code.value):raise HTTPException(409,'Confira a identificação do cargo antes de aprofundar.')
        if state.selected_role_id and state.selected_role_id!=role.id:
            await session.execute(update(EditalUnit).where(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,
                EditalUnit.scope_key==f'role:{state.selected_role_id}',EditalUnit.status=='running')
                .values(status='pending',lease_token=None,lease_until=None,available_at=store.utc_now()))
        state.selected_role_id=role.id
        scope=state.scopes.get(role.id)
        if scope is None:scope=ContentScope(generation=uuid4());state.scopes[role.id]=scope
        if scope.status in ('completed','awaiting_review'):
            state.status=scope.status;state.phase='result' if scope.status=='completed' else 'review'
        else:
            if scope.status in ('quota_paused','waiting_provider','recoverable_failure','cancelled') or state.status in ('quota_paused','waiting_provider','recoverable_failure','cancelled'):
                raise HTTPException(409,{'code':'explicit_resume_required','message':'Este cargo está pausado. Use Retomar ou Reanalisar após conferir o diagnóstico.'})
            await capacity(session,analysis.user_id,job.id)
            state.status=scope.status='processing';state.error_kind=None
            await progress.advance_selected(session,analysis,job.id,state)
        return {'role_id':role.id}
    return await mutate(user_id,analysis_id,key,body,'select_role',change)


async def cancel(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        generations=[state.inventory.generation,*[s.generation for s in state.scopes.values()]]
        await session.execute(update(EditalUnit).where(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,
            EditalUnit.generation.in_(generations),EditalUnit.status.in_(('pending','running','quota','waiting_provider','failed')))
            .values(status='cancelled',lease_token=None,lease_until=None,finished_at=store.utc_now()))
        state.status='cancelled';state.error_kind=None;state.retry_at=None
        if state.inventory.status not in ('awaiting_review','completed'):state.inventory.status='cancelled'
        for scope in state.scopes.values():
            if scope.status not in ('awaiting_review','completed'):scope.status='cancelled'
        return {'checkpoints_preserved':True}
    return await mutate(user_id,analysis_id,key,body,'cancel',change)


async def resume(user_id,analysis_id,key,body):
    async def change(session,analysis,job,state):
        if body.diagnostic_case is not None:
            plan=await planning.forecast(session,analysis,state)
            if body.mode!='pilot' or body.provider_limit is not None or body.diagnostic_case not in plan['diagnostic_cases']:
                raise HTTPException(409,{'code':'diagnostic_unavailable','message':'O diagnóstico exige uma autorização exclusiva de uma chamada, sem ampliar o orçamento e antes de validar a descoberta.'})
        if state.status in ('ocr_required','completed'):
            raise HTTPException(409,{'code':'resume_unavailable','message':'Esta análise não possui processamento retomável neste estado.'})
        if state.retry_at and state.retry_at>store.utc_now():
            raise HTTPException(409,{'code':'retry_not_before','message':'Aguarde o intervalo de tentativa registrado. A liberação da cota do provedor não está confirmada.',
                'retry_at':state.retry_at.isoformat()})
        if await session.scalar(select(EditalUnit.id).where(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,
            EditalUnit.status=='running',EditalUnit.lease_until>store.utc_now()).limit(1)):
            raise HTTPException(409,{'code':'execution_in_progress','message':'Um lote ainda está em execução. Aguarde ou cancele antes de autorizar outra execução.'})
        if body.provider_limit is not None:
            if body.provider_limit<state.budget.reserved_attempts:raise HTTPException(422,'O limite não pode ser menor que as tentativas já reservadas.')
            state.budget.provider_limit=body.provider_limit
        approval=state.provider_approval
        mode=body.mode or ('full' if approval and approval.transport_version==TRANSPORT_VERSION and approval.pilot_validated else None)
        if mode is None:raise HTTPException(409,{'code':'pilot_required','message':'Autorize primeiro um lote piloto de uma chamada; as fontes salvas serão reutilizadas.'})
        if mode=='full':
            if not approval or approval.transport_version!=TRANSPORT_VERSION or not approval.pilot_validated:
                raise HTTPException(409,{'code':'pilot_required','message':'Valide primeiro o lote piloto antes de autorizar os demais lotes.'})
            plan=await planning.forecast(session,analysis,state)
            if plan['extension_required']:raise HTTPException(409,{'code':'planned_units_exceed_remaining_budget','message':'Confira a previsão e confirme um limite suficiente antes de retomar.','plan':plan})
            approval.mode='full'
        else:
            if state.budget.reserved_attempts>=state.budget.provider_limit:
                raise HTTPException(409,{'code':'analysis_provider_budget','message':'O piloto precisa de uma tentativa disponível no limite autorizado.'})
            state.provider_approval=ProviderApproval(transport_version=TRANSPORT_VERSION,mode='pilot',
                pilot_stop_after=state.budget.reserved_attempts+1,diagnostic_case=body.diagnostic_case)
        generations=[state.inventory.generation]
        if state.selected_role_id in state.scopes:generations.append(state.scopes[state.selected_role_id].generation)
        filters=(EditalUnit.user_id==analysis.user_id,EditalUnit.analysis_id==analysis.id,EditalUnit.generation.in_(generations))
        blocked=await session.scalar(select(EditalUnit.id).where(*filters,EditalUnit.status.in_(('failed','cancelled','quota','waiting_provider')),
            EditalUnit.provider_calls>=12).limit(1))
        if blocked:raise HTTPException(409,{'code':'unit_retry_limit','message':'Um lote atingiu o limite de tentativas. Confira a seção e solicite uma reanálise explícita.'})
        await capacity(session,analysis.user_id,job.id)
        await session.execute(update(EditalUnit).where(*filters,EditalUnit.status.in_(('cancelled','quota','waiting_provider','failed')))
            .values(status='pending',lease_token=None,lease_until=None,finished_at=None,available_at=store.utc_now()))
        retry_units=(await session.scalars(select(EditalUnit).where(*filters,EditalUnit.status=='pending'))).all()
        for retry_unit in retry_units:
            retry_unit.diagnostics={**retry_unit.diagnostics,'retry_failures':0,'retry_authorized_at':store.utc_now().isoformat()}
        state.status='processing';state.error_kind=None;state.retry_at=None
        if state.selected_role_id in state.scopes:state.scopes[state.selected_role_id].status='processing'
        await progress.advance_selected(session,analysis,job.id,state)
        return {'provider_limit':state.budget.provider_limit,'completed_units_preserved':True,'execution_mode':mode,'diagnostic_case':body.diagnostic_case}
    return await mutate(user_id,analysis_id,key,body,'resume',change)
