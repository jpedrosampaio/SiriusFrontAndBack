"""Owned durable PDF intake and lightweight incremental progress/source reads."""
import asyncio
import hashlib
import logging
import re
from uuid import uuid4
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from db.models.files import EditalAnalysis
from db.models.edital_units import EditalUnit
from db.session import unit_of_work
from edital_pipeline_contracts import PIPELINE_VERSION, MAX_PAGES
from services.auth_routes import account
from services import edital_pipeline_store as store
from services import edital_pipeline_controls as controls,edital_pipeline_compile as compiler
from services.edital_pdf import extract_pdf, PDFInputError, ExtractionMetrics, MAX_BYTES
from services.edital_pipeline_diagnostics import message as diagnostic_message
from services.edital_pipeline_budget import forecast

router=APIRouter(prefix='/study/edital-pipeline')
_wake=None
_input_gate=asyncio.Semaphore(1)
PDF_ERRORS={
    'invalid_pdf':'Selecione um arquivo PDF íntegro.',
    'encrypted_pdf':'O PDF está protegido por senha. Envie uma cópia desbloqueada.',
    'page_limit':'O PDF excede o limite de páginas suportado.',
    'file_size_limit':'O PDF excede o limite de 20 MB.',
    'pdf_size_limit':'O PDF excede o limite de 20 MB.',
    'extraction_resource_limit':'A extração excedeu os limites de recursos. Divida o documento preservando suas referências.',
    'extraction_process_failed':'O processo de extração foi interrompido. Tente novamente; se persistir, informe a referência do erro.',
    'extraction_result_limit':'O texto extraído excedeu o limite operacional.',
    'ingestion_busy':'Outra validação está em andamento. Tente novamente em instantes.',
    'parser_security_upgrade_required':'O backend precisa atualizar o processador de PDFs antes de analisar este arquivo.',
    'unreadable_pdf':'O PDF não pôde ser lido. Confira sua integridade ou exporte uma nova cópia.',
    'no_pages':'O PDF não contém páginas legíveis.',
    'extraction_timeout':'A extração local excedeu o tempo disponível. Nenhuma chamada de IA foi feita.',
    'invalid_geometry':'A geometria de páginas do PDF não é suportada.',
    'page_dimensions_limit':'As dimensões das páginas excedem o limite operacional.',
    'page_complexity_limit':'Uma página excede o limite de complexidade suportado.',
    'table_limit':'O PDF excede o limite de tabelas suportado nesta extração.',
    'block_limit':'O PDF excede o limite de blocos de texto suportado.',
    'text_limit':'O PDF excede o limite de texto suportado.',
    'memory_limit':'A extração local excedeu o limite de memória disponível.',
    'page_coverage':'Não foi possível conferir todas as páginas. Nenhuma análise completa foi publicada.',
    'parser_internal_error':'O extrator não concluiu o processamento. Consulte a referência do erro.',
    'extraction_failed':'Não foi possível extrair este PDF. Nenhuma chamada de IA foi feita.',
}


def configure(wake):
    global _wake
    _wake=wake


def wake():
    if _wake:
        try:_wake()
        except Exception:logging.warning('edital_queue wake_pending')


async def fail_input(uid,intake,code):
    if not intake or not intake.get('token'):return
    try:await store.fail_intake(uid,intake['job_id'],intake['token'],code)
    except Exception:
        # A database outage must not turn a safe intake error into a traceback
        # containing SQL/provider details. The durable lease still fences retry.
        logging.warning('edital_ingestion recovery_pending')


