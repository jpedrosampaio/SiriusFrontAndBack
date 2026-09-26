import sys
import unittest
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edital_audit import audit_cargos


class AuditTests(unittest.TestCase):
    def test_tjce_reference_has_ten_subjects_per_judicial_role(self):
        fixture = json.loads(Path(__file__).with_name('tjce_syllabus_headings.json').read_text(encoding='utf-8'))
        pages = [{'page': 31, 'text': 'CONTEÚDO PROGRAMÁTICO\nCONHECIMENTOS GERAIS – PARA TODOS OS CARGOS\n' + '\n'.join(s['name'] + ': Conteúdo' for s in fixture['common'])}]
        for role in fixture['roles']:
            pages.append({'page': role['subjects'][0]['page'], 'text': role['code'] + ' – ' + role['name'] + '\n' + '\n'.join(s['name'] + (' Princípios aplicáveis' if s['name'].endswith('DIREITO PENAL') else ': Conteúdo') for s in role['subjects'])})
        for role in fixture['roles']:
            cargo = {'codigo': role['code'], 'disciplinas': [{'nome': 'Conhecimentos Gerais'}, {'nome': 'Conhecimentos Específicos'}]}
            audit_cargos([cargo], pages)
            self.assertEqual(len(cargo['conferencia']['missing']), 10)

    pages = [{'page': 31, 'text': 'CONTEÚDO PROGRAMÁTICO\nCONHECIMENTOS GERAIS – PARA TODOS OS CARGOS\nLÍNGUA PORTUGUESA: Interpretação\nG07 – Analista Judiciário – ÁREA JUDICIÁRIA\nDIREITO CIVIL: Pessoas\nH08 – Oficial de Justiça\nDIREITO PENAL: Crimes\nANEXO IV\nOUTRO TÍTULO: Não pertence'}]

    def test_partial_list_is_incomplete_and_does_not_mix_roles(self):
        cargo = {'nome': 'Analista Judiciário – Área Judiciária', 'disciplinas': [{'nome': 'Língua Portuguesa'}]}
        audit_cargos([cargo], self.pages)
        self.assertEqual(cargo['disciplinas_status'], 'incompleto')
        self.assertEqual([x['name'] for x in cargo['conferencia']['missing']], ['DIREITO CIVIL'])
        self.assertEqual(cargo['conferencia']['missing'][0]['page'], 31)

    def test_unknown_role_is_not_certified(self):
        cargo = {'nome': 'Analista Sênior', 'disciplinas': []}
        audit_cargos([cargo], self.pages)
        self.assertEqual(cargo['conferencia']['status'], 'nao_verificado')

    def test_code_and_no_heading_after_annex(self):
        cargo = {'codigo': 'H08', 'nome': 'Oficial', 'disciplinas': [{'nome': 'Língua Portuguesa'}, {'nome': 'Direito Penal'}]}
        audit_cargos([cargo], self.pages)
        self.assertEqual(cargo['conferencia']['status'], 'titulos_conferidos')
        self.assertEqual(len(cargo['conferencia']['expected']), 2)
