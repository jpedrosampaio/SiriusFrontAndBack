"""Confirmed canonical content enters the existing study catalog atomically.

No provider or schedule generator runs here. The established study/global
planners remain responsible for proposals using real availability.
"""
from datetime import date
from decimal import Decimal,InvalidOperation
from uuid import UUID
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select
from db.models.studies import StudyProgram
from services import edital_programs as programs,edital_pipeline_store as store,edital_pipeline_controls as controls
from services.edital_semantics import normalized
from services.studies_catalog import public


class Import(controls.Version):
    role_id:str=Field(min_length=1,max_length=64)
    confirmed_digest:str=Field(pattern=r'^[0-9a-f]{64}$')
    area_id:UUID
    target_date:date|None=None # personal study goal; never an official exam date
    hours_per_day:float=Field(default=4,ge=.25,le=12)
    days_per_week:int=Field(default=5,ge=1,le=7)
    create_new_version:bool=False


def number(value,*,integer=False):
    if value is None:return None
    try:
        # Normalize only a complete numeric value, never guess from prose.
        numeric=Decimal(value.strip().replace(',','.'))
        if not numeric.is_finite() or numeric<0 or numeric>(10000 if integer else 1000):return None
        if integer:return int(numeric) if numeric==numeric.to_integral_value() else None
        return float(numeric) if numeric>0 else None
    except (InvalidOperation,ValueError,AttributeError):return None


def projection(state,role_id,analysis_id):
    scope=state.scopes[role_id];role=controls.find(state.inventory.roles,role_id)
    def general(key):
        facts=[f.fact.value for f in state.inventory.facts if f.key==key and f.fact.verification=='confirmed' and f.fact.value]
        return facts[0] if len(set(facts))==1 else None
    exam=general('exam_date')
    # Documentary dates remain literal in canonical data; only unambiguous ISO
    # dates feed automatic countdowns. Owners can explicitly correct the date.
    exam_date=programs.exam_date(exam,False)
    concurso={'nome':general('exam_name') or 'Concurso conferido','banca':general('board'),
        'cargo':role.name.value,'vagas':role.vacancies.value,'remuneracao':role.salary.value,
        'escolaridade':role.requirements.value,'data_prova':exam_date.isoformat() if exam_date else None}
    disciplines=[]
    for discipline in scope.program.disciplines:
        roots=[t for t in discipline.topics if t.parent_id is None];nodes=[];content=[]
        def descendants(root):
            for child in discipline.topics:
                if child.parent_id==root.id:
                    yield child;yield from descendants(child)
        for index,root in enumerate(roots):
            children=list(descendants(root));content.append({'assunto':root.title.value,'subtopicos':[
                ((child.numbering+' ') if child.numbering else '')+child.title.value for child in children]})
            for position,node in enumerate([root,*children]):
                nodes.append({**node.model_dump(mode='json'),'topic_key':str(index) if position==0 else f'{index}_{position-1}','position':position})
        item={'nome':discipline.name.value,'grupo':discipline.group.value,'topicos':[t.title.value for t in roots],
            'conteudo_programatico':content,'peso':None,'num_questoes':None,'peso_status':'ausente','num_questoes_status':'ausente',
            'fontes':[s.model_dump(mode='json') for s in discipline.name.sources],
            'universal_edital':{'analysis_id':analysis_id,'role_id':role_id,'discipline_id':discipline.id,
                'confirmed_digest':scope.confirmed_digest,'nodes':nodes,'stage':discipline.stage.model_dump(mode='json'),
                'group':discipline.group.model_dump(mode='json')}}
        for kind,field in (('weight','peso'),('question_count','num_questoes')):
            same_name=[d for d in scope.program.disciplines if normalized(d.name.value or '')==normalized(discipline.name.value or '')]
            rules=[r for r in scope.program.rules if r.target_scope=='discipline' and r.kind==kind
                and normalized(r.target.value or '')==normalized(discipline.name.value or '')]
            if len(same_name)!=1 or len(rules)!=1:continue
            rule=rules[0];value=number(rule.fact.value,integer=kind=='question_count')
            if value is None:continue
            item[field]=value;item[field+'_status']='informado_pelo_usuario' if rule.fact.origin=='human_declared' else 'extraido_com_fonte'
            item[field+'_fonte']=' | '.join(f'p. {s.page}: {s.quote}' for s in rule.fact.sources) or rule.fact.human_note or ''
        disciplines.append(item)
    return concurso,disciplines