@router.post('',status_code=202)
async def submit(request:Request,file:UploadFile=File(...),force:bool=Query(False)):
    auth=await account(request);uid=store.uuid(auth['user_id'])
    if _wake is None:raise HTTPException(503,{'code':'incremental_unavailable','message':'O processamento incremental está temporariamente indisponível.'})
    key=store.request_key(request.headers.get('Idempotency-Key'))
    filename=(file.filename or '').replace('\\','/').rsplit('/',1)[-1][:300]
    if not filename.lower().endswith('.pdf'):raise HTTPException(422,{'code':'invalid_pdf','message':PDF_ERRORS['invalid_pdf']})
    try:await asyncio.wait_for(_input_gate.acquire(),timeout=1)
    except asyncio.TimeoutError:raise HTTPException(429,{'code':'ingestion_busy','message':PDF_ERRORS['ingestion_busy']}) from None
    intake=None
    try:
        content=await file.read(MAX_BYTES+1)
        if len(content)>MAX_BYTES:raise HTTPException(413,{'code':'pdf_size_limit','message':PDF_ERRORS['pdf_size_limit']})
        if not content.startswith(b'%PDF-'):raise HTTPException(422,{'code':'invalid_pdf','message':PDF_ERRORS['invalid_pdf']})
        intake=await store.reserve_intake(uid,hashlib.sha256(content).hexdigest(),filename,force,key)
        if intake['action']=='accepted':return {'user_id':str(uid),**intake,'pipeline':PIPELINE_VERSION}
        if intake['action']=='in_progress':
            raise HTTPException(409,{'code':'input_validating','message':'O envio ainda está sendo validado. Aguarde antes de tentar novamente.',
                'job_id':intake['job_id']})
        document=await extract_pdf(content)
        result=await store.persist_input(uid,intake['job_id'],intake['token'],document)
        wake()
        return {'user_id':str(uid),**result,'pipeline':PIPELINE_VERSION}
    except PDFInputError as error:
        code=error.code if error.code in PDF_ERRORS else 'extraction_failed'
        reference=error.metrics.reference if isinstance(error.metrics,ExtractionMetrics) else uuid4().hex[:12]
        await fail_input(uid,intake,code)
        logging.warning('edital_ingestion failed code=%s reference=%s',code,reference)
        status=429 if code=='ingestion_busy' else 503 if code in ('parser_internal_error','parser_security_upgrade_required','extraction_process_failed') else 422
        raise HTTPException(status,{'code':code,'message':PDF_ERRORS[code],'reference':reference}) from None
    except asyncio.CancelledError:
        # Keep the 90s database admission while the shielded parser may still
        # run (its child deadline is60s). A retry cannot launch a second parser.
        raise
    except HTTPException:
        await fail_input(uid,intake,'input_not_committed')
        raise
    except Exception:
        reference=uuid4().hex[:12]
        await fail_input(uid,intake,'input_not_committed')
        logging.warning('edital_ingestion internal_failure reference=%s',reference)
        raise HTTPException(503,{'code':'input_not_committed','message':'Não foi possível confirmar o texto salvo. Reenvie o mesmo PDF para recuperar o estado.',
            'reference':reference}) from None
    finally:
        try:await file.close()
        except Exception:logging.warning('edital_ingestion upload_cleanup_pending')
        finally:_input_gate.release()


def active_generations(state):
    values=[state.inventory.generation]
    if state.selected_role_id in state.scopes:values.append(state.scopes[state.selected_role_id].generation)
    return values


@router.get('/{analysis_id}')
async def get_state(request:Request,analysis_id:str):
    auth=await account(request);uid=store.uuid(auth['user_id']);identity=store.uuid(analysis_id)
    async with unit_of_work() as session:
        # Do not transfer/parse the potentially large canonical manifest on an
        # unchanged poll, and never return304 before checking ownership.
        revision=await session.scalar(select(EditalAnalysis.revision).where(EditalAnalysis.user_id==uid,
            EditalAnalysis.id==identity,EditalAnalysis.analysis_version=='6'))
        if revision is None:raise HTTPException(404,'Análise incremental não encontrada.')
        etag=f'"edital-v6-{identity}-{revision}"'
        headers={'ETag':etag,'Cache-Control':'private, no-store'}
        if request.headers.get('If-None-Match')==etag:return Response(status_code=304,headers=headers)
        row=await store.owned_analysis(session,uid,identity);state=store.manifest(row)
        etag=f'"edital-v6-{identity}-{row.revision}"';headers['ETag']=etag
        filters=(EditalUnit.user_id==uid,EditalUnit.analysis_id==identity,EditalUnit.generation.in_(active_generations(state)))
        groups=(await session.execute(select(EditalUnit.kind,EditalUnit.status,func.count()).where(*filters)
            .group_by(EditalUnit.kind,EditalUnit.status))).all()
        latest=(await session.execute(select(EditalUnit.id,EditalUnit.kind,EditalUnit.status,EditalUnit.attempts,
            EditalUnit.provider_calls,EditalUnit.diagnostics,EditalUnit.available_at).where(*filters)
            .order_by(EditalUnit.updated_at.desc(),EditalUnit.id.desc()).limit(20))).all()
        diagnostics=[]
        for unit_id,kind,status,attempts,calls,details,available in latest:
            observed=(details.get('attempts') or [None])[-1]
            completed=details.get('completed_model')
            diagnostics.append({'unit_id':str(unit_id),'kind':kind,'status':status,'attempts':attempts,'provider_calls':calls,
                'reused_checkpoint':bool(details.get('reused_from')),
                'last_observed_model':None if observed is None else {k:observed.get(k) for k in ('provider','model','at')},
                'last_completed_model':None if not isinstance(completed,dict) else {k:completed.get(k) for k in ('provider','model','at')},
                'error_kind':details.get('last_error'),'error_message':diagnostic_message(details.get('last_error')),
                'reference':details.get('reference'),'next_attempt_at':available})
            failure=details.get('last_failure',{})
            diagnostics[-1]['failure']={key:failure.get(key) for key in ('http_status','incompatibility','reason','provider_attempted','request_format','schema_sha256','schema_bytes')}
        data={'analysis_id':str(row.id),'user_id':str(uid),'filename':row.filename,'revision':row.revision,
            'pipeline':PIPELINE_VERSION,'manifest':state.model_dump(mode='json'),
            'progress':[{'kind':kind,'status':status,'units':count} for kind,status,count in groups],
            'diagnostics':diagnostics,'error_message':diagnostic_message(state.error_kind),'worker_configured':_wake is not None,'original_available':False,
            'execution_plan':await forecast(session,row,state)}
        scope=state.scopes.get(state.selected_role_id)
        def section_summary(section):
            # pdf-layout/1 emits page-qualified block identities. This is page
            # navigation, not an inferred documentary fact or a citation.
            match=re.fullmatch(r'p(\d{4})-b\d{4}',section.block_id)
            return {'key':compiler.section_key(section),'source_page':int(match[1]) if match else None,**section.model_dump(mode='json')}
        data['review']={'sections':[section_summary(s) for s in state.inventory.sections],
            'inventory_issues':[{'id':compiler.digest(issue),'message':issue} for issue in state.inventory.issues],
            'program_issues':[{'id':compiler.digest(issue),'message':issue} for issue in scope.program.issues] if scope else []}
        return JSONResponse(jsonable_encoder(data),headers=headers)


