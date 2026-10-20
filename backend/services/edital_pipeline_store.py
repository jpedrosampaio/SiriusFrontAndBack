"""Owned durable intake/checkpoints, integrated with the existing edital jobs.

No provider or parser executes inside these transactions. The intake receipt
acknowledges durable input only after the extracted representation commits.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func,update
from sqlalchemy.orm import defer
from db.activity import run_activity
from db.models.files import EditalAnalysis,EditalJob
from db.models.edital_units import EditalUnit
from db.models.identity import ActivityReceipt
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work
from edital_pipeline_contracts import (PIPELINE_VERSION,PipelineManifest,DocumentSummary,InventoryState,MAX_PROVIDER_ATTEMPTS,
    JOB_IR_PROVIDER,JOB_INGEST_PROVIDER)
from services.edital_semantics import batches,blocks_from_pages,block_dict,unit_key
from services.edital_pipeline_inputs import inventory_batches

MARKER=JOB_IR_PROVIDER
INGESTING=JOB_INGEST_PROVIDER
INGEST_LOCK=731030407
MAX_OWNED_BYTES=64*1024*1024


def utc_now():return datetime.now(timezone.utc)


def uuid(value):
    try:return UUID(str(value))
    except (ValueError,TypeError,AttributeError):raise HTTPException(404,'Análise não encontrada.') from None


def request_key(value):
    try:return str(UUID(value))
    except (ValueError,TypeError,AttributeError):raise HTTPException(422,{'code':'idempotency_required','message':'O envio exige uma chave de idempotência UUID.'}) from None


def manifest(row):
    if row.analysis_version!='6' or row.structured_payload.get('pipeline')!=PIPELINE_VERSION:
        raise HTTPException(409,{'code':'legacy_analysis','message':'Esta análise usa o fluxo histórico.'})
    try:return PipelineManifest.model_validate(row.structured_payload['universal'])
    except (ValidationError,KeyError,TypeError):
        raise HTTPException(409,{'code':'analysis_state_invalid','message':'O estado salvo precisa de conferência técnica; os registros foram preservados.'}) from None


def write_manifest(row,state):
    # Pydantic collection limits apply on validation, not on later list/dict
    # mutation. Never commit a consolidated manifest that cannot be read back.
    state=PipelineManifest.model_validate(state.model_dump(mode='json'))
    payload=deepcopy(row.structured_payload or {})
    payload.update(pipeline=PIPELINE_VERSION,universal=state.model_dump(mode='json'))
    payload.setdefault('concurso',{})
    payload.setdefault('cargos',[])
    payload.setdefault('multiple_cargos',False)
    row.structured_payload=payload;row.status=state.status;row.revision=(row.revision or 0)+1


async def owned_analysis(session,uid,identity,lock=False,source=False):
    query=select(EditalAnalysis).where(EditalAnalysis.user_id==uid,EditalAnalysis.id==uuid(identity))
    if not source:query=query.options(defer(EditalAnalysis.pages),defer(EditalAnalysis.extracted_text))
    if lock:query=query.with_for_update()
    row=await session.scalar(query)
    if row is None:raise HTTPException(404,'Análise não encontrada.')
    return row


async def admit(session,uid,now,exclude=None):
    # Account lock is acquired by callers before this short global admission
    # lock. Neither survives parsing or network IO.
    await session.execute(select(func.pg_advisory_xact_lock(INGEST_LOCK)))
    active=[EditalJob.status.in_(('queued','running'))]
    if exclude is not None:active.append(EditalJob.id!=exclude)
    if (await session.scalar(select(func.count()).select_from(EditalJob).where(EditalJob.user_id==uid,*active)))>=2:
        raise HTTPException(429,{'code':'analysis_concurrency','message':'Aguarde uma das suas duas análises em andamento.'})
    parsing=await session.scalar(select(func.count()).select_from(EditalJob).where(EditalJob.storage_provider==INGESTING,
        EditalJob.status=='running',EditalJob.lease_until>now,*([] if exclude is None else [EditalJob.id!=exclude])))
    if parsing>=1:raise HTTPException(429,{'code':'ingestion_busy','message':'A validação de arquivos está ocupada. Tente novamente em instantes.'})
    size=await source_bytes(session,uid)
    if size>=MAX_OWNED_BYTES:
        raise HTTPException(413,{'code':'source_storage_limit','message':'O limite de fontes salvas desta conta foi atingido. Gerencie seus documentos antes de enviar outro.'})


async def source_bytes(session,uid):
    return await session.scalar(select(func.coalesce(func.sum(func.pg_column_size(EditalAnalysis.pages)+
        func.coalesce(func.octet_length(EditalAnalysis.extracted_text),0)),0)).where(EditalAnalysis.user_id==uid))


async def reserve_intake(user_id,content_hash,filename,force,key):
    uid=uuid(user_id);key=request_key(key);now=utc_now();started={}
    async def apply(session,user):
        await session.execute(update(EditalJob).where(EditalJob.user_id==uid,EditalJob.storage_provider==INGESTING,
            EditalJob.status=='running',EditalJob.lease_until<now).values(status='failed',lease_token=None,lease_until=None,
                finished_at=now,phase='Validação interrompida antes de salvar o texto. Reenvie o PDF para retomar.'))
        if not force:
            previous=await session.scalar(select(EditalAnalysis.id).where(EditalAnalysis.user_id==uid,
                EditalAnalysis.content_hash==content_hash,EditalAnalysis.analysis_version=='6',
                EditalAnalysis.structured_payload['pipeline'].astext==PIPELINE_VERSION)
                .order_by(EditalAnalysis.created_at.desc()).limit(1))
            if previous:
                job=await session.scalar(select(EditalJob).where(EditalJob.user_id==uid,EditalJob.analysis_id==previous,
                    EditalJob.storage_provider==MARKER).order_by(EditalJob.created_at.desc()).limit(1))
                if job:return {'job_id':str(job.id),'phase':'accepted','intake_attempts':0}
        previous=await session.scalar(select(EditalJob).where(EditalJob.user_id==uid,EditalJob.content_hash==content_hash,
            EditalJob.force==force,EditalJob.storage_provider.in_((INGESTING,MARKER)),EditalJob.status.in_(('queued','running')))
            .order_by(EditalJob.created_at.desc()).limit(1))
        if previous:return {'job_id':str(previous.id),'phase':'existing','intake_attempts':0}
        await admit(session,uid,now)
        token=uuid4();job=EditalJob(id=uuid4(),user_id=uid,filename=filename,storage_provider=INGESTING,storage_key=None,
            content_hash=content_hash,force=force,status='running',phase='Validando PDF e preservando a origem do texto',
            lease_token=token,lease_until=now+timedelta(seconds=90))
        session.add(job);await session.flush();started.update(token=token)
        return {'job_id':str(job.id),'phase':'validating','intake_attempts':1}
    result=await run_activity(uid,key,['edital_ingest',PIPELINE_VERSION,content_hash,force],apply)
    if started:return {**result,'action':'start','token':started['token']}
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        job=await session.scalar(select(EditalJob).where(EditalJob.user_id==uid,EditalJob.id==uuid(result['job_id'])).with_for_update())
        if user is None or job is None:raise HTTPException(404,'Envio não encontrado.')
        if job.analysis_id is not None and job.storage_provider==MARKER:
            return {'action':'accepted','job_id':str(job.id),'analysis_id':str(job.analysis_id),'replayed':True}
        if job.status=='running' and job.lease_until and job.lease_until>now:
            return {'action':'in_progress','job_id':str(job.id)}
        receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==uid,ActivityReceipt.request_key==key))
        attempts=receipt.result.get('intake_attempts',0)
        if attempts>=3:raise HTTPException(422,{'code':'ingestion_retry_limit','message':'Confira o arquivo antes de iniciar outro envio; a validação já foi retomada três vezes.'})
        await admit(session,uid,now,exclude=job.id)
        token=uuid4();job.status='running';job.storage_provider=INGESTING;job.lease_token=token
        job.lease_until=now+timedelta(seconds=90);job.finished_at=None;job.phase='Retomando validação do arquivo'
        receipt.result={'job_id':str(job.id),'phase':'validating','intake_attempts':attempts+1}
        return {'action':'start','job_id':str(job.id),'token':token,'replayed':True}


def input_context(batch,all_blocks,previous):
    by_id={block['id']:block for block in all_blocks};primary={block['id'] for block in batch}
    candidates=[b['id'] for b in previous[-2:]]
    point=batch[0].get('parent_heading_hint');seen=set()
    while point and point in by_id and point not in seen and len(seen)<8:
        seen.add(point);candidates.append(point);point=by_id[point].get('parent_heading_hint')
    selected=[];size=0
    for identity in dict.fromkeys(candidates):
        if identity in primary:continue
        cost=len(by_id[identity]['text'])
        if size+cost<=3000:selected.append(identity);size+=cost
    return selected


async def persist_input(user_id,job_id,token,document):
    uid=uuid(user_id);now=utc_now()
    all_blocks=[block_dict(b) for b in blocks_from_pages(document.pages)]
    chunks=list(inventory_batches(all_blocks))
    async with unit_of_work() as session:
        user=await IdentityRepository(session).by_id(uid,lock=True)
        job=await session.scalar(select(EditalJob).where(EditalJob.user_id==uid,EditalJob.id==uuid(job_id)).with_for_update())
        if user is None or job is None:raise HTTPException(404,'Envio não encontrado.')
        if job.status!='running' or job.storage_provider!=INGESTING or job.lease_token!=token or job.lease_until<=now:
            raise HTTPException(409,{'code':'ingestion_lease_lost','message':'Outro envio retomou a validação. Atualize suas análises.'})
        if document.sha256!=job.content_hash:raise HTTPException(409,'O arquivo extraído diverge do envio.')
        source=DocumentSummary(hash=document.sha256,pages=len(document.pages),characters=sum(p.characters for p in document.pages),
            blocks=len(all_blocks),size_bytes=document.size_bytes,ocr_required_pages=[p.page for p in document.pages if p.quality=='requires_ocr'],
            low_text_pages=[p.page for p in document.pages if p.quality=='low_text'],
            image_pages=[p.page for p in document.pages if p.image_count],warnings=document.warnings)
        state=PipelineManifest(source=source,inventory=InventoryState(generation=uuid4()),status='waiting_provider',phase='inventory',error_kind='provider_approval_required')
        if source.ocr_required_pages:state.status='ocr_required';state.phase='layout';state.error_kind='requires_selective_ocr_unavailable'
        elif not all_blocks:state.status='recoverable_failure';state.phase='layout';state.error_kind='empty_text_document'
        elif len(chunks)>MAX_PROVIDER_ATTEMPTS or len(chunks)>state.budget.leaf_unit_limit:
            state.status='recoverable_failure';state.error_kind='document_operational_unit_limit'
        elif len(chunks)*2>state.budget.provider_limit:
            state.status='quota_paused';state.error_kind='initial_document_budget_exceeded'
        row=EditalAnalysis(id=uuid4(),user_id=uid,content_hash=document.sha256,status=state.status,analysis_version='6',
            structured_payload={},filename=job.filename,pages=[p.model_dump(mode='json') for p in document.pages],
            extracted_text='\n\n'.join(f'[Página {page.page}]\n'+'\n'.join(b.text for b in page.blocks) for page in document.pages))
        write_manifest(row,state);session.add(row);await session.flush()
        if await source_bytes(session,uid)>MAX_OWNED_BYTES:
            raise HTTPException(413,{'code':'source_storage_limit','message':'O texto excederia o limite de fontes desta conta; nenhum resultado anterior foi removido.'})
        job.analysis_id=row.id;job.storage_provider=MARKER;job.lease_token=None;job.lease_until=None
        job.status='queued' if state.status in ('processing','waiting_provider') else 'completed'
        job.phase='Aguardando homologação e autorização da IA' if state.status=='waiting_provider' else 'Identificando cargos e estrutura' if state.status=='processing' else 'Texto requer processamento adicional; confira as páginas indicadas'
        if job.status=='completed':job.finished_at=now
        if state.status in ('processing','quota_paused','waiting_provider'):
            previous=[]
            for chunk in chunks:
                ids=[b['id'] for b in chunk];context=input_context(chunk,all_blocks,previous)
                session.add(EditalUnit(user_id=uid,analysis_id=row.id,job_id=job.id,generation=state.inventory.generation,
                    scope_key='inventory',kind='inventory',unit_key=unit_key('inventory','inventory',ids,context),
                    source_blocks=ids,context_blocks=context))
                previous=chunk
        return {'action':'accepted','analysis_id':str(row.id),'job_id':str(job.id),'status':state.status}


async def fail_intake(user_id,job_id,token,code):
    uid=uuid(user_id)
    async with unit_of_work() as session:
        await IdentityRepository(session).by_id(uid,lock=True)
        await session.execute(update(EditalJob).where(EditalJob.user_id==uid,EditalJob.id==uuid(job_id),
            EditalJob.storage_provider==INGESTING,EditalJob.status=='running',EditalJob.lease_token==token)
            .values(status='failed',lease_token=None,lease_until=None,finished_at=utc_now(),
                phase=f'Validação não concluída ({code}). O arquivo original não foi salvo; reenvie para retomar.'))