async def create(user_id,analysis_id,key,body):
    uid=store.uuid(user_id);identity=store.uuid(analysis_id);key=store.request_key(key)
    from db.activity import replay_activity
    fingerprint=['edital_pipeline_import',str(identity),body.model_dump(mode='json')]
    previous=await replay_activity(uid,key,fingerprint)
    if previous is not None:return previous
    from db.session import unit_of_work
    async with unit_of_work() as session:
        row=await store.owned_analysis(session,uid,identity);state=store.manifest(row)
        scope=state.scopes.get(body.role_id)
        if scope is None or scope.status!='completed' or not scope.confirmed_digest:
            raise HTTPException(409,{'code':'human_confirmation_required','message':'Confira e confirme o cargo antes de criar o programa.'})
        if body.confirmed_digest!=scope.confirmed_digest or controls.content_digest(state,body.role_id)!=scope.confirmed_digest:
            raise HTTPException(409,{'code':'confirmation_changed','message':'A confirmação não corresponde ao conteúdo atual. Confira o cargo novamente.'})
        concurso,disciplines=projection(state,body.role_id,str(identity));filename=row.filename
        metadata={'universal_edital':{'analysis_id':str(identity),'role_id':body.role_id,'confirmed_digest':scope.confirmed_digest,
            'document_hash':state.source.hash,'rules':[r.model_dump(mode='json') for r in scope.program.rules],
            'general_facts':[f.model_dump(mode='json') for f in state.inventory.facts],
            'program':scope.program.model_dump(mode='json'),'personal_target_date':body.target_date.isoformat() if body.target_date else None}}
    context={}
    async def before(session,user):
        analysis=await store.owned_analysis(session,uid,identity,lock=True);current=store.manifest(analysis);scope=current.scopes.get(body.role_id)
        if scope is None or scope.status!='completed' or scope.confirmed_digest!=body.confirmed_digest or controls.content_digest(current,body.role_id)!=body.confirmed_digest:
            raise HTTPException(409,'A confirmação mudou. Atualize antes de importar.')
        matching=(StudyProgram.user_id==uid,
            StudyProgram.edital_data['universal_edital']['document_hash'].astext==current.source.hash,
            StudyProgram.edital_data['universal_edital']['role_id'].astext==body.role_id)
        existing=await session.scalar(select(StudyProgram.id).where(*matching,
            StudyProgram.edital_data['universal_edital']['confirmed_digest'].astext==body.confirmed_digest).limit(1))
        any_previous=existing or await session.scalar(select(StudyProgram.id).where(*matching).limit(1))
        previous_id=scope.imports.get(body.confirmed_digest) or (str(existing) if existing else None)
        if previous_id:
            previous=await session.scalar(select(StudyProgram).where(StudyProgram.user_id==uid,StudyProgram.id==store.uuid(previous_id)))
            if previous is None:raise HTTPException(409,'O programa importado não está disponível; confira o histórico antes de criar outro.')
            return {'success':True,'program':public(previous),'replayed':True,'xp_earned':0,'schedules_created':0,
                'message':'Este conteúdo já foi importado. O programa e seu histórico foram preservados.','archived':previous.archived_at is not None}
        if analysis.revision!=body.revision:raise HTTPException(409,'A análise mudou; atualize antes de criar o programa.')
        if (scope.imports or any_previous) and not body.create_new_version:raise HTTPException(409,{'code':'explicit_new_version_required',
            'message':'Uma versão anterior deste cargo já foi importada. Confirme a criação de um programa separado, preservando o anterior.'})
        context.update(analysis=analysis,state=current,first_import=not(scope.imports or any_previous))
    async def after(session,user,program,result):
        current=context['state'];current.scopes[body.role_id].imports[body.confirmed_digest]=str(program.id)
        store.write_manifest(context['analysis'],current)
        controls.snapshot(session,context['analysis'],'import_confirmed_program',None,{'role_id':body.role_id,'program_id':str(program.id),
            'confirmed_digest':body.confirmed_digest,'schedule_created':False,'prior_programs_preserved':True})
    return await programs.create(str(uid),key,fingerprint,
        area_id=str(body.area_id),target_date=body.target_date.isoformat() if body.target_date else None,hours=body.hours_per_day,
        days=body.days_per_week,concurso=concurso,disciplines=disciplines,weekly=[],strategy={'resumo':
            'Conteúdo conferido. Use o planejamento de estudos existente para propor horários conforme sua disponibilidade.'},filename=filename,
        cargo={'nome':concurso['cargo'],'role_id':body.role_id},analysis_id=str(identity),before_create=before,after_create=after,
        metadata_extra=metadata,verified_target=True,award_xp=lambda:context['first_import'])
