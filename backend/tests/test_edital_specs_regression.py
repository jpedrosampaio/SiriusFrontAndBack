import unittest
from datetime import datetime, timezone
from uuid import uuid4
from edital_pipeline_contracts import (PipelineManifest, DocumentSummary, InventoryState, IdentifiedRole,
    CanonicalFact, Citation, ContentScope, BlockClassification, SectionBinding, HumanCorrection)
from services.edital_pipeline_specs import scope_specs, detail_specs
from services.edital_pipeline_compile import section_key
from services.edital_semantics import EvidenceError


class SelectedRoleSpecs(unittest.TestCase):
    def fixture(self):
        text = ['Cargo A Analista; Cargo B Técnico.', 'Todos os cargos: Programa comum.', 'Português: redação oficial.',
            'Matemática: álgebra.', 'Somente cargo B: conteúdo específico.', 'Informática: redes.',
            'Todos os cargos: prova objetiva, grupo comum.', 'Peso do grupo: 2; questões do grupo: 40.']
        blocks = [{'id': f'p0001-b{i:04d}', 'page': 1, 'text': value, 'kind': 'line'} for i, value in enumerate(text, 1)]
        def citation(i): return Citation(page=1, block_id=blocks[i - 1]['id'], quote=text[i - 1])
        role = IdentifiedRole(id='analyst', source_name='Analista', name=CanonicalFact(value='Analista', state='extracted', sources=[citation(1)]))
        sections = [BlockClassification(block_id=blocks[a - 1]['id'], end_block_id=blocks[b - 1]['id'], kind=kind)
            for a, b, kind in [(2, 4, 'program'), (5, 6, 'program'), (7, 8, 'exam_rules')]]
        state = PipelineManifest(source=DocumentSummary(hash='a' * 64, pages=1, characters=sum(map(len, text)), blocks=8, size_bytes=100),
            inventory=InventoryState(generation=uuid4(), roles=[role], sections=sections),
            scopes={'analyst': ContentScope(generation=uuid4())})
        scope = state.scopes['analyst']
        for section, decision, point in zip(sections, ['include', 'exclude', 'include'], [2, 5, 7]):
            scope.bindings[section_key(section)] = SectionBinding(section_key=section_key(section), decision=decision,
                sources=[citation(point)], reason='Aplicabilidade verificada na fixture sintética.')
        return state, blocks

    def test_only_selected_and_shared_content_is_scheduled_in_depth(self):
        state, blocks = self.fixture(); specs, ambiguous = detail_specs(state, 'analyst', blocks)
        self.assertEqual(ambiguous, [])
        self.assertEqual({point for spec in specs for point in spec.primary}, {blocks[i - 1]['id'] for i in [2, 3, 4, 7, 8]})
        self.assertTrue(all(spec.kind == 'detail' and len(spec.primary) <= 60 for spec in specs))
        # Context can carry headings/role names; it does not become coverage.
        self.assertTrue(any(blocks[0]['id'] in spec.context for spec in specs))

    def test_missing_or_ambiguous_binding_is_visible_and_never_silently_included(self):
        state, blocks = self.fixture(); key = section_key(state.inventory.sections[0]); del state.scopes['analyst'].bindings[key]
        specs, ambiguous = detail_specs(state, 'analyst', blocks)
        self.assertEqual(ambiguous, [key]); self.assertEqual({p for s in specs for p in s.primary}, {blocks[6]['id'], blocks[7]['id']})

    def test_scope_discovery_is_bounded_and_does_not_recall_already_bound_sections(self):
        state, blocks = self.fixture()
        self.assertEqual(scope_specs(state, 'analyst', blocks), [])
        state.scopes['analyst'].bindings = {}
        specs = scope_specs(state, 'analyst', blocks)
        keys = [key for spec in specs for key in spec.validation['expected_section_keys']]
        self.assertEqual(set(keys), {section_key(s) for s in state.inventory.sections})
        for spec in specs:
            self.assertLessEqual(sum(len(next(b['text'] for b in blocks if b['id'] == i)) + 80 for i in spec.primary), 6000)
            self.assertLessEqual(sum(len(next(b['text'] for b in blocks if b['id'] == i)) for i in spec.context), 3000)

    def test_explicit_owner_override_can_include_an_unrecognized_interval_without_claiming_ai_evidence(self):
        state, blocks = self.fixture(); section = state.inventory.sections[1]; section.kind = 'other'
        key = section_key(section); scope = state.scopes['analyst']
        scope.binding_corrections[key] = HumanCorrection(value='include', note='Associação conferida pelo proprietário.', recorded_at=datetime.now(timezone.utc))
        specs, _ = detail_specs(state, 'analyst', blocks)
        self.assertTrue({blocks[4]['id'], blocks[5]['id']} <= {p for s in specs for p in s.primary})
        self.assertNotIn(key, [k for s in scope_specs(state, 'analyst', blocks) for k in s.validation['expected_section_keys']])
        self.assertEqual(scope.binding_corrections[key].note, 'Associação conferida pelo proprietário.')

    def test_unknown_role_or_broken_source_range_fails_closed(self):
        state, blocks = self.fixture()
        with self.assertRaises(EvidenceError): detail_specs(state, 'another', blocks)
        state.inventory.sections[0].end_block_id = 'missing'
        with self.assertRaises(EvidenceError): detail_specs(state, 'analyst', blocks)

    def test_annex_is_semantically_assessed_even_without_a_program_heading(self):
        state,blocks=self.fixture();section=state.inventory.sections[0];section.kind='annex'
        specs=scope_specs(state,'analyst',blocks)
        match=next(info for spec in specs for info in spec.metadata['sections'] if info['section_key']==section_key(section))
        self.assertEqual(match['kind_proposal'],'annex')
        self.assertTrue(match['evidence_window_limited']) # first/last are not the middle of this interval
