import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, HTTPException
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edital_jobs import EditalJobs


class EditalJobTests(unittest.IsolatedAsyncioTestCase):
    def service(self, process):
        db = SimpleNamespace(edital_jobs=SimpleNamespace(update_one=AsyncMock(), insert_one=AsyncMock(), count_documents=AsyncMock(return_value=0)))
        files = SimpleNamespace(upload_from_stream=AsyncMock(return_value='file'), delete=AsyncMock(), open_download_stream=AsyncMock(return_value=SimpleNamespace(read=AsyncMock(return_value=b'%PDF-test'))))
        async def mutate(user, key, fingerprint, apply): return await apply(None, {})
        with patch('edital_jobs.AsyncIOMotorGridFSBucket', return_value=files):
            service = EditalJobs(db, AsyncMock(return_value=SimpleNamespace(user_id='alice')), process, mutate)
        return service, db, files

    async def test_worker_records_analysis_and_deletes_input(self):
        process = AsyncMock(return_value={'analysis_id': 'analysis'})
        service, db, files = self.service(process)
        await service.run({'_id': 'job', 'file_id': 'file', 'filename': 'notice.pdf', 'user_id': 'alice', 'force': False})
        process.assert_awaited_once()
        self.assertEqual(process.call_args.args[0], 'alice')
        updates = [call.args[1].get('$set', {}) for call in db.edital_jobs.update_one.call_args_list]
        self.assertTrue(any(update.get('status') == 'completed' and update.get('analysis_id') == 'analysis' for update in updates))
        files.delete.assert_awaited_once_with('file')

    async def test_worker_failure_is_visible_and_never_silently_retries_ai(self):
        process = AsyncMock(side_effect=HTTPException(400, 'Configure sua chave Gemini.'))
        service, db, files = self.service(process)
        await service.run({'_id': 'job', 'file_id': 'file', 'filename': 'notice.pdf', 'user_id': 'alice', 'force': False})
        self.assertEqual(process.await_count, 1)
        self.assertTrue(any(call.args[1].get('$set', {}).get('status') == 'failed' for call in db.edital_jobs.update_one.call_args_list))
        files.delete.assert_awaited_once()

    async def test_upload_bounds_and_per_user_queue_limit(self):
        service, db, files = self.service(AsyncMock())
        app = FastAPI(); app.include_router(service.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            invalid = await client.post('/study/edital-jobs', files={'file': ('wrong.pdf', b'not-pdf', 'application/pdf')})
            self.assertEqual(invalid.status_code, 422)
            files.upload_from_stream.assert_not_awaited()
            db.edital_jobs.count_documents.return_value = 2
            limited = await client.post('/study/edital-jobs', files={'file': ('notice.pdf', b'%PDF-test', 'application/pdf')})
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(db.edital_jobs.count_documents.call_args.args[0]['user_id'], 'alice')
            files.delete.assert_awaited_once()
            db.edital_jobs.insert_one.assert_not_awaited()


if __name__ == '__main__': unittest.main()
