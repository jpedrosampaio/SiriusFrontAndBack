import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from uuid import UUID
from sqlalchemy import select,func
from db.models.exams import Question,Exam
from db.models.studies import QuestionAttempt,ReviewEvent,StudyTopic
from datetime import datetime,timezone,timedelta
from db.models.question_insights import QuestionInsight
from db.models.agent import Usage
from db.models.identity import ActivityReceipt
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work
import test_postgres_runtime_studies_v2 as fixture


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class QuestionIntelligence(unittest.IsolatedAsyncioTestCase):
    ok=fixture.RuntimeStudiesV2.ok
    setup_catalog=fixture.RuntimeStudiesV2.setup_catalog

    async def asyncSetUp(self):
        await fixture.RuntimeStudiesV2.asyncSetUp(self)
        async def auth(authorization=None,**kwargs):return SimpleNamespace(user_id=str(self.bob if authorization=='Bearer bob' else self.uid))
        self.generator=AsyncMock()
        self.extra=[patch('services.exam_generation_routes.get_current_user',auth),
            patch('services.exam_generation_routes.get_user_api_key',AsyncMock(return_value='mock-only')),
            patch('services.exam_generation_routes.request_gemini',self.generator)]
        for item in self.extra:item.start()
        self.base='/api/study/v2/programs/'+self.pid+'/question-intelligence'

    async def asyncTearDown(self):
        for item in reversed(self.extra):item.stop()
        await fixture.RuntimeStudiesV2.asyncTearDown(self)

    async def attempt(self,index,**extra):
        body={'notebook_id':self.nid,'topic_key':'0','question':'Crase conceito '+str(index),
            'correct':False,'error_reason':'knowledge_gap',**extra}
        return self.ok(await self.http.post('/api/study/v2/attempts',json=body,headers={'Idempotency-Key':'question-'+str(index)}))

    async def test_confidence_skips_identity_recovery_and_foreign_owner(self):
        skipped=await self.attempt(1,skipped=True,confidence='guess',changed_answer=True)
        self.assertIsNone(skipped['review']);self.assertTrue(skipped['skipped'])
        self.assertEqual(self.ok(await self.http.get('/api/study/v2/performance'))['summary']['samples'],0)
        stats=self.ok(await self.http.get('/api/study/questions/stats'))
        self.assertEqual((stats['total_questions'],stats['incorrect']),(0,0))
        book=next(r for r in self.ok(await self.http.get('/api/study/notebooks')) if r['notebook_id']==self.nid)
        self.assertEqual((book['total_questions'],book['correct_questions']),(0,0))
        overview=self.ok(await self.http.get('/api/study/v2/programs/'+self.pid+'/overview'))
        self.assertEqual(overview['questions'],0);self.assertIsNone(overview['accuracy'])
        from db.repositories.studies import StudiesRepository
        from services.study_activity_routes import streak_summary
        async with unit_of_work() as session:
            facts=await StudiesRepository(session).program_facts(self.uid,UUID(self.pid))
            self.assertEqual(facts['total_questions'],0)
            self.assertEqual((await streak_summary(session,self.uid,'America/Sao_Paulo'))['total_study_days'],0)
        wrong=await self.attempt(2,confidence='uncertain',source='official')
        self.assertEqual(wrong['question_provenance'],'user_created')
        self.assertEqual(wrong['confidence'],'uncertain')
        correct=await self.attempt(3,question=wrong['question'],internal_question_id=wrong['internal_question_id'],correct=True)
        self.assertEqual(correct['internal_question_id'],wrong['internal_question_id'])
        bank=self.ok(await self.http.get(self.base))['error_bank']
        self.assertEqual(bank['question_count'],1);self.assertEqual(bank['recovery_rate'],100)
        await self.attempt(4,skipped=True,internal_question_id=wrong['internal_question_id'])
        from services.agent_reads import read
        agent_rows=await read('get_wrong_questions',str(self.uid))
        self.assertEqual((agent_rows[0]['total'],agent_rows[0]['correct'],agent_rows[0]['accuracy']),(1,1,100))
        response=await self.http.post('/api/study/v2/attempts',json={'notebook_id':self.nid,'topic_key':'0',
            'question':'Reference','correct':True,'internal_question_id':wrong['internal_question_id']},
            headers={'Authorization':'Bearer bob','Idempotency-Key':'foreign-key'})
        self.assertEqual(response.status_code,404)
        self.assertEqual((await self.http.get(self.base,headers={'Authorization':'Bearer bob'})).status_code,404)

    async def test_persistent_suggestion_receipt_dismissal_and_facts_unchanged(self):
        attempts=[await self.attempt(i) for i in (1,2,3)]
        responses=await asyncio.gather(*(self.http.post(self.base+'/analyze',headers={'Idempotency-Key':'analyze-once'}) for _ in range(5)))
        results=[self.ok(r) for r in responses];self.assertTrue(all(not r['facts_changed'] for r in results))
        insight=results[0]['suggestions'][0];self.assertEqual(insight['question_count'],3)
        self.assertEqual(len({r['suggestions'][0]['insight_id'] for r in results}),1)
        self.assertEqual(set(insight['attempt_ids']),{r['attempt_id'] for r in attempts})
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionInsight).where(QuestionInsight.user_id==self.uid)),1)
            self.assertEqual(await session.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.user_id==self.uid)),3)
        url=self.base+'/'+insight['insight_id']
        self.assertEqual((await self.http.patch(url,json={'status':'dismissed'},headers={'Authorization':'Bearer bob','Idempotency-Key':'foreign-key'})).status_code,404)
        self.ok(await self.http.patch(url,json={'status':'dismissed'},headers={'Idempotency-Key':'dismiss-key'}))
        self.ok(await self.http.post(self.base+'/analyze',headers={'Idempotency-Key':'analyze-again'}))
        self.assertEqual(self.ok(await self.http.get(self.base))['suggestions'],[])

    async def test_lab_two_mocked_calls_discards_low_confidence_and_keeps_provenance(self):
        questions=[{'question_number':i,'question_text':'Crase: '+str(i),'options':['A) First','B) Second'],'correct_answer':'First','explanation':'Justification'} for i in (1,2)]
        async def provider(**kwargs):
            # Real providers read credentials/write usage using separate units of work.
            async with unit_of_work() as session:
                await IdentityRepository(session).by_id(self.uid,lock=True)
                session.add(Usage(user_id=self.uid,provider='mock',model='mock',task=kwargs['task'],status='ok',duration_ms=0))
            await asyncio.sleep(.05)
            payload={'questions':questions} if kwargs['task']=='study_question_generation' else {'validation':[
                {'index':0,'acceptable':True,'confidence':'low'},{'index':1,'acceptable':True,'confidence':'high'}]}
            return SimpleNamespace(text=json.dumps(payload))
        self.generator.side_effect=provider
        self.extra[1].new.return_value=None  # A text laboratory also supports Groq-only configured accounts.
        body={'title':'Lab','notebook_id':self.nid,'topic_key':'0','num_questions':2,'laboratory':True}
        concurrent=await asyncio.gather(*(self.http.post('/api/study/simulados/generate',json=body,headers={'Idempotency-Key':'laboratory-key'}) for _ in range(5)))
        self.assertTrue(all(r.status_code in (200,409) for r in concurrent))
        responses=[self.ok(r) for r in concurrent if r.status_code==200];response=responses[0]
        self.assertEqual(len({r['simulado']['simulado_id'] for r in responses}),1)
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'name':'Renamed'}))
        replayed=self.ok(await self.http.post('/api/study/simulados/generate',json={'title':'Lab','notebook_id':self.nid,
            'topic_key':'0','num_questions':2,'laboratory':True},headers={'Idempotency-Key':'laboratory-key'}))
        self.assertTrue(replayed['replayed'])
        self.assertEqual(replayed['simulado']['simulado_id'],response['simulado']['simulado_id'])
        self.assertEqual(self.generator.await_count,2)
        self.extra[1].new.assert_not_awaited()
        saved=response['simulado']['questions'];self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]['correct_answer'],'A')
        self.assertEqual(saved[0]['question_number'],1);self.assertEqual(saved[0]['question_text'],'Crase: 2')
        from services.exams import submit_exam
        graded=await submit_exam(self.uid,UUID(response['simulado']['simulado_id']),[{'question_idx':0,'selected_answer':'A'}],10,'lab-text-answer')
        self.assertEqual(graded['score'],100)
        self.assertTrue(saved[0]['generated_by_ai']);self.assertEqual(saved[0]['origin'],'ai_generated')
        self.assertEqual(saved[0]['validation_level'],'separate_ai_and_structural')
        self.assertEqual(saved[0]['source_context']['source_type'],'syllabus')
        self.assertEqual(self.generator.await_args_list[1].kwargs['task'],'study_question_validation')
        self.ok(await self.http.delete('/api/study/notebooks/'+self.nid))
        archived_replay=self.ok(await self.http.post('/api/study/simulados/generate',json=body,headers={'Idempotency-Key':'laboratory-key'}))
        self.assertTrue(archived_replay['replayed']);self.assertEqual(self.generator.await_count,2)
        refused=await self.http.post('/api/study/simulados/generate',json=body,headers={'Idempotency-Key':'new-archived-generation'})
        self.assertEqual(refused.status_code,404);self.assertEqual(self.generator.await_count,2)

    async def test_labeled_true_false_lab_grades_ui_letter_correctly(self):
        question={'question_text':'Crase statement','type':'certo_errado','options':['A) Certo','B) Errado'],
            'correct_answer':'Certo','explanation':'Reason'}
        self.generator.side_effect=[SimpleNamespace(text=json.dumps({'questions':[question]})),
            SimpleNamespace(text=json.dumps({'validation':[{'index':0,'acceptable':True,'confidence':'high'}]}))]
        response=self.ok(await self.http.post('/api/study/simulados/generate',json={'title':'True false lab',
            'notebook_id':self.nid,'topic_key':'0','num_questions':1,'laboratory':True},
            headers={'Idempotency-Key':'labeled-true-false'}))
        self.assertEqual(response['simulado']['questions'][0]['correct_answer'],'A')
        from services.exams import submit_exam
        graded=await submit_exam(self.uid,UUID(response['simulado']['simulado_id']),
            [{'question_idx':0,'selected_answer':'A'}],10,'lab-true-false-answer')
        self.assertEqual(graded['score'],100)

    async def test_lab_missing_context_and_malformed_validation_do_not_save(self):
        body={'title':'Lab','notebook_id':self.nid,'topic_key':'0','num_questions':1,'laboratory':True,'context_source':'materials'}
        self.assertEqual((await self.http.post('/api/study/simulados/generate',json=body,headers={'Idempotency-Key':'missing-context'})).status_code,422)
        self.generator.assert_not_awaited()
        question={'question_text':'Crase','options':['A) First','B) Second'],'correct_answer':'A','explanation':'Reason'}
        self.generator.side_effect=[SimpleNamespace(text=json.dumps({'questions':[question]})),SimpleNamespace(text='{"validation":[]}')]
        response=await self.http.post('/api/study/simulados/generate',json={**body,'context_source':'syllabus'},headers={'Idempotency-Key':'malformed-validation'})
        self.assertEqual(response.status_code,502)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Exam).where(Exam.user_id==self.uid)),0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(ActivityReceipt).where(
                ActivityReceipt.user_id==self.uid,ActivityReceipt.request_key=='malformed-validation')),0)

    async def test_expired_reservation_fences_old_worker_and_preserves_new_result(self):
        from services.question_generation import generate_once,LEASE_KEY
        from fastapi import HTTPException
        started,release=asyncio.Event(),asyncio.Event()
        document={'title':'Reserved','notebook_id':self.nid,'source_type':'ai_generated'}
        questions=[{'question_text':'Crase','correct_answer':'A','options':['A','B']}]
        async def old_worker():
            started.set();await release.wait();return document,questions
        async def new_worker():return document,questions
        first=asyncio.create_task(generate_once(str(self.uid),'expired-reservation',['reserved'],old_worker))
        await asyncio.wait_for(started.wait(),5)
        try:
            async with unit_of_work() as session:
                await IdentityRepository(session).by_id(self.uid,lock=True)
                receipt=await session.scalar(select(ActivityReceipt).where(ActivityReceipt.user_id==self.uid,
                    ActivityReceipt.request_key=='expired-reservation'))
                receipt.result={LEASE_KEY:{**receipt.result[LEASE_KEY],'until':'2020-01-01T00:00:00+00:00'}}
            completed=await generate_once(str(self.uid),'expired-reservation',['reserved'],new_worker)
            release.set()
            with self.assertRaises(HTTPException) as failure:await first
            self.assertEqual(failure.exception.status_code,409)
            replayed=await generate_once(str(self.uid),'expired-reservation',['reserved'],new_worker)
            self.assertTrue(replayed['replayed']);self.assertEqual(replayed['simulado']['simulado_id'],completed['simulado']['simulado_id'])
            async with unit_of_work() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(Exam).where(Exam.user_id==self.uid)),1)
        finally:
            release.set()
            if not first.done():first.cancel()
            await asyncio.gather(first,return_exceptions=True)

    async def test_error_context_limits_inside_selected_topic(self):
        wrong=await self.attempt(1)
        self.ok(await self.http.patch('/api/study/notebooks/'+self.nid,json={'conteudo_programatico':[
            {'assunto':'Crase','subtopicos':[]},{'assunto':'Other','subtopicos':[]}]}))
        async with unit_of_work() as session:
            topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==self.uid,
                StudyTopic.notebook_id==UUID(self.nid),StudyTopic.topic_key=='1',StudyTopic.archived_at.is_(None)))
            question=Question(user_id=self.uid,notebook_id=UUID(self.nid),topic_id=topic.id,statement='Other',source='manual',question_type='manual')
            session.add(question);await session.flush();now=datetime.now(timezone.utc)
            session.add_all([QuestionAttempt(user_id=self.uid,notebook_id=UUID(self.nid),topic_id=topic.id,
                question_id=question.id,source='manual',answered_at=now+timedelta(seconds=i),total=1,correct=1,
                evidence={'answered':True}) for i in range(501)])
        from services.question_lab import context
        result=await context(str(self.uid),self.nid,'0','errors')
        self.assertEqual(result['source_ids'],[wrong['attempt_id']])
