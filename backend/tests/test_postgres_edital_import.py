"""Confirmed import uses the existing catalog, real SQL and no provider calls."""
import asyncio
import os
import unittest
from uuid import uuid4,UUID
from datetime import date
from fastapi import HTTPException
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import StudyArea,StudyProgram,StudyTarget,Notebook,StudyTopic,StudySchedule
from db.models.identity import User
from services import edital_pipeline_import as imports,edital_pipeline_controls as controls,edital_analyses
from services.studies_catalog import public
from services.preparation_state import preparation_state
import test_postgres_edital_controls as review_setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class ConfirmedImport(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=review_setup.HumanControls.asyncSetUp
    asyncTearDown=review_setup.HumanControls.asyncTearDown
    fixture=review_setup.HumanControls.fixture
    state=review_setup.HumanControls.state
    command=review_setup.HumanControls.command
    fact=review_setup.HumanControls.fact
    accept=review_setup.HumanControls.accept
    checks=review_setup.HumanControls.checks
    finish_details=review_setup.HumanControls.finish_details

    async def payload(self):
        async with unit_of_work() as session:
            area=StudyArea(user_id=self.uid,name='Concursos');session.add(area);await session.flush();self.area=area.id
        revision,state=await self.state()
        return imports.Import(revision=revision,role_id=self.role,confirmed_digest=state.scopes[self.role].confirmed_digest,
            area_id=self.area,target_date=date(2027,3,1))

    async def test_unconfirmed_import_is_blocked_even_with_forged_digest(self):
        await self.fixture()
        body=imports.Import(revision=(await self.state())[0],role_id=self.role,confirmed_digest='a'*64,area_id=uuid4())
        with self.assertRaises(HTTPException) as error:await imports.create(self.uid,self.identity,str(uuid4()),body)
        self.assertEqual(error.exception.detail['code'],'human_confirmation_required')
        async with unit_of_work() as session:self.assertEqual(await session.scalar(select(func.count()).select_from(StudyProgram).where(StudyProgram.user_id==self.uid)),0)

    async def test_concurrent_imports_same_content_do_not_duplicate_program_xp_or_schedule(self):
        await self.fixture()
        await self.command(controls.confirm,controls.Confirm,note='Conferi o edital e as limitações.',acknowledge_document_limits=True)
        body=await self.payload();key=str(uuid4())
        results=await asyncio.gather(*(imports.create(self.uid,self.identity,key if i<3 else str(uuid4()),body) for i in range(8)))
        self.assertEqual(len({r['program']['program_id'] for r in results}),1)
        # Receipt replays can return the original award; only actual SQL XP counts.
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyProgram).where(StudyProgram.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudySchedule).where(StudySchedule.user_id==self.uid)),0)
            user=await session.get(User,self.uid);self.assertEqual(user.xp,25)
            program=await session.scalar(select(StudyProgram).where(StudyProgram.user_id==self.uid))
            target=await session.scalar(select(StudyTarget).where(StudyTarget.user_id==self.uid))
            self.assertEqual(program.target_date,date(2027,3,1));self.assertIsNone(target.exam_date)
            books=(await session.scalars(select(Notebook).where(Notebook.user_id==self.uid))).all()
            self.assertEqual(len(books),2)
            for book in books:
                self.assertEqual(book.peso_status,'ausente');self.assertIsNone(public(book)['weight'])
                self.assertIsNone(book.num_questoes_edital)
                topics=(await session.scalars(select(StudyTopic).where(StudyTopic.user_id==self.uid,StudyTopic.notebook_id==book.id))).all()
                self.assertTrue(all(t.evidence.get('canonical_id') for t in topics))
            view=await preparation_state(session,self.uid,program,'America/Sao_Paulo',date(2026,10,16))
            self.assertIsNone(view['exam_date']);self.assertIsNone(view['days_remaining'])
            self.assertTrue(all(d['weight'] is None and d['question_count'] is None for d in view['syllabus_graph']['disciplines']))
        with self.assertRaises(HTTPException) as foreign:await imports.create(self.other,self.identity,str(uuid4()),body)
        self.assertEqual(foreign.exception.status_code,404)

    async def test_hierarchy_and_new_versions_preserve_prior_program_without_extra_xp(self):
        await self.fixture();_,state=await self.state();disc=state.scopes[self.role].program.disciplines[0]
        await self.command(controls.edit_structure,controls.StructureEdit,action='add_topic',discipline_id=disc.id,
            parent_id=disc.topics[0].id,title='Subtópico específico',note='Subtópico incluído manualmente.')
        _,state=await self.state();child=next(t for t in state.scopes[self.role].program.disciplines[0].topics if t.parent_id)
        await self.command(controls.edit_structure,controls.StructureEdit,action='add_topic',discipline_id=disc.id,
            parent_id=child.id,title='Terceiro nível',note='Detalhe conferido no documento.')
        await self.command(controls.confirm,controls.Confirm,note='Conferi os assuntos e a hierarquia.',acknowledge_document_limits=True)
        body=await self.payload();first=await imports.create(self.uid,self.identity,str(uuid4()),body)
        async with unit_of_work() as session:
            topics=(await session.scalars(select(StudyTopic).where(StudyTopic.user_id==self.uid))).all();by_name={t.name:t for t in topics}
            self.assertEqual(by_name['Terceiro nível'].parent_id,by_name['Subtópico específico'].id)
            self.assertEqual(by_name['Subtópico específico'].parent_id,by_name['redação oficial'].id)
            self.assertRegex(by_name['Terceiro nível'].topic_key,r'^\d+_\d+$')
        await self.command(controls.reopen,controls.Reviewed,note='Vou corrigir um nome neste cargo.')
        await self.command(controls.edit_fact,controls.FactEdit,target='discipline',identity=disc.id,field='name',value='Português corrigido',note='Nome conferido novamente.')
        await self.command(controls.confirm,controls.Confirm,note='Confirmei a revisão corrigida.',acknowledge_document_limits=True)
        revision,state=await self.state();new=body.model_copy(update={'revision':revision,'confirmed_digest':state.scopes[self.role].confirmed_digest})
        with self.assertRaises(HTTPException) as error:await imports.create(self.uid,self.identity,str(uuid4()),new)
        self.assertEqual(error.exception.detail['code'],'explicit_new_version_required')
        second=await imports.create(self.uid,self.identity,str(uuid4()),new.model_copy(update={'create_new_version':True}))
        self.assertNotEqual(first['program']['program_id'],second['program']['program_id']);self.assertEqual(second['xp_earned'],0)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(StudyProgram).where(StudyProgram.user_id==self.uid)),2)
            self.assertEqual((await session.get(User,self.uid)).xp,25)
            old=await session.get(StudyProgram,UUID(first['program']['program_id']))
            self.assertNotEqual(old.edital_data['universal_edital']['confirmed_digest'],new.confirmed_digest)

    async def test_summary_list_includes_partial_analyses_and_preserves_versions(self):
        await self.fixture();result=await edital_analyses.list_owned(self.uid)
        item=next(r for r in result['editais'] if r['analysis_id']==self.identity)
        self.assertEqual(item['pipeline_status'],'awaiting_review');self.assertEqual(item['num_cargos'],1)
        self.assertEqual(item['cargos_names'],['Analista']);self.assertNotIn('universal',item)
        self.assertEqual((await edital_analyses.list_owned(self.other))['editais'],[])

    async def test_group_rules_never_turn_into_per_discipline_weights_or_counts(self):
        await self.fixture();_,state=await self.state();disc=state.scopes[self.role].program.disciplines[0]
        for kind,value in (('weight','2'),('question_count','40')):
            await self.command(controls.change_rule,controls.RuleChange,action='add',target_scope='group',kind=kind,
                target='Conhecimentos comuns',value=value,note='Regra declarada para o grupo inteiro.')
        await self.command(controls.change_rule,controls.RuleChange,action='add',target_scope='discipline',kind='weight',
            target=disc.name.value,value='3',note='Peso desta disciplina conferido pelo proprietário.')
        await self.command(controls.confirm,controls.Confirm,note='Conferi as regras e seus destinos.',acknowledge_document_limits=True)
        body=await self.payload();result=await imports.create(self.uid,self.identity,str(uuid4()),body)
        async with unit_of_work() as session:
            books=(await session.scalars(select(Notebook).where(Notebook.user_id==self.uid))).all()
            known=next(b for b in books if b.name==disc.name.value);unknown=next(b for b in books if b.name!=disc.name.value)
            self.assertEqual(known.weight,3);self.assertEqual(known.peso_status,'informado_pelo_usuario')
            self.assertIsNone(public(unknown)['weight']);self.assertIsNone(known.num_questoes_edital);self.assertIsNone(unknown.num_questoes_edital)
            program=await session.get(StudyProgram,UUID(result['program']['program_id']))
            self.assertEqual(len(program.edital_data['universal_edital']['rules']),3)

    async def test_agent_receives_partial_status_and_owned_text_remains_retrievable(self):
        from services.retrieval import Retrieval
        from services.agent_reads import page_context
        await self.fixture();retrieval=Retrieval();result=await retrieval.index_edital(self.uid,self.identity)
        self.assertFalse(result.get('truncated'))
        own=await retrieval.search(self.uid,'redação',self.identity);self.assertTrue(own['citations'])
        self.assertIn('redação',own['citations'][0]['text']);self.assertEqual(own['citations'][0]['page'],1)
        self.assertEqual((await retrieval.search(self.other,'redação',self.identity))['citations'],[])
        context=await page_context(self.uid,{'analysis_id':self.identity})
        self.assertEqual(context['analysis']['analysis_status'],'awaiting_review')
        self.assertEqual(context['analysis']['selected_role_status'],'awaiting_review')
        self.assertIsNone(context['analysis']['confirmed_digest']);self.assertIn('não confirmadas',context['analysis']['limitation'])
        self.assertNotIn('analysis',await page_context(self.other,{'analysis_id':self.identity}))
