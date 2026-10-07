"""Run the shared pipeline with synthetic PDF extraction and mocked providers."""
import ast, asyncio, io, json, logging, sys, unittest, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import List
from unittest.mock import AsyncMock
from fastapi import HTTPException, UploadFile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edital_quality import needs_disciplines, mark_discipline_quality, edital_context

SOURCE = Path(__file__).resolve().parents[1] / 'server.py'
def pipeline():
    names = {'process_edital_analysis', '_detect_min_cargos', '_fill_cp_from_topicos', '_sanitize_cargos', 'dedup_cargos_fuzzy', '_normalize_cargo_name', '_normalize_disciplinas'}
    nodes = [n for n in ast.parse(SOURCE.read_text(encoding='utf8')).body if getattr(n, 'name', '') in names]
    ns = dict(globals(), _CARGO_TEXT_FIELDS=('vagas','remuneracao','escolaridade'))
    ns.update(get_user_api_key=AsyncMock(return_value='synthetic-key'), sql_edital=SimpleNamespace(cached=AsyncMock(return_value=None),save=AsyncMock()),
        extract_pdf_text=lambda _: 'Document text', call_gemini=AsyncMock(return_value=(json.dumps({'concurso':{'nome':'Contest'}, 'cargos':[{'nome':'Analyst', 'disciplinas':[{'nome':'Mathematics','topicos':['Algebra']}]}]}), None)),
        agent_runtime=SimpleNamespace(router=None,credentials=SimpleNamespace(get=AsyncMock(return_value={})),settings=SimpleNamespace(rag=False),automations=SimpleNamespace(emit=AsyncMock())),
        _hydrate_missing_disciplinas=AsyncMock(), _enumerate_cargos_text=AsyncMock(), _try_repair_json=lambda _: None)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns

def upload(content=b'%PDF-synthetic', name='notice.pdf'):
    return UploadFile(io.BytesIO(content), filename=name)

class DirectTests(unittest.IsolatedAsyncioTestCase):
    async def test_lost_response_retry_reuses_hash_cache_and_force_bypasses(self):
        ns=pipeline(); user=SimpleNamespace(user_id=str(uuid.uuid4()))
        result=await ns['process_edital_analysis'](user,upload())
        saved=ns['sql_edital'].save.call_args.args[1]
        self.assertEqual(result['cargos'][0]['nome'],'Analyst')
        self.assertEqual(saved['user_id'],user.user_id)
        self.assertNotIn(b'%PDF',repr(saved).encode())
        ns['sql_edital'].cached.return_value=saved
        retry=await ns['process_edital_analysis'](user,upload())
        self.assertTrue(retry['cached']); self.assertNotEqual(result['analysis_id'],retry['analysis_id'])
        self.assertEqual(ns['call_gemini'].await_count,1)
        ns['sql_edital'].cached.assert_awaited_with(user.user_id,saved['pdf_hash'],5)
        forced=await ns['process_edital_analysis'](user,upload(),True)
        self.assertFalse(forced['cached']); self.assertEqual(ns['call_gemini'].await_count,2)

    async def test_validation_and_missing_key_precede_ai(self):
        for content,name in [(b'bad','notice.pdf'),(b'%PDF-x','bad.txt'),(b'%PDF-'+b'x'*(20*1024*1024),'notice.pdf')]:
            ns=pipeline()
            with self.assertRaises(HTTPException): await ns['process_edital_analysis'](SimpleNamespace(user_id='u'),upload(content,name))
            ns['call_gemini'].assert_not_awaited()
        ns=pipeline(); ns['get_user_api_key'].return_value=None
        with self.assertRaises(HTTPException) as error: await ns['process_edital_analysis'](SimpleNamespace(user_id='u'),upload())
        self.assertIn('Gemini',error.exception.detail); ns['call_gemini'].assert_not_awaited()

    async def test_provider_errors_are_specific_without_secrets(self):
        for kind,word in [('invalid','inv'),('quota','cota')]:
            ns=pipeline(); ns['call_gemini'].return_value=(None,kind)
            with self.assertRaises(HTTPException) as error: await ns['process_edital_analysis'](SimpleNamespace(user_id='u'),upload())
            self.assertIn(word,error.exception.detail); self.assertNotIn('synthetic-key',error.exception.detail)
        ns=pipeline(); ns['call_gemini'].side_effect=RuntimeError('synthetic-key PRIVATE SOURCE')
        with self.assertRaises(HTTPException) as error: await ns['process_edital_analysis'](SimpleNamespace(user_id='u'),upload())
        self.assertNotIn('PRIVATE',error.exception.detail); self.assertNotIn('RuntimeError',error.exception.detail)

    async def test_unreadable_pdf_and_incomplete_json_are_explicit(self):
        ns=pipeline(); ns['extract_pdf_text']=lambda _: ''
        with self.assertRaises(HTTPException) as error: await ns['process_edital_analysis'](SimpleNamespace(user_id='u'),upload())
        self.assertEqual(error.exception.status_code,422); ns['call_gemini'].assert_not_awaited()
        ns=pipeline(); ns['call_gemini'].return_value=('not json',None)
        with self.assertRaises(HTTPException) as error: await ns['process_edital_analysis'](SimpleNamespace(user_id='u'),upload())
        self.assertIn('incompleto',error.exception.detail); ns['sql_edital'].save.assert_not_awaited()

    def test_direct_and_worker_use_same_pipeline(self):
        tree=ast.parse(SOURCE.read_text(encoding='utf8'))
        for name in ['analyze_edital_cargos','process_queued_edital']:
            node=next(n for n in ast.walk(tree) if getattr(n,'name','')==name)
            self.assertTrue(any(isinstance(n,ast.Name) and n.id=='process_edital_analysis' for n in ast.walk(node)))
