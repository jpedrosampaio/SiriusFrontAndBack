"""PostgreSQL queue with explicit object storage and leased, non-retried AI work."""
import asyncio
import io
import logging
from datetime import datetime,timedelta,timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter,Cookie,File,HTTPException,Query,Request,UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func,update
from db.models.files import EditalJob,EditalAnalysis
from db.models.identity import User
from db.session import unit_of_work
from storage.objects import configured_storage,UnconfiguredStorage,StorageUnavailable


class EditalJobs:
    def __init__(self,authenticate,process,storage=None):
        self.authenticate,self.process=authenticate,process
        self.storage=storage if storage is not None else configured_storage()
        self.task=None; self.wake=asyncio.Event()
        self.router=APIRouter(prefix='/study/edital-jobs')
        self.router.add_api_route('',self.submit,methods=['POST'],status_code=202)
        self.router.add_api_route('',self.list_jobs,methods=['GET'])

    async def submit(self,request: Request,file: UploadFile=File(...),force: bool=Query(False),session_token: Optional[str]=Cookie(None)):
        user=await self.authenticate(authorization=request.headers.get('Authorization'),session_token=session_token)
        if not (file.filename or '').lower().endswith('.pdf'): raise HTTPException(422,'Selecione um PDF.')
        content=await file.read(20*1024*1024+1)
        if len(content)>20*1024*1024 or not content.startswith(b'%PDF-'): raise HTTPException(422,'PDF inválido ou maior que 20 MB.')
        uid=UUID(user.user_id)
        try: stored=await self.storage.put(uid,content)
        except StorageUnavailable:
            raise HTTPException(503,'Envio em segundo plano indisponível: armazenamento durável de arquivos não configurado.')
        try:
            async with unit_of_work() as session:
                owner=await session.scalar(select(User).where(User.id==uid).with_for_update())
                if owner is None: raise HTTPException(401,'Usuário não encontrado.')
                active=await session.scalar(select(func.count()).select_from(EditalJob).where(EditalJob.user_id==uid,EditalJob.status.in_(['queued','running'])))
                if active>=2: raise HTTPException(429,'Aguarde suas análises em andamento antes de enviar outra.')
                job=EditalJob(user_id=uid,filename=file.filename,storage_provider=stored.provider,storage_key=stored.key,
                    content_hash=stored.sha256,force=force)
                session.add(job); await session.flush(); result={'job_id':str(job.id),'status':job.status}
        except BaseException:
            try: await self.storage.delete(uid,stored.key)
            except Exception: logging.warning('edital_input orphan cleanup required')
            raise
        self.wake.set()
        return result

    async def list_jobs(self,request: Request,session_token: Optional[str]=Cookie(None)):
        user=await self.authenticate(authorization=request.headers.get('Authorization'),session_token=session_token)
        async with unit_of_work() as session:
            rows=(await session.scalars(select(EditalJob).where(EditalJob.user_id==UUID(user.user_id)).order_by(EditalJob.created_at.desc()).limit(10))).all()
            return {'jobs':[jsonable_encoder({'job_id':r.id,'filename':r.filename,'status':r.status,'phase':r.phase,
                'created_at':r.created_at,'finished_at':r.finished_at,'analysis_id':r.analysis_id}) for r in rows],
                'upload_available':not isinstance(self.storage,UnconfiguredStorage)}

    async def start(self):
        if not isinstance(self.storage,UnconfiguredStorage) and self.task is None:
            self.task=asyncio.create_task(self.loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
            self.task=None

    async def claim(self):
        now=datetime.now(timezone.utc)
        async with unit_of_work() as session:
            await session.execute(update(EditalJob).where(EditalJob.status=='running',EditalJob.lease_until<now)
                .values(status='failed',phase='Análise interrompida. Confira os editais salvos antes de reenviar.',finished_at=now))
            job=await session.scalar(select(EditalJob).where(EditalJob.status=='queued').order_by(EditalJob.created_at)
                .with_for_update(skip_locked=True).limit(1))
            if job is None: return None
            job.status='running'; job.phase='Lendo PDF e analisando cargos e disciplinas'; job.lease_until=now+timedelta(seconds=180)
            return {'id':job.id,'user_id':job.user_id,'filename':job.filename,'storage_key':job.storage_key,'force':job.force}

    async def heartbeat(self,job_id):
        while True:
            await asyncio.sleep(60)
            async with unit_of_work() as session:
                await session.execute(update(EditalJob).where(EditalJob.id==job_id,EditalJob.status=='running')
                    .values(lease_until=datetime.now(timezone.utc)+timedelta(seconds=180)))

    async def finish(self,job,status,phase,analysis_id=None):
        async with unit_of_work() as session:
            if analysis_id:
                exists=await session.scalar(select(EditalAnalysis.id).where(EditalAnalysis.id==UUID(analysis_id),EditalAnalysis.user_id==job['user_id']))
                if exists is None: raise HTTPException(404,'Análise não encontrada.')
            await session.execute(update(EditalJob).where(EditalJob.id==job['id'],EditalJob.user_id==job['user_id'],EditalJob.status=='running')
                .values(status=status,phase=phase,analysis_id=UUID(analysis_id) if analysis_id else None,
                    finished_at=datetime.now(timezone.utc),lease_until=None))

    async def cleanup(self):
        async with unit_of_work() as session:
            rows=(await session.execute(select(EditalJob.id,EditalJob.user_id,EditalJob.storage_key).where(
                EditalJob.status.in_(['completed','failed']),EditalJob.storage_key.is_not(None)).limit(20))).all()
        for job_id,uid,key in rows:
            try: await self.storage.delete(uid,key)
            except Exception:
                logging.warning('edital_input cleanup pending'); continue
            async with unit_of_work() as session:
                await session.execute(update(EditalJob).where(EditalJob.id==job_id,EditalJob.storage_key==key).values(storage_key=None))

    async def run(self,job):
        heartbeat=asyncio.create_task(self.heartbeat(job['id']))
        try:
            content=await self.storage.read(job['user_id'],job['storage_key'])
            upload=UploadFile(filename=job['filename'],file=io.BytesIO(content))
            try: result=await asyncio.wait_for(self.process(str(job['user_id']),upload,job['force']),timeout=900)
            finally: await upload.close()
            await self.finish(job,'completed','Análise disponível para conferência',result['analysis_id'])
        except asyncio.CancelledError:
            await self.finish(job,'failed','Servidor reiniciado durante a análise. Confira os editais salvos antes de reenviar.')
            raise
        except Exception as error:
            message=str(error.detail) if isinstance(error,HTTPException) and error.status_code<500 else 'Não foi possível concluir a análise. Confira sua conexão com a IA e reenvie o PDF.'
            await self.finish(job,'failed',message)
            logging.warning('edital_job failed type=%s',type(error).__name__)
        finally:
            heartbeat.cancel()
            try: await heartbeat
            except asyncio.CancelledError: pass
            await self.cleanup()

    async def loop(self):
        while True:
            try:
                self.wake.clear()
                await self.cleanup()
                job=await self.claim()
                if job: await self.run(job)
                else:
                    try: await asyncio.wait_for(self.wake.wait(),timeout=60)
                    except asyncio.TimeoutError: pass
            except asyncio.CancelledError: raise
            except Exception as error:
                logging.error('edital_queue failure type=%s',type(error).__name__)
                await asyncio.sleep(60)
