import unittest
from datetime import datetime, timezone
from uuid import uuid4
from edital_pipeline_contracts import (InventoryState, InventoryUnit, ContentScope, DetailUnit, HumanCorrection)
from services import edital_pipeline_compile as compiler


class Consolidation(unittest.TestCase):
    def fact(self, value, block='p0001-b0001', quote=None):
        return {'value': value, 'state': 'extracted', 'sources': [{'page': 1, 'block_id': block, 'quote': quote or value}]}

    def inventory(self, roles=(), facts=(), block='p0001-b0001'):
        return InventoryUnit(roles=list(roles), facts=list(facts), classifications=[{'block_id': block, 'kind': 'roles'}])

    def role(self, salary=None, block='p0001-b0001'):
        value = {'name': self.fact('Analista', block), 'code': self.fact('A', block)}
        if salary: value['salary'] = self.fact(salary, block)
        return value

    def detail(self, topics=(), rules=(), discipline='Direito', block='p0001-b0001'):
        return DetailUnit(applicability='selected_role', scope_sources=self.fact('Perfil A', block)['sources'],
            covered_block_ids=[block], disciplines=[{'name': self.fact(discipline, block), 'topics': list(topics)}], rules=list(rules))

    def test_two_official_roles_in_one_table_cell_cannot_share_an_identity(self):
        state = InventoryState(generation=uuid4())
        proposal = self.inventory(roles=[{'name': self.fact(name, quote='Analista e Técnico')} for name in ('Analista', 'Técnico')])
        compiler.inventory(state, proposal); compiler.inventory(state, proposal)
        self.assertEqual(len(state.roles), 2); self.assertEqual(len({r.id for r in state.roles}), 2)
        self.assertTrue(all(r.requirements.value is None and r.vacancies.value is None for r in state.roles))

    def test_repeated_sourced_code_merges_without_merging_unnamed_specialties(self):
        state = InventoryState(generation=uuid4())
        for block in ('p0001-b0001', 'p0001-b0002'): compiler.inventory(state, self.inventory([self.role(block=block)], block=block))
        self.assertEqual(len(state.roles), 1); self.assertEqual(len(state.roles[0].source_keys), 2)
        compiler.inventory(state, self.inventory([{'name': self.fact('Analista', 'p0001-b0003')}], block='p0001-b0003'))
        self.assertEqual(len(state.roles), 2); self.assertTrue(state.issues)

    def test_conflicting_salary_is_not_silently_selected_and_human_correction_survives(self):
        state = InventoryState(generation=uuid4())
        compiler.inventory(state, self.inventory([self.role('10')]))
        identity = state.roles[0].id
        compiler.inventory(state, self.inventory([self.role('20', 'p0001-b0002')], block='p0001-b0002'))
        self.assertEqual(state.roles[0].salary.state, 'ambiguous')
        correction = HumanCorrection(value='15', note='Valor conferido pelo proprietário na retificação.', recorded_at=datetime.now(timezone.utc))
        state.corrections[f'roles/{identity}/salary'] = correction
        compiler.inventory(state, self.inventory([self.role('30', 'p0001-b0003')], block='p0001-b0003'))
        fact = state.roles[0].salary
        self.assertEqual((fact.value, fact.state, fact.verification, fact.origin), ('15', 'corrected_by_user', 'confirmed', 'human_declared'))
        self.assertEqual(fact.sources, []); self.assertTrue(fact.alternatives); self.assertEqual(state.roles[0].id, identity)

    def test_missing_is_not_zero_and_multiple_exam_dates_require_review(self):
        state = InventoryState(generation=uuid4())
        for value, block in [('01/12/2026', 'p0001-b0001'), ('02/12/2026', 'p0001-b0002')]:
            compiler.inventory(state, self.inventory(facts=[{'key': 'exam_date', 'fact': self.fact(value, block)}], block=block))
        self.assertEqual(len(state.facts), 2); self.assertTrue(all(f.fact.state == 'ambiguous' for f in state.facts))
        self.assertTrue(state.issues)

    def test_group_weight_and_quantity_never_become_each_discipline_values(self):
        scope = ContentScope(generation=uuid4())
        rules = [{'target_scope': 'group', 'target': self.fact('Conhecimentos específicos'), 'kind': kind, 'fact': self.fact(value)}
            for kind, value in [('weight', '2'), ('question_count', '40')]]
        compiler.program(scope, self.detail(rules=rules))
        compiler.program(scope, self.detail(discipline='Gestão', block='p0001-b0002'))
        self.assertEqual(len(scope.program.disciplines), 2); self.assertEqual(len(scope.program.rules), 2)
        self.assertTrue(all(r.target_scope == 'group' for r in scope.program.rules))
        self.assertTrue(all('weight' not in d.model_dump() and 'question_count' not in d.model_dump() for d in scope.program.disciplines))

    def test_flat_nodes_preserve_hierarchy_and_deduplicate_repeated_batches(self):
        scope = ContentScope(generation=uuid4())
        first = self.detail(topics=[{'key': 'p0001-b0001-item1', 'title': self.fact('Administração')},
            {'key': 'p0001-b0001-item2', 'title': self.fact('Princípios'), 'parent_key': 'p0001-b0001-item1'}])
        compiler.program(scope, first); compiler.program(scope, first)
        second = self.detail(topics=[{'key': 'p0001-b0002-item3', 'title': self.fact('Legalidade', 'p0001-b0002'), 'parent_key': 'p0001-b0001-item2'}], block='p0001-b0002')
        compiler.program(scope, second)
        topics = {t.title.value: t for t in scope.program.disciplines[0].topics}
        self.assertEqual(len(topics), 3); self.assertEqual(topics['Princípios'].parent_id, topics['Administração'].id)
        self.assertEqual(topics['Legalidade'].parent_id, topics['Princípios'].id)

    def test_other_role_or_ambiguous_data_never_contributes_selected_role_program(self):
        for applicability in ('other_role', 'ambiguous'):
            scope = ContentScope(generation=uuid4())
            compiler.program(scope, DetailUnit(applicability=applicability, covered_block_ids=['p0001-b0001']))
            self.assertEqual(scope.program.disciplines, []); self.assertTrue(scope.program.issues)
