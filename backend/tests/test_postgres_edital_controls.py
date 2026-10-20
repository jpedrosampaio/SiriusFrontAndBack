"""Owner review, immutable evidence, reanalysis and transaction fences on SQL."""
import asyncio
import hashlib
import os
import unittest
from uuid import uuid4,UUID
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import select,delete,func
from db.session import unit_of_work
from db.models.identity import User
from db.models.command import CommandAudit
from db.models.edital_units import EditalUnit
from edital_pipeline_contracts import DocumentIR,SourcePage,SourceBlock
from services import (edital_pipeline_store as store,edital_pipeline_units as units,
    edital_pipeline_progress as progress,edital_pipeline_controls as controls,edital_pipeline_compile as compiler)
import test_postgres_agent as setup
from edital_test_helpers import persist_approved


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class HumanControls(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=setup.PostgresAgent.asyncSetUp

    async def asyncTearDown(self):
        async with unit_of_work() as session:await session.execute(delete(User).where(User.id.in_((self.uid,self.other))))
        await setup.PostgresAgent.asyncTearDown(self)

    async def state(self):
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,self.identity)
            return row.revision,store.manifest(row)

    async def command(self,handler,model,**values):
        revision,_=await self.state()
        return await handler(self.uid,self.identity,str(uuid4()),model(revision=revision,**values))

    def fact(self,value,point):return {'value':value,'state':'extracted',
        'sources':[{'page':1,'block_id':f'p0001-b{point:04d}','quote':self.lines[point-1]}]}

    async def accept(self,claim,proposal):
        await units.provider_attempt(claim,SimpleNamespace(provider='mock',name='no-network'))
        await units.complete(claim,proposal,{'total_tokens':5},progress.consolidate)

    async def checks(self):
        while claim:=await units.claim_next(kind='verify'):
            data=await units.snapshot(claim)
            await self.accept(claim,{'reviewed_unit_key':data['metadata']['reviewed_unit_key'],
                'covered_block_ids':[b['id'] for b in data['primary']],'findings':[]})

    async def fixture(self):
        self.lines=getattr(self,'custom_lines',['Cargo A: Analista.','Programa de todos os cargos: Português e redação oficial.',
            'Disposições administrativas.','Programa de todos os cargos: Informática e redes.'])
        blocks=[SourceBlock(id=f'p0001-b{i:04d}',page=1,text=t,bbox=(0,i*20,500,i*20+15)) for i,t in enumerate(self.lines,1)]
        doc=DocumentIR(sha256=hashlib.sha256('\n'.join(self.lines).encode()).hexdigest(),size_bytes=500,
            pages=[SourcePage(page=1,width=600,height=800,quality='text',characters=sum(map(len,self.lines)),blocks=blocks)])
        reserved=await store.reserve_intake(self.uid,doc.sha256,'synthetic.pdf',getattr(self,'force_reanalysis',False),str(uuid4()))
        accepted=await persist_approved(self.uid,reserved['job_id'],reserved['token'],doc);self.identity=accepted['analysis_id']
        claim=await units.claim_next()
        await self.accept(claim,{'roles':[{'name':self.fact(getattr(self,'role_name','Analista'),1)}],
            'classifications':[{'block_id':'p0001-b0001','kind':'roles'},{'block_id':'p0001-b0003','kind':'other'},*[
                {'block_id':f'p0001-b{p:04d}','kind':'program','level':'discipline',
                'title':self.fact(title,p),'scope':'all_roles','scope_sources':self.fact(title,p)['sources']}
                for p,title in ((2,'Português'),(4,'Português' if getattr(self,'cross_batch_parent',False) else 'Informática'))]]})
        await self.checks();_,state=await self.state();self.role=state.inventory.roles[0].id
        await self.command(controls.select_role,controls.SelectRole,role_id=self.role)
        claim=await units.claim_next();data=await units.snapshot(claim)
        await self.accept(claim,{'bindings':[{'section_key':v['section_key'],'decision':'include',
            'sources':self.fact('Programa',2 if v['first'].endswith('0002') else 4)['sources'],'reason':'Escopo explícito da fixture.'}
            for v in data['metadata']['sections']]})
        await self.finish_details()
        _,state=await self.state();self.assertEqual(state.status,'awaiting_review')

    async def finish_details(self):
        while claim:=await units.claim_next():
            if claim.kind=='scope':
                data=await units.snapshot(claim)
                await self.accept(claim,{'bindings':[{'section_key':v['section_key'],'decision':'include',
                    'sources':self.fact('Programa',2 if v['first'].endswith('0002') else 4)['sources'],'reason':'Associação documental conferida.'}
                    for v in data['metadata']['sections']]});continue
            if claim.kind=='verify':
                data=await units.snapshot(claim)
                await self.accept(claim,{'reviewed_unit_key':data['metadata']['reviewed_unit_key'],
                    'covered_block_ids':[b['id'] for b in data['primary']],'findings':[]});continue
            self.assertEqual(claim.kind,'detail');data=await units.snapshot(claim)
            point=2 if any(b['id'].endswith('0002') for b in data['primary']) else 4
            title,topic=('Português','redação oficial') if point==2 else ('Informática','redes')
            if point==4 and getattr(self,'cross_batch_parent',False):title,topic='Português','ortografia'
            if point==4 and getattr(self,'changed_discipline_identity',False):title='Informática e redes'
            node={'key':f'p0001-b{point:04d}-topic','title':self.fact(topic,point)}
            if point==4 and getattr(self,'cross_batch_parent',False):node['parent_key']='p0001-b0002-topic'
            await self.accept(claim,{'applicability':'shared','scope_sources':self.fact(title,point)['sources'],
                'covered_block_ids':[b['id'] for b in data['primary']],
                'disciplines':[{'name':self.fact(title,point),'topics':[node]}]})

    async def test_review_ownership_stale_writes_replay_and_confirmed_history(self):
        await self.fixture();revision,state=await self.state();disc=state.scopes[self.role].program.disciplines[0]
        body=controls.FactEdit(revision=revision,target='discipline',identity=disc.id,field='name',value='Língua Portuguesa',note='Conferido no documento original.')
        with self.assertRaises(HTTPException) as foreign:await controls.edit_fact(self.other,self.identity,str(uuid4()),body)
        self.assertEqual(foreign.exception.status_code,404)
        key=str(uuid4());first=await controls.edit_fact(self.uid,self.identity,key,body)
        replay=await controls.edit_fact(self.uid,self.identity,key,body);self.assertTrue(replay['replayed']);self.assertEqual(first['revision'],replay['revision'])
        with self.assertRaises(HTTPException) as stale:await controls.edit_fact(self.uid,self.identity,str(uuid4()),body)
        self.assertEqual(stale.exception.status_code,409)
        await self.command(controls.confirm,controls.Confirm,note='Conferi o cargo e seus conteúdos.',acknowledge_document_limits=True)
        _,state=await self.state();digest=state.scopes[self.role].confirmed_digest;self.assertEqual(len(digest),64)
        self.assertEqual(state.status,'completed')
        await self.command(controls.reopen,controls.Reviewed,note='Vou acrescentar um assunto ausente.')
        _,state=await self.state();self.assertIsNotNone(state.scopes[self.role].previous_confirmed)
        async with unit_of_work() as session:
            history=(await session.scalars(select(CommandAudit).where(CommandAudit.user_id==self.uid,CommandAudit.event=='edital.reviewed'))).all()
            confirmations=[h for h in history if h.action=='confirm_role']
            self.assertEqual(len(confirmations),1);self.assertEqual(confirmations[0].after['digest'],digest)
            self.assertEqual(confirmations[0].after['program']['disciplines'][0]['name']['value'],'Língua Portuguesa')

    async def test_structural_corrections_survive_targeted_reanalysis_without_repeating_unaffected_calls(self):
        await self.fixture();_,state=await self.state();scope=state.scopes[self.role]
        original=scope.program.disciplines[0];section=next(s for s in state.inventory.sections if s.block_id.endswith('0002'))
        await self.command(controls.edit_fact,controls.FactEdit,target='discipline',identity=original.id,field='name',
            value='Português revisado',note='Nome corrigido pelo proprietário.')
        await self.command(controls.edit_structure,controls.StructureEdit,action='add_topic',discipline_id=original.id,
            title='Ortografia',note='Conteúdo acrescido pelo proprietário.')
        before_revision,before=await self.state();reserved=before.budget.reserved_attempts
        result=await self.command(controls.reanalyze,controls.Reanalyze,section_keys=[compiler.section_key(section)],note='Reanalisar somente esta seção.')
        self.assertEqual(result['reused_completed_units'],2)
        await self.finish_details();_,after=await self.state()
        self.assertEqual(after.budget.reserved_attempts,reserved+3) # one binding, extraction and comparison
        current=next(d for d in after.scopes[self.role].program.disciplines if d.id==original.id)
        self.assertEqual(current.name.value,'Português revisado');self.assertEqual({t.title.value for t in current.topics},{'redação oficial','Ortografia'})
        self.assertEqual(len(after.scopes[self.role].program.disciplines),2)
        self.assertGreater((await self.state())[0],before_revision)

    async def test_confirmation_blocks_gaps_ambiguity_and_unresolved_findings(self):
        from edital_pipeline_contracts import VerificationFinding
        await self.fixture();_,state=await self.state();scope=state.scopes[self.role]
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,self.identity,lock=True);value=store.manifest(row)
            value.scopes[self.role].findings['missing-topic']=VerificationFinding(kind='missing_topic',severity='blocker',
                description='Confira a inclusão de conteúdo ausente.',sources=self.fact('redação',2)['sources'])
            store.write_manifest(row,value)
        with self.assertRaises(HTTPException):await self.command(controls.confirm,controls.Confirm,note='Revisei o resultado.',acknowledge_document_limits=True)
        await self.command(controls.resolve,controls.Resolve,target='scope',kind='finding',identity='missing-topic',note='Conteúdo já consta como redação oficial.')
        await self.command(controls.edit_structure,controls.StructureEdit,action='remove_topic',discipline_id=scope.program.disciplines[0].id,
            topic_id=scope.program.disciplines[0].topics[0].id,note='Remoção de assunto para conferir.')
        with self.assertRaises(HTTPException):await self.command(controls.confirm,controls.Confirm,note='Revisei o resultado.',acknowledge_document_limits=True)

    async def test_cancel_fences_running_result_and_resume_keeps_completed_checkpoints(self):
        await self.fixture();_,state=await self.state();section=next(s for s in state.inventory.sections if s.kind=='program')
        await self.command(controls.reanalyze,controls.Reanalyze,section_keys=[compiler.section_key(section)],note='Conferir a interpretação do conteúdo.')
        claim=await units.claim_next();self.assertIsNotNone(claim)
        await self.command(controls.cancel,controls.Version)
        with self.assertRaises(units.LeaseLost):await units.snapshot(claim)
        _,cancelled=await self.state();self.assertEqual(cancelled.status,'cancelled')
        await self.command(controls.resume,controls.Resume)
        _,resumed=await self.state();self.assertEqual(resumed.status,'processing')
        self.assertEqual(resumed.budget.reserved_attempts,cancelled.budget.reserved_attempts)
        await self.finish_details();_,done=await self.state();self.assertEqual(done.status,'awaiting_review')

    async def test_two_tabs_same_revision_only_one_change_commits(self):
        await self.fixture();revision,state=await self.state();disc=state.scopes[self.role].program.disciplines[0]
        bodies=[controls.FactEdit(revision=revision,target='discipline',identity=disc.id,field='name',value=v,note='Conferência explícita em aba concorrente.') for v in ('Português A','Português B')]
        outcomes=await asyncio.gather(*(controls.edit_fact(self.uid,self.identity,str(uuid4()),body) for body in bodies),return_exceptions=True)
        self.assertEqual(sum(isinstance(v,dict) for v in outcomes),1)
        self.assertEqual([v.status_code for v in outcomes if isinstance(v,HTTPException)],[409])

    async def test_role_selection_cannot_bypass_quota_pause_or_retry_time(self):
        await self.fixture();_,state=await self.state();section=next(s for s in state.inventory.sections if s.kind=='program')
        await self.command(controls.reanalyze,controls.Reanalyze,section_keys=[compiler.section_key(section)],note='Reanálise controlada da seção.')
        claim=await units.claim_next();await units.fail(claim,'quota',120)
        _,paused=await self.state();self.assertEqual(paused.scopes[self.role].status,'quota_paused')
        with self.assertRaises(HTTPException) as error:await self.command(controls.select_role,controls.SelectRole,role_id=self.role)
        self.assertEqual(error.exception.detail['code'],'explicit_resume_required')
        with self.assertRaises(HTTPException) as error:await self.command(controls.resume,controls.Resume)
        self.assertEqual(error.exception.detail['code'],'retry_not_before')

    async def test_truncated_comparison_splits_and_resumes_only_unfinished_source_windows(self):
        await self.fixture()
        # Reuse the saved inventory result but explicitly exercise a new bounded
        # comparison generation, including split-child coverage/idempotency.
        async with unit_of_work() as session:
            row=await store.owned_analysis(session,self.uid,self.identity,lock=True);state=store.manifest(row)
            verified=(await session.scalars(select(EditalUnit).where(EditalUnit.user_id==self.uid,EditalUnit.kind=='verify',EditalUnit.scope_key=='inventory'))).all()
            for unit in verified:unit.status='pending';unit.result=None;unit.finished_at=None
            state.status='processing';state.inventory.status='processing';store.write_manifest(row,state)
        claim=await units.claim_next(kind='verify');self.assertGreater(len((await units.snapshot(claim))['primary']),1)
        await units.provider_attempt(claim,SimpleNamespace(provider='mock',name='truncated-check'))
        await units.fail(claim,'output_truncated')
        children=[]
        while child:=await units.claim_next(kind='verify'):
            data=await units.snapshot(child);children.append([b['id'] for b in data['primary']])
            await self.accept(child,{'reviewed_unit_key':data['metadata']['reviewed_unit_key'],
                'covered_block_ids':children[-1],'findings':[]})
        self.assertEqual(sorted(p for child in children for p in child),[f'p0001-b{i:04d}' for i in range(1,5)])
        self.assertEqual(len(children),2);self.assertIsNone(await units.claim_next())
        _,state=await self.state();self.assertEqual(state.status,'awaiting_review')

    async def test_reanalysis_includes_later_units_whose_topic_parent_is_in_the_changed_section(self):
        self.cross_batch_parent=True
        self.custom_lines=['Cargo A: Analista.','Programa de todos os cargos: Português e redação oficial.',
            'Disposições administrativas.','Programa de todos os cargos: Português e ortografia.']
        await self.fixture();_,state=await self.state();self.assertEqual(len(state.scopes[self.role].program.disciplines),1)
        section=next(s for s in state.inventory.sections if s.block_id.endswith('0002'))
        result=await self.command(controls.reanalyze,controls.Reanalyze,section_keys=[compiler.section_key(section)],note='Conferir raiz e seus conteúdos dependentes.')
        self.assertEqual(result['reused_completed_units'],0)
        await self.finish_details();_,state=await self.state();topics=state.scopes[self.role].program.disciplines[0].topics
        self.assertEqual(len(topics),2);root=next(t for t in topics if t.title.value=='redação oficial')
        self.assertEqual(next(t for t in topics if t.title.value=='ortografia').parent_id,root.id)

    async def test_changed_model_identity_does_not_silently_discard_an_earlier_human_correction(self):
        await self.fixture();_,state=await self.state();disc=next(d for d in state.scopes[self.role].program.disciplines if d.name.value=='Informática')
        await self.command(controls.edit_fact,controls.FactEdit,target='discipline',identity=disc.id,field='name',
            value='Computação conferida',note='Nome corrigido com conferência do proprietário.')
        self.changed_discipline_identity=True
        section=next(s for s in state.inventory.sections if s.block_id.endswith('0004'))
        await self.command(controls.reanalyze,controls.Reanalyze,section_keys=[compiler.section_key(section)],note='Rever esta seção sem perder correções.')
        await self.finish_details();_,state=await self.state();scope=state.scopes[self.role]
        path=f'disciplines/{disc.id}/name';self.assertIn(path,scope.unapplied_corrections)
        self.assertEqual(scope.corrections[path].value,'Computação conferida')
        self.assertTrue(any('sem associação' in issue for issue in scope.program.issues))
        with self.assertRaises(HTTPException):await self.command(controls.confirm,controls.Confirm,note='Conferi os conteúdos.',acknowledge_document_limits=True)

    async def test_changed_model_identity_cannot_silently_reintroduce_a_removed_topic(self):
        await self.fixture();_,state=await self.state();disc=next(d for d in state.scopes[self.role].program.disciplines if d.name.value=='Informática')
        topic=disc.topics[0]
        await self.command(controls.edit_structure,controls.StructureEdit,action='remove_topic',discipline_id=disc.id,
            topic_id=topic.id,note='Assunto removido após conferência do proprietário.')
        self.changed_discipline_identity=True;section=next(s for s in state.inventory.sections if s.block_id.endswith('0004'))
        await self.command(controls.reanalyze,controls.Reanalyze,section_keys=[compiler.section_key(section)],note='Reanalisar mantendo a decisão de remoção auditável.')
        await self.finish_details();_,state=await self.state()
        self.assertIn(f'removed_topics/{topic.id}',state.scopes[self.role].unapplied_corrections)
        with self.assertRaises(HTTPException):await self.command(controls.confirm,controls.Confirm,note='Conferi os conteúdos.',acknowledge_document_limits=True)
