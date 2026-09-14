"""Regressions for late TJCE-like annexes, group placeholders and cargo isolation."""
import ast
import json
import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from fastapi import APIRouter, Cookie, HTTPException, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from edital_quality import edital_context, generic_discipline, mark_discipline_quality, needs_disciplines, normalized_name

SOURCE = ROOT / 'server.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))


def load_routes():
    names = {'_normalize_disciplinas', '_merge_hydrated_disciplinas', '_hydrate_missing_disciplinas',
             '_build_hydration_prompt', '_parse_json_lenient', '_strip_json_fences',
             '_hydrate_disciplinas_from_text', 'import_edital_with_cargo'}
    nodes = [n for n in TREE.body if getattr(n, 'name', '') in names]
    ns = dict(globals(), api_router=APIRouter(), _HYDRATION_SYSTEM_MSG='test', _HYDRATION_SCHEMA={})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns


def subject(name):
    return {'nome': name, 'conteudo_programatico': [{'assunto': 'Conteúdo oficial'}]}


def long_edital():
    return ('Regras iniciais.\n' * 9000 + '\nANEXO III\nCONTEÚDO PROGRAMÁTICO\n'
            'CONHECIMENTOS GERAIS PARA TODOS OS CARGOS\nLÍNGUA PORTUGUESA: Interpretação.\n'
            'G07 – Analista Judiciário – Área Judiciária\nDIREITO CIVIL: Atos jurídicos.\n'
            + 'Programa detalhado.\n' * 5000 + '\nH08 – OFICIAL DE JUSTIÇA\nDiligências específicas.\n'
            'I09 – Técnico Judiciário – Área Judiciária\nNOÇÕES DE DIREITO PROCESSUAL PENAL: Procedimentos.\n'
            'ANEXO IV\nFormulário final.\n')


class ContextTests(unittest.TestCase):
    def test_entire_document_includes_annex_beyond_both_old_limits(self):
        text = long_edital()
        self.assertGreater(text.index('CONTEÚDO PROGRAMÁTICO'), 100000)
        self.assertGreater(text.index('I09'), 200000)
        self.assertEqual(edital_context(text), text)

    def test_role_context_keeps_common_and_last_role_without_other_specifics(self):
        text = edital_context(long_edital(), ['Técnico Judiciário - Área Judiciária'])
        self.assertIn('LÍNGUA PORTUGUESA', text)
        self.assertIn('NOÇÕES DE DIREITO PROCESSUAL PENAL', text)
        self.assertNotIn('Diligências específicas', text)
        self.assertNotIn('Formulário final', text)

    def test_unmatched_role_uses_full_document_not_guessed_role(self):
        text = long_edital()
        self.assertEqual(edital_context(text, ['Outro cargo']), text)

    def test_oversized_document_is_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            edital_context('x' * 600001)

    def test_group_suffixes_do_not_turn_groups_into_subjects(self):
        for name in ['Conhecimentos Gerais (P1)', 'CONHECIMENTOS ESPECÍFICOS - Peso 3', 'Conhecimentos Básicos para todos os cargos']:
            self.assertTrue(generic_discipline(subject(name)))
        self.assertFalse(generic_discipline(subject('Direito Constitucional')))

    def test_valid_two_subject_edital_is_not_rejected_by_arbitrary_count(self):
        self.assertFalse(needs_disciplines({'disciplinas': [subject('Português'), subject('Matemática')]}))

    def test_partial_quality_is_explicit(self):
        cargos = [{'disciplinas': []}, {'disciplinas': [subject('Conhecimentos Gerais')]}]
        mark_discipline_quality(cargos)
        self.assertTrue(all(c['disciplinas_status'] == 'incompleto' for c in cargos))


class RepairTests(unittest.IsolatedAsyncioTestCase):
    def test_existing_group_placeholders_are_replaced(self):
        ns = load_routes()
        cargos = [{'nome': 'Analista Judiciário - Área Judiciária', 'disciplinas': [subject('Conhecimentos Gerais (P1)'), subject('Conhecimentos Específicos (P3)')]}]
        parsed = {'disciplinas_comuns': [subject('Português'), subject('Legislação')], 'cargos': [
            {'nome': 'G07 – Analista Judiciário – Área Judiciária', 'disciplinas': [subject('Direito Civil'), subject('Direito Constitucional')]}]}
        self.assertEqual(ns['_merge_hydrated_disciplinas'](cargos, parsed), 1)
        self.assertEqual(len(cargos[0]['disciplinas']), 4)
        self.assertFalse(needs_disciplines(cargos[0]))

    def test_similar_cargo_never_donates_specific_subjects(self):
        ns = load_routes()
        cargos = [{'nome': 'Analista Judiciário - Área Judiciária', 'disciplinas': []}]
        parsed = {'disciplinas_comuns': [subject('Português')], 'cargos': [
            {'nome': 'Técnico Judiciário - Área Judiciária', 'disciplinas': [subject('Noções de Direito')]}]}
        self.assertEqual(ns['_merge_hydrated_disciplinas'](cargos, parsed), 0)
        self.assertEqual(cargos[0]['disciplinas'], [])

    async def test_repair_retries_generic_response_and_reaches_late_annex(self):
        ns = load_routes()
        cargo = {'nome': 'Técnico Judiciário - Área Judiciária', 'disciplinas': [subject('Conhecimentos Gerais (P1)')]}
        bad = {'cargos': [{'nome': cargo['nome'], 'disciplinas': [subject('Conhecimentos Gerais'), subject('Conhecimentos Específicos')]}]}
        good = {'disciplinas_comuns': [subject('Português')], 'cargos': [{'nome': cargo['nome'], 'disciplinas': [subject('Noções de Direito Processual Penal')]}]}
        ns['call_gemini'] = AsyncMock(side_effect=[(json.dumps(bad), None), (json.dumps(good), None)])
        count = await ns['_hydrate_missing_disciplinas'](long_edital(), [cargo], 'test-key', 'user')
        self.assertEqual(count, 1)
        self.assertEqual(ns['call_gemini'].await_count, 2)
        self.assertIn('NOÇÕES DE DIREITO PROCESSUAL PENAL', ns['call_gemini'].call_args.args[0])

    async def test_import_does_not_copy_donor_when_repair_fails(self):
        ns = load_routes()
        db = MagicMock()
        db.edital_analyses.find_one = AsyncMock(return_value={'analysis_version': 3, 'pdf_text': 'Complete source', 'cargos': [
            {'nome': 'Oficial de Justiça', 'disciplinas': []},
            {'nome': 'Contador', 'disciplinas': [subject('Contabilidade')]}]})
        db.study_programs.insert_one = AsyncMock()
        ns.update(db=db, get_current_user=AsyncMock(return_value=SimpleNamespace(user_id='user')),
                  get_user_api_key=AsyncMock(return_value='test-key'), _hydrate_disciplinas_from_text=AsyncMock(return_value=[]))
        with self.assertRaises(HTTPException) as error:
            await ns['import_edital_with_cargo'](SimpleNamespace(headers={}), {'analysis_id': 'analysis', 'cargo_index': 0, 'area_id': 'area'}, None)
        self.assertEqual(error.exception.status_code, 422)
        db.study_programs.insert_one.assert_not_awaited()
        ns['_hydrate_disciplinas_from_text'].assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
