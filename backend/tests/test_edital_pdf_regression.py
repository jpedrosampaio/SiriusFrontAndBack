"""Heterogeneous extraction, operational boundaries and cancelled admission."""
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import edital_pdf_fixtures as fixtures
from services import edital_pdf as extraction
from edital_pipeline_contracts import DocumentIR,SourcePage


class PDFExtraction(unittest.TestCase):
    def test_cgroup_measurements_are_numeric_optional_and_do_not_claim_request_oom(self):
        result=SimpleNamespace(returncode=-9,stdout=b'')
        with patch.object(extraction,'_cgroup_memory',side_effect=[
            (200000000,300000000,512000000,4),(190000000,510000000,512000000,5)]),\
            patch.object(extraction.subprocess,'run',return_value=result),\
            self.assertLogs(extraction.logger,level='WARNING') as logged,\
            self.assertRaises(extraction.PDFInputError) as failure:
            extraction.supervised(b'%PDF-synthetic')
        metrics=failure.exception.metrics
        self.assertEqual(metrics.cgroup_memory_before_bytes,200000000)
        self.assertEqual(metrics.cgroup_memory_after_bytes,190000000)
        self.assertEqual(metrics.cgroup_memory_peak_bytes,510000000)
        self.assertEqual(metrics.cgroup_memory_max_bytes,512000000)
        self.assertEqual(metrics.cgroup_oom_kill_delta,1)
        self.assertIn('cgroup_oom_kill_delta=1',' '.join(logged.output))
        self.assertEqual(failure.exception.code,'extraction_process_failed')

    def test_cgroup_reader_handles_namespace_paths_and_unavailable_counters(self):
        root=Path('/sys/fs/cgroup')
        for namespace in ('/','/service'):
            files={Path('/proc/self/cgroup'):'0::'+namespace+'\n',
                root/namespace.lstrip('/')/'memory.current':'12345\n',
                root/namespace.lstrip('/')/'memory.peak':'67890\n',
                root/namespace.lstrip('/')/'memory.max':'max\n',
                root/namespace.lstrip('/')/'memory.events':'oom 3\noom_kill 2\n'}
            def opened(path,*args,**kwargs):
                if path not in files:raise FileNotFoundError
                return io.StringIO(files[path])
            with self.subTest(namespace=namespace),patch.object(extraction.sys,'platform','linux'),\
                patch.object(Path,'open',autospec=True,side_effect=opened):
                self.assertEqual(extraction._cgroup_memory(),(12345,67890,None,2))
        with patch.object(extraction.sys,'platform','linux'),patch.object(Path,'open',side_effect=PermissionError):
            self.assertEqual(extraction._cgroup_memory(),(None,None,None,None))

    def test_abnormal_exit_and_excess_output_are_distinct_without_logging_content(self):
        private=b'PRIVATE-PDF-OR-CREDENTIAL'
        for returncode,size,expected,outcome in [
            (-9,len(private),'extraction_process_failed','process_failed'),
            (1,256,'extraction_process_failed','process_failed'),
            (0,256,'extraction_result_limit','result_limit')]:
            output=(private+b'x'*size)[:size]
            with self.subTest(returncode=returncode,size=size),patch.object(extraction,'MAX_RESULT',128),\
                patch.object(extraction.subprocess,'run',return_value=SimpleNamespace(returncode=returncode,stdout=output)),\
                self.assertLogs(extraction.logger,level='WARNING') as logged,\
                self.assertRaises(extraction.PDFInputError) as failure:
                extraction.supervised(b'%PDF-PRIVATE-INPUT')
            error=failure.exception;metrics=error.metrics;message=' '.join(logged.output)
            self.assertEqual(error.code,expected)
            self.assertEqual(metrics.returncode,returncode)
            self.assertEqual(metrics.stdout_bytes,size);self.assertTrue(metrics.stdout_complete)
            self.assertEqual(metrics.signal,9 if returncode==-9 and os.name=='posix' else None)
            self.assertGreaterEqual(metrics.duration_ms,0)
            self.assertRegex(metrics.reference,r'^[0-9a-f]{12}$')
            for field in (f'outcome={outcome}',f'reference={metrics.reference}',f'returncode={returncode}',
                f'stdout_bytes={size}',f'stdout_limit_exceeded={size>128}','duration_ms=','signal='):
                self.assertIn(field,message)
            self.assertNotIn('PRIVATE',message);self.assertNotIn('OOM',message)

    def test_timeout_logs_partial_byte_count_without_guessing_exit_signal(self):
        timeout=subprocess.TimeoutExpired(['PRIVATE-COMMAND'],60,output=b'PRIVATE-PARTIAL',stderr=b'PRIVATE-STDERR')
        with patch.object(extraction.subprocess,'run',side_effect=timeout),\
            self.assertLogs(extraction.logger,level='WARNING') as logged,\
            self.assertRaises(extraction.PDFInputError) as failure:
            extraction.supervised(b'%PDF-private')
        metrics=failure.exception.metrics
        self.assertEqual(failure.exception.code,'extraction_timeout')
        self.assertEqual(metrics.stdout_bytes,len(b'PRIVATE-PARTIAL'))
        self.assertFalse(metrics.stdout_complete)
        self.assertIsNone(metrics.returncode);self.assertIsNone(metrics.signal)
        self.assertIn('outcome=timeout',' '.join(logged.output))
        self.assertNotIn('PRIVATE',' '.join(logged.output))

    def test_launch_failure_and_invalid_protocol_are_safe_diagnostics(self):
        for result,expected,outcome in [
            (OSError('PRIVATE-PATH'),'extraction_process_failed','launch_failed'),
            (SimpleNamespace(returncode=0,stdout=b'PRIVATE-TEXT'),'extraction_failed','invalid_result'),
            (SimpleNamespace(returncode=0,stdout=b'[]'),'extraction_failed','invalid_result'),
            (SimpleNamespace(returncode=0,stdout=b'{"ok":true,"document":{"private":"PRIVATE"}}'),'extraction_failed','invalid_result'),
            (SimpleNamespace(returncode=0,stdout=b'{"ok":false,"code":"PRIVATE","diagnostic":"PRIVATE"}'),'PRIVATE','child_rejected')]:
            kwargs={'side_effect':result} if isinstance(result,Exception) else {'return_value':result}
            with self.subTest(outcome=outcome),patch.object(extraction.subprocess,'run',**kwargs),\
                self.assertLogs(extraction.logger,level='WARNING') as logged,\
                self.assertRaises(extraction.PDFInputError) as failure:
                extraction.supervised(b'%PDF-private')
            self.assertEqual(failure.exception.code,expected)
            self.assertIn(f'outcome={outcome}',' '.join(logged.output))
            self.assertNotIn('PRIVATE',' '.join(logged.output))

    @unittest.skipUnless(sys.platform.startswith('linux'),'Linux process limits/signals')
    def test_real_linux_signal_is_reported_without_claiming_oom(self):
        actual_run=subprocess.run
        def killed_child(command,**kwargs):
            return actual_run([sys.executable,'-c','import os,signal; os.kill(os.getpid(),signal.SIGKILL)'],**kwargs)
        with patch.object(extraction.subprocess,'run',side_effect=killed_child),\
            self.assertLogs(extraction.logger,level='WARNING') as logged,\
            self.assertRaises(extraction.PDFInputError) as failure:
            extraction.supervised(b'%PDF-synthetic')
        self.assertEqual(failure.exception.code,'extraction_process_failed')
        self.assertEqual(failure.exception.metrics.returncode,-9)
        self.assertEqual(failure.exception.metrics.signal,9)
        self.assertEqual(failure.exception.metrics.stdout_bytes,0)
        self.assertNotIn('OOM',' '.join(logged.output))

    @unittest.skipUnless(sys.platform.startswith('linux'),'Linux address-space enforcement')
    def test_linux_address_space_limit_still_rejects_over_budget_allocation(self):
        script="""import json,resource
from services.edital_pdf import child_limits
child_limits()
limits=[resource.getrlimit(kind) for kind in (resource.RLIMIT_AS,resource.RLIMIT_CPU,resource.RLIMIT_FSIZE)]
try:
    bytearray(384*1024*1024)
except MemoryError:
    print(json.dumps(limits))
else:
    raise SystemExit('address-space protection missing')
"""
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=10,
            cwd=Path(extraction.__file__).resolve().parents[1],env={'PATH':os.environ.get('PATH',''),'PYTHONDONTWRITEBYTECODE':'1'},check=False)
        self.assertEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout),[[384*1024*1024]*2,[55]*2,[0]*2])

    @unittest.skipUnless(sys.platform.startswith('linux'),'Long-document regression under production Linux limits')
    def test_extensive_linux_document_preserves_all_pages_text_tables_and_references(self):
        content=fixtures.extensive()
        with self.assertLogs(extraction.logger,level='INFO') as logged:
            document=extraction.supervised(content)
        self.assertEqual(document.sha256,hashlib.sha256(content).hexdigest())
        self.assertEqual(len(document.pages),70)
        self.assertGreater(sum(p.characters for p in document.pages),200000)
        for number,page in enumerate(document.pages,1):
            self.assertEqual(page.page,number);self.assertEqual(page.quality,'text')
            text=' '.join(block.text for block in page.blocks)
            for line in range(1,41):
                self.assertIn(f'Pagina {number:03d} linha {line:03d}: Conteudo verificavel de extracao integral e referencias.',text)
            rows=[block for block in page.blocks if block.kind=='table_row']
            self.assertEqual([row.cells for row in rows],[
                ['Perfil profissional','Vagas previstas'],[f'Analista {number:03d}','Cadastro de reserva'],
                [f'Especialista {number:03d}','12 vagas']])
            self.assertTrue(all(row.table_id==f'p{number:04d}-table001' for row in rows))
            self.assertTrue(all(block.id.startswith(f'p{number:04d}-b') and block.page==number and block.paragraph_hint
                for block in page.blocks))
        message=' '.join(logged.output)
        self.assertIn('outcome=completed',message);self.assertIn('returncode=0',message)
        self.assertIn('address_space_limit_bytes=402653184',message)
        self.assertNotIn('Conteudo verificavel',message)

    def test_synthetic_digital_roles_text_and_geometry(self):
        content=fixtures.pdf([[fixtures.text(50,740,'Seleção pública - Quadro funcional',16),
            fixtures.text(50,700,'Perfil A: Analista. Vagas: CR. Salário: R$ 4.500,00.'),
            fixtures.text(50,680,'Exige graduação na área de formação informada.')]])
        document=extraction.supervised(content)
        self.assertEqual(document.sha256,hashlib.sha256(content).hexdigest())
        self.assertEqual(document.pages[0].quality,'text')
        self.assertTrue(all(b.bbox[0]>=0 and b.page==1 for b in document.pages[0].blocks))
        self.assertIn('R$ 4.500,00',' '.join(b.text for b in document.pages[0].blocks))

    def test_columns_do_not_merge_parallel_lines(self):
        document=extraction.supervised(fixtures.columns());page=document.pages[0]
        self.assertEqual(page.column_hint,2)
        left=[i for i,b in enumerate(page.blocks) if b.text.startswith('Esquerda')]
        right=[i for i,b in enumerate(page.blocks) if b.text.startswith('Direita')]
        self.assertEqual((len(left),len(right)),(12,12));self.assertLess(max(left),min(right))
        self.assertTrue(all(not ('Esquerda' in b.text and 'Direita' in b.text) for b in page.blocks))

    def test_table_relationships_and_cells_are_preserved(self):
        document=extraction.supervised(fixtures.table())
        rows=[b for b in document.pages[0].blocks if b.kind=='table_row']
        self.assertEqual(len(rows),3);self.assertEqual(len({r.table_id for r in rows}),1)
        self.assertEqual(rows[1].cells,['Analista de Sistemas','Cadastro de reserva'])
        self.assertEqual(rows[2].cells,['Especialista financeiro','12 vagas'])
        self.assertEqual(rows[1].table_header_hint,['Perfil profissional','Vagas previstas'])

    def test_scanned_mixed_blank_and_low_text_are_distinct_valid_inputs(self):
        content=fixtures.pdf([[fixtures.text(50,740,'Texto digital completo com informações para revisão documental.')],None,[],[fixtures.text(50,740,'Anexo')]])
        document=extraction.supervised(content)
        self.assertEqual([p.quality for p in document.pages],['text','requires_ocr','blank','low_text'])
        self.assertFalse(document.ocr_available);self.assertIn('requires_selective_ocr_unavailable',document.warnings)

    def test_digital_header_does_not_hide_a_scanned_program_on_the_same_page(self):
        header=fixtures.text(30,770,'Digital administrative header with more than fifty selectable characters for this page.')
        document=extraction.supervised(fixtures.pdf([{'text':[header]}]))
        self.assertGreater(document.pages[0].characters,50)
        self.assertEqual(document.pages[0].quality,'requires_ocr');self.assertEqual(document.pages[0].image_count,1)

    def test_recurring_margins_are_hints_and_never_drop_document_text(self):
        content=fixtures.pdf([[fixtures.text(50,775,'INSTITUIÇÃO - SELEÇÃO PÚBLICA'),
            fixtures.text(50,720,f'Artigo {n+1}. Conteúdo próprio desta página e suas regras.'),
            fixtures.text(50,25,'DOCUMENTO OFICIAL')] for n in range(3)])
        document=extraction.supervised(content)
        self.assertTrue(all(any(b.recurring_margin for b in p.blocks) for p in document.pages))
        self.assertEqual(sum('DOCUMENTO OFICIAL' in b.text for p in document.pages for b in p.blocks),3)
        self.assertTrue(all(any(b.paragraph_hint for b in p.blocks) for p in document.pages))

    def test_encrypted_corrupt_and_page_limit_fail_before_provider_access(self):
        for content,code in [(fixtures.pdf([[]],password='test-only'),'encrypted_pdf'),
            (b'%PDF-1.7\ninvalid','unreadable_pdf'),(fixtures.pdf([[]]*401),'page_limit')]:
            with self.subTest(code=code),self.assertRaises(extraction.PDFInputError) as error:
                extraction.supervised(content)
            self.assertEqual(error.exception.code,code)

    def test_old_unsafe_cmap_loader_fails_closed(self):
        with patch.object(extraction,'version',return_value='20250327'),self.assertRaises(extraction.PDFInputError) as error:
            extraction.extract_local(b'%PDF-1.7\ninvalid')
        self.assertEqual(error.exception.code,'parser_security_upgrade_required')

    def test_child_receives_no_database_keys_or_external_cmap_path(self):
        document=DocumentIR(sha256='a'*64,size_bytes=10,pages=[SourcePage(page=1,width=600,height=800,quality='blank',characters=0)])
        result=SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'document':document.model_dump(mode='json')}).encode())
        with patch.dict(os.environ,{'DATABASE_URL':'test-only-never-print','AI_SECRET':'test-only-never-print','CMAP_PATH':'untrusted'}),patch.object(extraction.subprocess,'run',return_value=result) as run:
            extraction.supervised(b'%PDF-1.7')
        env=run.call_args.kwargs['env']
        self.assertTrue(all(key not in env for key in ('DATABASE_URL','DATABASE_URL_DIRECT','AI_SECRET','CMAP_PATH')))
        self.assertEqual(run.call_args.kwargs['timeout'],60)
        self.assertEqual(run.call_args.kwargs['stderr'],extraction.subprocess.DEVNULL)


class CancelledIngestion(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_does_not_release_capacity_while_child_is_running(self):
        entered=threading.Event();release=threading.Event();calls=[]
        document=DocumentIR(sha256='a'*64,size_bytes=10,pages=[SourcePage(page=1,width=600,height=800,quality='blank',characters=0)])
        def parser(content):
            calls.append(content)
            if len(calls)==1:
                entered.set();release.wait(2)
                raise extraction.PDFInputError('unreadable_pdf')
            return document
        with patch.object(extraction,'_slots',asyncio.Semaphore(1)),patch.object(extraction,'supervised',side_effect=parser):
            first=asyncio.create_task(extraction.extract_pdf(b'first'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait,1))
                first.cancel()
                with self.assertRaises(asyncio.CancelledError):await first
                second=asyncio.create_task(extraction.extract_pdf(b'second'))
                await asyncio.sleep(.05)
                self.assertEqual(calls,[b'first'])
                release.set();self.assertEqual((await second).sha256,'a'*64)
                self.assertEqual(calls,[b'first',b'second'])
            finally:release.set()
