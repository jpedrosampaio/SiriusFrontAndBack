"""Mongo-backed PDF queue. Inputs survive navigation/restarts; active jobs use leases.

An interrupted AI call is not silently retried (which could spend quota twice).
"""
import asyncio
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, File, HTTPException, Query, Request, UploadFile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pymongo import ReturnDocument


class EditalJobs:
    def __init__(self, db, authenticate, process, mutate):
        self.db, self.authenticate, self.process, self.mutate = db, authenticate, process, mutate
        self.files = AsyncIOMotorGridFSBucket(db, bucket_name='edital_inputs')
        self.task = None
        self.router = APIRouter(prefix='/study/edital-jobs')
        self.router.add_api_route('', self.submit, methods=['POST'], status_code=202)
        self.router.add_api_route('', self.list_jobs, methods=['GET'])

    async def submit(self, request: Request, file: UploadFile = File(...), force: bool = Query(False), session_token: Optional[str] = Cookie(None)):
        user = await self.authenticate(authorization=request.headers.get('Authorization'), session_token=session_token)
        if not (file.filename or '').lower().endswith('.pdf'):
            raise HTTPException(422, 'Selecione um PDF.')
        content = await file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024 or not content.startswith(b'%PDF-'):
            raise HTTPException(422, 'PDF inválido ou maior que 20 MB.')
        file_id = await self.files.upload_from_stream(file.filename, content)
        job_id = uuid.uuid4().hex
        async def apply(session, balance):
            active = await self.db.edital_jobs.count_documents({'user_id': user.user_id, 'status': {'$in': ['queued', 'running']}}, session=session)
            if active >= 2:
                raise HTTPException(429, 'Aguarde suas análises em andamento antes de enviar outra.')
            doc = {'_id': job_id, 'job_id': job_id, 'file_id': file_id, 'user_id': user.user_id,
                   'filename': file.filename, 'force': force, 'status': 'queued',
                   'created_at': datetime.now(timezone.utc), 'phase': 'Na fila'}
            await self.db.edital_jobs.insert_one(doc, session=session)
            return {'job_id': job_id, 'status': 'queued'}
        try:
            return await self.mutate(user.user_id, None, ['edital-job', job_id], apply)
        except Exception:
            await self.files.delete(file_id)
            raise

    async def list_jobs(self, request: Request, session_token: Optional[str] = Cookie(None)):
        user = await self.authenticate(authorization=request.headers.get('Authorization'), session_token=session_token)
        rows = await self.db.edital_jobs.find({'user_id': user.user_id}, {'_id': 0, 'file_id': 0, 'user_id': 0}).sort('created_at', -1).limit(10).to_list(10)
        return {'jobs': rows}

    async def start(self):
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def heartbeat(self, job_id):
        while True:
            await self.db.edital_jobs.update_one({'_id': job_id, 'status': 'running'}, {'$set': {'lease_until': datetime.now(timezone.utc) + timedelta(seconds=90)}})
            await asyncio.sleep(20)

    async def loop(self):
        while True:
            try:
                now = datetime.now(timezone.utc)
                await self.db.edital_jobs.update_many({'status': 'running', 'lease_until': {'$lt': now}}, {'$set': {'status': 'failed', 'phase': 'Análise interrompida. Confira os editais salvos antes de reenviar o PDF.'}})
                stale = await self.db.edital_jobs.find({'status': {'$in': ['failed', 'completed']}, 'file_id': {'$exists': True}}, {'file_id': 1}).limit(10).to_list(10)
                for item in stale:
                    try:
                        await self.files.delete(item['file_id'])
                    except Exception:
                        pass
                    await self.db.edital_jobs.update_one({'_id': item['_id']}, {'$unset': {'file_id': ''}})
                job = await self.db.edital_jobs.find_one_and_update({'status': 'queued'}, {'$set': {'status': 'running', 'phase': 'Lendo PDF e analisando cargos e disciplinas', 'lease_until': now + timedelta(seconds=90)}}, sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)
                if job:
                    await self.run(job)
                else:
                    await asyncio.sleep(3)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logging.error('edital_queue failure type=%s', type(error).__name__)
                await asyncio.sleep(10)

    async def run(self, job):
        heartbeat = asyncio.create_task(self.heartbeat(job['_id']))
        started = asyncio.get_running_loop().time()
        try:
            stream = await self.files.open_download_stream(job['file_id'])
            content = await stream.read()
            upload = UploadFile(filename=job['filename'], file=io.BytesIO(content))
            try:
                result = await asyncio.wait_for(self.process(job['user_id'], upload, job['force']), timeout=900)
            finally:
                await upload.close()
            await self.db.edital_jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'completed', 'phase': 'Análise disponível para conferência', 'analysis_id': result['analysis_id'], 'finished_at': datetime.now(timezone.utc)}})
        except asyncio.CancelledError:
            await self.db.edital_jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'failed', 'phase': 'Servidor reiniciado durante a análise. Confira os editais salvos antes de reenviar.'}})
            raise
        except Exception as error:
            message = str(error.detail) if isinstance(error, HTTPException) and error.status_code < 500 else 'Não foi possível concluir a análise. Confira sua conexão com a IA e reenvie o PDF.'
            await self.db.edital_jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'failed', 'phase': message, 'finished_at': datetime.now(timezone.utc)}})
            logging.warning('edital_job failed type=%s', type(error).__name__)
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
            logging.info('edital_job duration_ms=%s', round((asyncio.get_running_loop().time() - started) * 1000))
            try:
                await self.files.delete(job['file_id'])
                await self.db.edital_jobs.update_one({'_id': job['_id']}, {'$unset': {'file_id': ''}})
            except Exception:
                logging.warning('edital_input cleanup pending')
