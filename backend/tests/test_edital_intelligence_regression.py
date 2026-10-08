import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edital_intelligence import impact, official_dates
from contest_sources import validate_url, SourceUnavailable, GenericOfficialConnector


class EdictIntelligenceTests(unittest.TestCase):
    def test_literal_dates_require_official_complete_valid_unambiguous_event(self):
        text = 'Inscrições de 01/02/2027 a 28/02/2027\nProva objetiva: 31/02/2027\nResultado: 03/04\nPagamento e inscrição: 03/04/2027'
        self.assertEqual(official_dates(text, official=False), [])
        rows = official_dates(text, official=True)
        self.assertEqual([r['date'] for r in rows], ['2027-02-01', '2027-02-28'])
        self.assertTrue(all(r['requires_confirmation'] and r['provenance'] == 'extracted' for r in rows))
        self.assertEqual(official_dates('Resultado: 3 de março de 2027',official=True)[0]['date'],'2027-03-03')
        self.assertEqual(official_dates('Texto\n'*3500+'Resultado: 03/03/2027',official=True)[0]['date'],'2027-03-03')

    def test_diff_is_explicitly_inferred_without_plan_mutation_or_fake_minutes(self):
        result = impact('Peso 1\nDisciplina A', 'Peso 2\nDisciplina B')
        self.assertEqual(result['added'], ['Peso 2', 'Disciplina B'])
        self.assertEqual(result['categories'], ['syllabus', 'weights'])
        self.assertEqual(result['classification'], 'inferred')
        self.assertFalse(result['plan_changed'])
        self.assertIsNone(result['additional_minutes'])
        self.assertEqual(impact('', 'Peso 2', baseline=True)['added'], [])

    def test_limits_are_reported_and_protected_banks_rejected(self):
        self.assertTrue(impact('', '\n'.join(str(i) for i in range(1600)))['partial'])
        page = GenericOfficialConnector().normalize('x' * 200001, 'https://orgao.gov.br')
        self.assertEqual(len(page.text), 200000)
        self.assertTrue(page.partial)
        for host in ['qconcursos.com', 'www.qconcursos.com', 'tecconcursos.com.br', 'www.tecconcursos.com.br']:
            with self.assertRaises(SourceUnavailable): validate_url('https://' + host + '/questoes')
        self.assertEqual(validate_url('https://qconcursos.com.example.org/'), 'https://qconcursos.com.example.org/')

    def test_link_replacement_changes_version_hash_without_text_change(self):
        provider=GenericOfficialConnector()
        first=provider.normalize('<a href="/edital-v1.pdf">Edital</a>','https://orgao.gov.br')
        second=provider.normalize('<a href="/edital-v2.pdf">Edital</a>','https://orgao.gov.br')
        self.assertEqual(first.text,second.text)
        self.assertNotEqual(first.content_hash,second.content_hash)
        self.assertEqual(first.hash_basis,'page_text_and_links')

    def test_pdf_join_separator_truncation_has_consistent_partial_flags(self):
        pages=[SimpleNamespace(extract_text=lambda size=size:'a'*size) for size in (50000,50000,50000,49999)]
        reader=SimpleNamespace(is_encrypted=False,pages=pages)
        with patch('contest_sources.fetch_public',side_effect=[(404,{},b''),(200,{'content-type':'application/pdf'},b'%PDF-fixture')]), \
             patch('pypdf.PdfReader',return_value=reader):
            page=GenericOfficialConnector().poll('https://orgao.gov.br/edital.pdf')
        self.assertEqual(len(page.text),200000)
        self.assertTrue(page.partial)
        self.assertTrue(page.documents[0]['text_partial'])
