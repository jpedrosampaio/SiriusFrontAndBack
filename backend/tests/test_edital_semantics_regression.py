"""Documentary gates against omissions, invented numbers and AI self-approval."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from edital_pipeline_contracts import (Citation,ProposedFact,RolePart,InventoryUnit,ScopeUnit,DetailUnit,BlockClassification)
from services.edital_semantics import validate_unit,validate_fact,batches,unit_key,merge_fact,EvidenceError


class EditalSemanticGates(unittest.TestCase):
    def setUp(self):
        self.blocks=[{'id':'p0001-b0001','page':1,'text':'Cargo A: Analista. Vagas: CR.'},
            {'id':'p0001-b0002','page':1,'text':'Todos os cargos: Língua Portuguesa.'},
            {'id':'p0002-b0001','page':2,'text':'Conhecimentos gerais (P1): 12 questões. Peso 1.'}]

    def fact(self,value,block=0,quote=None):
        item=self.blocks[block]
        return ProposedFact(value=value,state='extracted',sources=[Citation(page=item['page'],block_id=item['id'],quote=quote or item['text'])])

    def inventory(self,classifications=None):
        return InventoryUnit(roles=[RolePart(name=self.fact('Analista'),vacancies=self.fact('CR'))],
            classifications=classifications or [BlockClassification(block_id=self.blocks[0]['id'],end_block_id=self.blocks[-1]['id'],kind='general')])

    def test_inventory_is_small_unconfirmed_and_absence_is_not_zero(self):
        result=validate_unit(self.inventory(),self.blocks)
        self.assertIsNone(result.roles[0].salary.value)
        self.assertEqual(result.roles[0].vacancies.value,'CR')
        self.assertFalse(hasattr(result.roles[0].name,'verified'))
        with self.assertRaises(ValueError):ProposedFact(value='Analista',state='extracted',sources=self.fact('Analista').sources,verified=True)

    def test_citation_must_match_page_block_and_exact_excerpt(self):
        for citation in [Citation(page=2,block_id='p0001-b0001',quote='Analista'),
            Citation(page=1,block_id='foreign-source',quote='Analista'),
            Citation(page=1,block_id='p0001-b0001',quote='Remuneração inventada')]:
            with self.assertRaises(EvidenceError):validate_fact(ProposedFact(value='Analista',state='extracted',sources=[citation]),{b['id']:b for b in self.blocks})

    def test_group_count_cannot_support_a_different_number_or_unknown_zero(self):
        source={b['id']:b for b in self.blocks}
        validate_fact(self.fact('12',2),source)
        for fact in [self.fact('2',2),self.fact('0'),self.fact('50',2)]:
            with self.assertRaises(EvidenceError):validate_fact(fact,source)

    def test_inventory_cannot_silently_omit_or_overlap_source_blocks(self):
        for spans in [[BlockClassification(block_id='p0001-b0001',kind='roles')],
            [BlockClassification(block_id='p0001-b0001',end_block_id='p0002-b0001',kind='general'),
                BlockClassification(block_id='p0002-b0001',kind='exam_rules')]]:
            with self.assertRaises(EvidenceError):validate_unit(self.inventory(spans),self.blocks)

    def test_context_can_support_a_fact_but_cannot_fake_processed_coverage(self):
        result=self.inventory([BlockClassification(block_id='p0001-b0002',kind='program')])
        validate_unit(result,self.blocks[1:2],self.blocks[:1])
        with self.assertRaises(EvidenceError):validate_unit(self.inventory(),self.blocks[1:2],self.blocks[:1])

    def test_semantic_scope_and_ambiguous_content_cannot_self_confirm(self):
        with self.assertRaises(ValueError):BlockClassification(block_id='p0001-b0002',kind='program',scope='all_roles')
        with self.assertRaises(ValueError):DetailUnit(applicability='ambiguous',covered_block_ids=['p0001-b0002'],
            disciplines=[{'name':self.fact('Língua Portuguesa',1)}])
        with self.assertRaises(ValueError):DetailUnit(applicability='selected_role',covered_block_ids=['p0001-b0002'])

    def test_detail_requires_full_unit_coverage_even_with_valid_json(self):
        result=DetailUnit(applicability='other_role',covered_block_ids=['p0001-b0001'])
        with self.assertRaises(EvidenceError):validate_unit(result,self.blocks)

    def test_batch_replay_identity_and_table_context_remain_scoped(self):
        blocks=[{**self.blocks[0],'text':'A'*80,'table_id':'table-a','cells':['A','B']} for _ in range(4)]
        for index,block in enumerate(blocks):block['id']=f'p0001-b{index+1:04d}'
        chunks=list(batches(blocks,characters=240))
        self.assertEqual(sum(len(c) for c in chunks),4)
        self.assertTrue(all(b['table_id']=='table-a' and b['cells']==['A','B'] for c in chunks for b in c))
        ids=[b['id'] for b in blocks]
        self.assertEqual(unit_key('detail','role-a',ids),unit_key('detail','role-a',ids))
        self.assertNotEqual(unit_key('detail','role-a',ids),unit_key('detail','role-b',ids))

    def test_conflicting_proposals_are_not_silently_replaced(self):
        first=merge_fact(None,self.fact('1',2));second=merge_fact(first,self.fact('12',2))
        self.assertEqual(first['state'],'extracted');self.assertEqual(first['alternatives'],[])
        self.assertEqual(second['state'],'ambiguous');self.assertEqual(second['verification'],'awaiting_review')
        self.assertEqual(second['value'],'1');self.assertEqual(second['alternatives'][0]['value'],'12')
        self.assertEqual(merge_fact(second,ProposedFact())['state'],'ambiguous')

    def test_flat_topics_keep_hierarchy_without_repeating_ancestor_evidence(self):
        self.blocks.append({'id':'p0002-b0002','page':2,'text':'1 Leitura. 1.1 Interpretação.'})
        result=DetailUnit(applicability='shared',scope_sources=self.fact('Todos os cargos',1).sources,
            covered_block_ids=['p0002-b0002'],disciplines=[{'name':self.fact('Língua Portuguesa',1),
                'topics':[{'key':'p0002-b0002-t1','title':self.fact('Leitura',3,'1 Leitura.'),'numbering':'1'},
                    {'key':'p0002-b0002-t2','title':self.fact('Interpretação',3,'1.1 Interpretação.'),'numbering':'1.1','parent_key':'p0002-b0002-t1'}]}])
        validate_unit(result,self.blocks[3:],self.blocks[:3])
        result.disciplines[0].topics[1].parent_key='foreign-parent'
        with self.assertRaises(EvidenceError):validate_unit(result,self.blocks[3:],self.blocks[:3])
        with self.assertRaises(ValueError):DetailUnit.model_validate({**result.model_dump(),
            'disciplines':[{'name':self.fact('Língua Portuguesa',1),'topics':[{'key':'cycle','title':self.fact('Leitura',3),'parent_key':'cycle'}]}]})

    def test_a_sourced_knowledge_group_is_not_counted_as_a_discipline(self):
        result=DetailUnit(applicability='shared',scope_sources=self.fact('Todos os cargos',1).sources,
            covered_block_ids=['p0002-b0001'],disciplines=[{'name':self.fact('Conhecimentos gerais (P1)',2)}])
        with self.assertRaises(EvidenceError) as error:
            validate_unit(result,self.blocks[2:3],self.blocks[1:2],container_titles=['Conhecimentos gerais (P1)'])
        self.assertEqual(error.exception.code,'container_as_discipline')

    def test_selected_role_scope_resolution_is_small_sourced_and_exhaustive(self):
        result=ScopeUnit(bindings=[{'section_key':'shared-program','decision':'include','sources':self.fact('Todos os cargos',1).sources,
            'reason':'A seção se aplica a todos os cargos, conforme o trecho citado.'}])
        validate_unit(result,self.blocks[1:2],expected_section_keys=['shared-program'])
        with self.assertRaises(EvidenceError):validate_unit(result,self.blocks[1:2],expected_section_keys=['shared-program','another-role'])
        with self.assertRaises(ValueError):ScopeUnit(bindings=[{'section_key':'invented','decision':'include','reason':'Sem fonte'}])

    def test_an_unrelated_primary_citation_cannot_launder_context_only_topic_or_rule_values(self):
        from edital_pipeline_contracts import ProposedFact
        # Both excerpts exist, but the value is supported only in context. That
        # does not make it part of this selected primary content window.
        fact=ProposedFact(value='Língua Portuguesa',state='extracted',sources=[
            self.fact('CR',0).sources[0],self.fact('Língua Portuguesa',1).sources[0]])
        topic=DetailUnit(applicability='shared',scope_sources=self.fact('Todos os cargos',1).sources,
            covered_block_ids=['p0001-b0001'],disciplines=[{'name':self.fact('Analista',0),
                'topics':[{'key':'p0001-b0001-fake','title':fact}]}])
        with self.assertRaises(EvidenceError):validate_unit(topic,self.blocks[:1],self.blocks[1:])
        rule=DetailUnit(applicability='shared',scope_sources=self.fact('Todos os cargos',1).sources,
            covered_block_ids=['p0001-b0001'],rules=[{'target_scope':'group','target':self.fact('Conhecimentos gerais (P1)',2),
                'kind':'question_count','fact':ProposedFact(value='12',state='extracted',sources=[
                    self.fact('CR',0).sources[0],self.fact('12',2).sources[0]])}])
        with self.assertRaises(EvidenceError):validate_unit(rule,self.blocks[:1],self.blocks[1:])

    def test_assisted_verification_cannot_self_approve_or_review_another_target(self):
        from edital_pipeline_contracts import VerificationUnit
        key='a'*64
        result=VerificationUnit(reviewed_unit_key=key,covered_block_ids=['p0001-b0001'])
        validate_unit(result,self.blocks[:1],expected_reviewed_unit_key=key)
        with self.assertRaises(EvidenceError):validate_unit(result,self.blocks[:1],expected_reviewed_unit_key='b'*64)
        with self.assertRaises(ValueError):VerificationUnit(**result.model_dump(),confidence=100,verified=True)
        result=VerificationUnit.model_validate({**result.model_dump(),'findings':[
            {'kind':'missing_role','severity':'blocker','description':'Conferir trecho.',
             'sources':[self.fact('Língua Portuguesa',1).sources[0].model_dump()]}]})
        with self.assertRaises(EvidenceError):validate_unit(result,self.blocks[:1],self.blocks[1:],expected_reviewed_unit_key=key)
