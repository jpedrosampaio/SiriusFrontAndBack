"""Heterogeneous extraction, operational boundaries and cancelled admission."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
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
