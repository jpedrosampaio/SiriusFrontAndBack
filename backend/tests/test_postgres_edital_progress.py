"""Synthetic end-to-end stage advancement, without provider or production IO."""
import hashlib
import os
import unittest
from datetime import timedelta
from uuid import uuid4
from types import SimpleNamespace
from sqlalchemy import select, delete, func
from db.session import unit_of_work
from db.models.identity import User
from db.models.edital_units import EditalUnit
from edital_pipeline_contracts import (DocumentIR, SourcePage, SourceBlock, ContentScope, HumanCorrection,
    IdentifiedRole, CanonicalFact, BlockClassification, SectionBinding, InventoryUnit)
from services import edital_pipeline_store as store, edital_pipeline_units as units, edital_pipeline_progress as progress
from services import edital_pipeline_compile as compiler
import test_postgres_agent as setup
from edital_test_helpers import persist_approved


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class IncrementalProgress(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = setup.PostgresAgent.asyncSetUp

    async def asyncTearDown(self):
        async with unit_of_work() as session: await session.execute(delete(User).where(User.id.in_((self.uid, self.other))))
        await setup.PostgresAgent.asyncTearDown(self)

    def fixture(self):
        lines = ['Cargo A: Analista; Cargo B: Técnico.', 'Programa comum para todos os cargos.',
            'Português: redação oficial.', 'Programa específico somente para Cargo B.',
            'Informática: redes.', 'Prova objetiva para todos os cargos.', 'Grupo comum: peso 2; 40 questões.']
        blocks = [SourceBlock(id=f'p0001-b{i:04d}', page=1, text=value, bbox=(0, i * 20, 500, i * 20 + 15)) for i, value in enumerate(lines, 1)]
        return DocumentIR(sha256=hashlib.sha256('\n'.join(lines).encode()).hexdigest(), size_bytes=500,
            pages=[SourcePage(page=1, width=600, height=800, quality='text', characters=sum(map(len, lines)), blocks=blocks)])

    def citation(self, document, point):
        block = document.pages[0].blocks[point - 1]
        return {'page': 1, 'block_id': block.id, 'quote': block.text}

    def fact(self, document, value, point):
        return {'value': value, 'state': 'extracted', 'sources': [self.citation(document, point)]}

    async def accept(self, claim, proposal):
        await units.provider_attempt(claim, SimpleNamespace(provider='mock', name='synthetic-no-network'))
        await units.complete(claim, proposal, {'total_tokens': 100}, progress.consolidate)
        await self.drain_checks()

    async def drain_checks(self):
        while True:
            claim=await units.claim_next(kind='verify')
            if claim is None:return
            snapshot=await units.snapshot(claim)
            await units.provider_attempt(claim,SimpleNamespace(provider='mock',name='synthetic-check-no-network'))
            await units.complete(claim,{'reviewed_unit_key':snapshot['metadata']['reviewed_unit_key'],
                'covered_block_ids':[b['id'] for b in snapshot['primary']],'findings':[]},
                {'total_tokens':30},progress.consolidate)

    async def test_parent_from_previous_batch_is_available_and_keeps_sourced_numbered_hierarchy(self):
        lines=['Cargo A: Analista.', 'Programa comum para todos os cargos. Língua Portuguesa.', '1 Leitura.']
        lines += [('Contexto documental sem nova disciplina. ' * 30) for _ in range(5)]
        lines += ['1.1 Interpretação.']
        blocks=[SourceBlock(id=f'p0001-b{i:04d}',page=1,text=text,bbox=(0,i*20,500,i*20+15),
            parent_heading_hint='p0001-b0002' if i>2 else None) for i,text in enumerate(lines,1)]
        document=DocumentIR(sha256=hashlib.sha256('\n'.join(lines).encode()).hexdigest(),size_bytes=10000,
            pages=[SourcePage(page=1,width=600,height=800,quality='text',characters=sum(map(len,lines)),blocks=blocks)])
        first=await store.reserve_intake(self.uid,document.sha256,'synthetic-long.pdf',False,str(uuid4()))
        result=await persist_approved(self.uid,first['job_id'],first['token'],document)
        async with unit_of_work() as session:
            analysis=await store.owned_analysis(session,self.uid,result['analysis_id'],lock=True)
            state=store.manifest(analysis);state.inventory.status='awaiting_review'
            state.inventory.roles=[IdentifiedRole(id='role-a',source_name='Analista',name=CanonicalFact.model_validate(self.fact(document,'Analista',1)))]
            section=BlockClassification(block_id=blocks[1].id,end_block_id=blocks[-1].id,kind='program',level='knowledge_group',
                title=self.fact(document,'Programa comum',2),scope='all_roles',scope_sources=[self.citation(document,2)])
            state.inventory.sections=[section];state.selected_role_id='role-a'
            scope=ContentScope(generation=uuid4());state.scopes['role-a']=scope
            key=compiler.section_key(section);scope.bindings[key]=SectionBinding(section_key=key,decision='include',
                sources=[self.citation(document,2)],reason='Associação documental da fixture.')
            # Seed a previously materialized inventory, then exercise real
            # detail scheduling/checkpointing rather than a giant mock output.
            for unit in (await session.scalars(select(EditalUnit).where(EditalUnit.user_id==self.uid))).all():
                unit.status='completed';unit.finished_at=store.utc_now()
                unit.result=InventoryUnit(classifications=[{'block_id':unit.source_blocks[0],
                    'end_block_id':unit.source_blocks[-1],'kind':'program'}]).model_dump(mode='json')
            await session.flush()
            await progress.advance_selected(session,analysis,first['job_id'],state);store.write_manifest(analysis,state)
        await self.drain_checks()
        root_key='p0001-b0003-1'
        for expected in (3,9):
            claim=await units.claim_next();self.assertEqual(claim.kind,'detail')
            snapshot=await units.snapshot(claim);ids=[b['id'] for b in snapshot['primary']]
            self.assertIn(f'p0001-b{expected:04d}',ids)
            topic={'key':root_key if expected==3 else 'p0001-b0009-1',
                'title':self.fact(document,'Leitura' if expected==3 else 'Interpretação',expected),
                'numbering':'1' if expected==3 else '1.1'}
            if expected==9:
                topic['parent_key']=root_key
                self.assertIn(root_key,snapshot['validation']['known_topic_owners'])
                self.assertTrue(any(p['key']==root_key for p in snapshot['metadata']['previous_topic_proposals']))
            await self.accept(claim,{'applicability':'shared','scope_sources':[self.citation(document,2)],
                'covered_block_ids':ids,'disciplines':[{'name':self.fact(document,'Língua Portuguesa',2),'topics':[topic]}]})
        async with unit_of_work() as session:
            analysis=await store.owned_analysis(session,self.uid,result['analysis_id'])
            topics=store.manifest(analysis).scopes['role-a'].program.disciplines[0].topics
            by_name={t.title.value:t for t in topics}
            self.assertEqual(by_name['Interpretação'].parent_id,by_name['Leitura'].id)
            self.assertEqual(by_name['Interpretação'].numbering,'1.1')

    async def test_early_inventory_selection_scoped_depth_group_rules_and_resume_preserve_corrections(self):
        document = self.fixture()
        first = await store.reserve_intake(self.uid, document.sha256, 'synthetic.pdf', False, str(uuid4()))
        accepted = await persist_approved(self.uid, first['job_id'], first['token'], document)
        parent = await units.claim_next()
        await units.provider_attempt(parent, SimpleNamespace(provider='mock', name='synthetic-no-network'))
        await units.fail(parent, 'output_truncated')
        # Claim order need not be page order. Complete the role-bearing child
        # first, retaining the second child as unfinished discovery work.
        async with unit_of_work() as session:
            rows = (await session.scalars(select(EditalUnit).where(EditalUnit.user_id == self.uid, EditalUnit.status == 'pending'))).all()
            for row in rows:
                if document.pages[0].blocks[0].id not in row.source_blocks:
                    row.available_at = store.utc_now() + timedelta(minutes=5)
        claim = await units.claim_next()
        inventory = {'roles': [{'name': self.fact(document, name, 1), 'code': self.fact(document, code, 1)}
            for name, code in [('Analista', 'A'), ('Técnico', 'B')]], 'classifications': [
                {'block_id': 'p0001-b0001', 'kind': 'roles'},
                {'block_id': 'p0001-b0002', 'end_block_id': 'p0001-b0003', 'kind': 'program', 'level': 'knowledge_group',
                 'title': self.fact(document, 'Programa comum', 2), 'scope': 'all_roles', 'scope_sources': [self.citation(document, 2)]}]}
        await self.accept(claim, inventory)
        async with unit_of_work() as session:
            analysis = await store.owned_analysis(session, self.uid, accepted['analysis_id'], lock=True)
            state = store.manifest(analysis)
            self.assertEqual(len(state.inventory.roles), 2); self.assertEqual(state.inventory.status, 'processing')
            selected = next(r.id for r in state.inventory.roles if r.name.value == 'Analista')
            state.selected_role_id = selected; state.scopes[selected] = ContentScope(generation=uuid4())
            store.write_manifest(analysis, state)
            rows = (await session.scalars(select(EditalUnit).where(EditalUnit.user_id == self.uid, EditalUnit.status == 'pending'))).all()
            for row in rows: row.available_at = store.utc_now()
        claim = await units.claim_next()
        await self.accept(claim, {'classifications': [
            {'block_id': 'p0001-b0004', 'end_block_id': 'p0001-b0005', 'kind': 'program',
             'scope': 'named_roles', 'role_references': [self.fact(document, 'Cargo B', 4)], 'scope_sources': [self.citation(document, 4)]},
            {'block_id': 'p0001-b0006', 'end_block_id': 'p0001-b0007', 'kind': 'exam_rules',
             'scope': 'all_roles', 'scope_sources': [self.citation(document, 6)]}]})
        claim = await units.claim_next()
        if claim is None:
            async with unit_of_work() as session:
                analysis = await store.owned_analysis(session, self.uid, accepted['analysis_id'])
                current = store.manifest(analysis)
                rows = (await session.execute(select(EditalUnit.kind, EditalUnit.status, EditalUnit.scope_key,
                    EditalUnit.available_at).where(EditalUnit.user_id == self.uid))).all()
                self.fail(str({'status': current.status, 'error': current.error_kind,
                    'selected': current.selected_role_id, 'units': [tuple(r) for r in rows], 'now': store.utc_now()}))
        self.assertEqual(claim.kind, 'scope')
        data = await units.snapshot(claim); metadata = data['metadata']['sections']
        await self.accept(claim, {'bindings': [{'section_key': item['section_key'],
            'decision': 'exclude' if item['first'] == 'p0001-b0004' else 'include',
            'sources': [self.citation(document, 4 if item['first'] == 'p0001-b0004' else 2 if item['first'] == 'p0001-b0002' else 6)],
            'reason': 'Aplicação esperada verificada nesta fixture sintética.'} for item in metadata]})
        for _ in range(2):
            claim = await units.claim_next(); self.assertEqual(claim.kind, 'detail')
            data = await units.snapshot(claim); ids = [b['id'] for b in data['primary']]
            self.assertFalse({'p0001-b0004', 'p0001-b0005'} & set(ids))
            proposal = {'applicability': 'shared', 'scope_sources': [self.citation(document, 2 if 'p0001-b0002' in ids else 6)], 'covered_block_ids': ids}
            if 'p0001-b0002' in ids:
                proposal['disciplines'] = [{'name': self.fact(document, 'Português', 3),
                    'topics': [{'key': 'p0001-b0003-1', 'title': self.fact(document, 'redação oficial', 3)}]}]
            else:
                proposal['rules'] = [{'target_scope': 'group', 'target': self.fact(document, 'Grupo comum', 7),
                    'kind': kind, 'fact': self.fact(document, value, 7)} for kind, value in [('weight', '2'), ('question_count', '40')]]
            await self.accept(claim, proposal)
            async with unit_of_work() as session:
                analysis = await store.owned_analysis(session, self.uid, accepted['analysis_id'], lock=True)
                state = store.manifest(analysis); scope = state.scopes[selected]
                if scope.program.disciplines:
                    discipline = scope.program.disciplines[0]; path = f'disciplines/{discipline.id}/name'
                    correction = HumanCorrection(value='Língua Portuguesa', note='Nome conferido pelo proprietário.', recorded_at=store.utc_now())
                    scope.corrections[path] = correction; discipline.name = compiler.corrected(discipline.name, correction)
                    store.write_manifest(analysis, state)
        self.assertIsNone(await units.claim_next())
        async with unit_of_work() as session:
            analysis = await store.owned_analysis(session, self.uid, accepted['analysis_id'], lock=True)
            state = store.manifest(analysis); scope = state.scopes[selected]
            self.assertEqual(state.status, 'awaiting_review'); self.assertEqual(state.error_kind, None)
            self.assertEqual(scope.program.disciplines[0].name.value, 'Língua Portuguesa')
            self.assertEqual(scope.program.disciplines[0].name.origin, 'human_declared')
            self.assertEqual(len(scope.program.rules), 2); self.assertTrue(all(r.target_scope == 'group' for r in scope.program.rules))
            self.assertEqual(state.budget.reserved_attempts, 10); self.assertTrue(state.budget.usage_incomplete)
            before = await session.scalar(select(func.count()).select_from(EditalUnit).where(EditalUnit.user_id == self.uid))
            await progress.advance_selected(session, analysis, first['job_id'], state)
            after = await session.scalar(select(func.count()).select_from(EditalUnit).where(EditalUnit.user_id == self.uid))
            self.assertEqual(before, after); self.assertEqual(state.budget.reserved_attempts, 10)