@router.get('/{analysis_id}/source/{page}')
async def get_page(request:Request,analysis_id:str,page:int):
    auth=await account(request);uid=store.uuid(auth['user_id']);identity=store.uuid(analysis_id)
    if not 1<=page<=MAX_PAGES:raise HTTPException(404,'Página não encontrada.')
    async with unit_of_work() as session:
        result=(await session.execute(select(EditalAnalysis.pages[page-1]).where(EditalAnalysis.user_id==uid,
            EditalAnalysis.id==identity,EditalAnalysis.analysis_version=='6'))).one_or_none()
        if result is None or result[0] is None:raise HTTPException(404,'Página não encontrada.')
        value=result[0]
        return JSONResponse({'page':page,'text':'\n'.join(b['text'] for b in value.get('blocks',[])),
            'blocks':value.get('blocks',[]),'quality':value['quality'],'original_available':False},
            headers={'Cache-Control':'private, no-store'})


async def command(request,analysis_id,body,handler):
    auth=await account(request)
    result=await handler(auth['user_id'],analysis_id,request.headers.get('Idempotency-Key'),body)
    if _wake and result.get('status')=='processing':_wake()
    return JSONResponse(jsonable_encoder(result),headers={'Cache-Control':'private, no-store'})


@router.post('/{analysis_id}/select-role')
async def select_role(request:Request,analysis_id:str,body:controls.SelectRole):return await command(request,analysis_id,body,controls.select_role)


@router.post('/{analysis_id}/cancel')
async def cancel(request:Request,analysis_id:str,body:controls.Version):return await command(request,analysis_id,body,controls.cancel)


@router.post('/{analysis_id}/resume')
async def resume(request:Request,analysis_id:str,body:controls.Resume):return await command(request,analysis_id,body,controls.resume)


@router.post('/{analysis_id}/facts')
async def facts(request:Request,analysis_id:str,body:controls.FactEdit):return await command(request,analysis_id,body,controls.edit_fact)


@router.post('/{analysis_id}/general-facts')
async def add_general(request:Request,analysis_id:str,body:controls.AddGeneral):return await command(request,analysis_id,body,controls.add_general)


@router.post('/{analysis_id}/structure')
async def structure(request:Request,analysis_id:str,body:controls.StructureEdit):return await command(request,analysis_id,body,controls.edit_structure)


@router.post('/{analysis_id}/rules')
async def rules(request:Request,analysis_id:str,body:controls.RuleChange):return await command(request,analysis_id,body,controls.change_rule)


@router.post('/{analysis_id}/resolve')
async def resolve(request:Request,analysis_id:str,body:controls.Resolve):return await command(request,analysis_id,body,controls.resolve)


@router.post('/{analysis_id}/binding')
async def binding(request:Request,analysis_id:str,body:controls.BindingEdit):return await command(request,analysis_id,body,controls.edit_binding)


@router.post('/{analysis_id}/reanalyze')
async def reanalyze(request:Request,analysis_id:str,body:controls.Reanalyze):return await command(request,analysis_id,body,controls.reanalyze)


@router.post('/{analysis_id}/confirm')
async def confirm(request:Request,analysis_id:str,body:controls.Confirm):return await command(request,analysis_id,body,controls.confirm)


@router.post('/{analysis_id}/reopen')
async def reopen(request:Request,analysis_id:str,body:controls.Reviewed):return await command(request,analysis_id,body,controls.reopen)


from services.edital_pipeline_import import Import,create as import_program


@router.post('/{analysis_id}/import')
async def create_program(request:Request,analysis_id:str,body:Import):return await command(request,analysis_id,body,import_program)


@router.get('/{analysis_id}/import-candidates')
async def prior_programs(request:Request,analysis_id:str,offset:int=Query(0,ge=0,le=10000)):
    from services.edital_pipeline_import import document_programs
    from db.models.studies import StudyProgram
    auth=await account(request);uid=store.uuid(auth['user_id']);identity=store.uuid(analysis_id)
    async with unit_of_work() as session:
        document_hash=await session.scalar(select(EditalAnalysis.content_hash).where(EditalAnalysis.user_id==uid,
            EditalAnalysis.id==identity,EditalAnalysis.analysis_version=='6'))
        if document_hash is None:raise HTTPException(404,'Análise não encontrada.')
        rows=(await session.execute(select(StudyProgram.id,StudyProgram.name,StudyProgram.created_at,StudyProgram.archived_at)
            .where(*document_programs(uid,document_hash)).order_by(StudyProgram.created_at.desc(),StudyProgram.id.desc())
            .offset(offset).limit(21))).all()
        return JSONResponse(jsonable_encoder({'programs':[{'program_id':str(r.id),'name':r.name,'created_at':r.created_at,
            'archived':r.archived_at is not None} for r in rows[:20]],'next_offset':offset+20 if len(rows)>20 else None}),
            headers={'Cache-Control':'private, no-store'})


@router.get('/{analysis_id}/history')
async def history(request:Request,analysis_id:str,offset:int=Query(0,ge=0,le=10000),limit:int=Query(20,ge=1,le=30)):
    from db.models.command import CommandAudit
    auth=await account(request);uid=store.uuid(auth['user_id']);identity=store.uuid(analysis_id)
    async with unit_of_work() as session:
        await store.owned_analysis(session,uid,identity)
        rows=(await session.execute(select(CommandAudit.id,CommandAudit.action,CommandAudit.created_at,
            func.coalesce(CommandAudit.after['note'].astext,CommandAudit.after['fact']['human_note'].astext,
                CommandAudit.after['resolution']['note'].astext)).where(CommandAudit.user_id==uid,CommandAudit.entity_id==identity,
                CommandAudit.entity_type=='edital_analysis',CommandAudit.event=='edital.reviewed')
            .order_by(CommandAudit.created_at.desc(),CommandAudit.id.desc()).offset(offset).limit(limit+1))).all()
        return JSONResponse(jsonable_encoder({'history':[{'id':str(r.id),'action':r.action,'at':r.created_at,
            'note':r[3]} for r in rows[:limit]],'has_more':len(rows)>limit}),
            headers={'Cache-Control':'private, no-store'})


@router.get('/{analysis_id}/history/{audit_id}')
async def history_entry(request:Request,analysis_id:str,audit_id:str):
    from db.models.command import CommandAudit
    auth=await account(request);uid=store.uuid(auth['user_id']);identity=store.uuid(analysis_id)
    async with unit_of_work() as session:
        await store.owned_analysis(session,uid,identity)
        row=(await session.execute(select(CommandAudit.before,CommandAudit.after).where(CommandAudit.user_id==uid,
            CommandAudit.entity_id==identity,CommandAudit.entity_type=='edital_analysis',CommandAudit.event=='edital.reviewed',
            CommandAudit.id==store.uuid(audit_id)))).one_or_none()
        if row is None:raise HTTPException(404,'Revisão não encontrada.')
        return JSONResponse(jsonable_encoder({'before':row.before,'after':row.after}),headers={'Cache-Control':'private, no-store'})
