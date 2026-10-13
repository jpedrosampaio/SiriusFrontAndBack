"""Command Center adversarial integration tests on disposable PostgreSQL only."""
import asyncio
import csv
import io
import os
import unittest
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from uuid import uuid4, UUID
from unittest.mock import patch
from sqlalchemy import select, func
from db.session import unit_of_work
from db.models.identity import User, ActivityReceipt
from db.models.planning import Task, CalendarEvent
from db.models.agent import Memory, Conversation, Message
from db.models.command import CommandAudit
from db.models.finance import FinancialTransaction
from db.models.exams import Question
from db.models.files import FileRecord, RagSource, RagChunk, EditalAnalysis
from db.models.studies import StudyTopic, ReviewEvent, StudyPlanEntry
from services.command_center import home
from services.agent_reads import page_context
from services.time import local_today
import test_postgres_runtime_catalog as fixtures


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class CommandCenter(unittest.IsolatedAsyncioTestCase):
    ok=fixtures.RuntimeCatalog.ok
    setup_catalog=fixtures.RuntimeCatalog.setup_catalog

    async def asyncSetUp(self):
        await fixtures.RuntimeCatalog.asyncSetUp(self)
        self.today=local_today('America/Sao_Paulo');self.patches=[]
        async def account(request):return {'user_id':str(self.bob if request.headers.get('Authorization')=='Bearer bob' else self.uid),'timezone':'America/Sao_Paulo'}
        for module in ('command_routes','command_export','global_search','life_routes','study_workspace','study_activity_routes'):
            p=patch('services.'+module+'.account',account);p.start();self.patches.append(p)

    async def asyncTearDown(self):
        for p in self.patches:p.stop()
        await fixtures.RuntimeCatalog.asyncTearDown(self)

    def key(self,**extra):return {'Idempotency-Key':str(uuid4()),**extra}

    async def test_home_reuses_planner_and_preserves_fixed_constraints_and_money(self):
        now=datetime.combine(self.today,datetime.min.time(),timezone.utc)+timedelta(hours=13) # 10 local
        async with unit_of_work() as s:
            user=await s.get(User,self.uid);user.preferences={'life_availability':{'weekdays':[[{'start_minute':480,'end_minute':1200}]]*7}}
            s.add(CalendarEvent(user_id=self.uid,title='Fixed appointment',start_at=now-timedelta(minutes=10),end_at=now+timedelta(minutes=40)))
            s.add(CalendarEvent(user_id=self.bob,title='Foreign private appointment',start_at=now,end_at=now+timedelta(hours=1)))
            s.add(Task(user_id=self.uid,title='Flexible high task',date=self.today,duration_minutes=30,priority='high',xp_reward=5))
            s.add(FinancialTransaction(user_id=self.uid,type='expense',category='food',amount=Decimal('0.10'),date=self.today))
            s.add(FinancialTransaction(user_id=self.uid,type='expense',category='food',amount=Decimal('0.20'),date=self.today))
        result=await home(self.uid,now=now)
        self.assertEqual(result['next_action']['title'],'Fixed appointment')
        self.assertTrue(result['next_action']['confirmed'])
        blocks=[r for r in result['today'] if not r['confirmed']]
        self.assertTrue(blocks);self.assertTrue(all(r['start_minute']>=640 for r in blocks))
        self.assertEqual(next(a for a in result['areas'] if a['domain']=='finance')['facts']['expense'],'0.30')
        self.assertNotIn('Foreign',str(result));self.assertTrue(result['simulation_only'])
        self.assertEqual(set(result['next_action']['why']),{'evidence','constraints','limitations','source'})
        async with unit_of_work() as s:
            self.assertEqual(await s.scalar(select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id==self.uid)),1)

    async def test_empty_home_and_unauthenticated_routes_are_explicit(self):
        result=self.ok(await self.http.get('/api/command/home'))
        self.assertIsNone(result['next_action']);self.assertEqual(len(result['areas']),8)
        self.assertEqual(result['attention'],[])
        for route in ('/api/command/home','/api/command/audit','/api/command/memory','/api/command/export/finance/json'):
            # Restore real auth just for this request; no production requests.
            with patch('services.command_routes.account',__import__('services.auth_routes',fromlist=['account']).account),patch('services.command_export.account',__import__('services.auth_routes',fromlist=['account']).account):
                response=await self.http.get(route);self.assertEqual(response.status_code,401,response.text)

    async def test_search_owned_pagination_literal_terms_and_private_message_filter(self):
        async with unit_of_work() as s:
            s.add_all([Task(user_id=self.uid,title='Needle '+str(i),date=self.today,xp_reward=5) for i in range(12)])
            s.add(Task(user_id=self.bob,title='Needle foreign',date=self.today,xp_reward=5))
            convo=Conversation(user_id=self.uid,title='Title',external_id=str(uuid4()));s.add(convo);await s.flush()
            s.add(Message(user_id=self.uid,conversation_id=convo.id,sequence=1,role='user',content='Needle conversation'))
            s.add(Message(user_id=self.uid,conversation_id=convo.id,sequence=2,role='tool',content='hidden-token-tool'))
        first=self.ok(await self.http.get('/api/search/global',params={'q':'needle','domain':'tasks','limit':5}))
        cursor=first['groups'][0]['next_cursor'];self.assertTrue(cursor)
        second=self.ok(await self.http.get('/api/search/global',params={'q':'needle','domain':'tasks','cursor':cursor,'limit':5}))
        self.assertFalse({r['id'] for r in first['results']}&{r['id'] for r in second['results']})
        self.assertNotIn('foreign',str(first)+str(second))
        self.assertEqual(len(self.ok(await self.http.get('/api/search/global',params={'q':'needle','domain':'conversations'}))['results']),1)
        self.assertEqual(self.ok(await self.http.get('/api/search/global',params={'q':'hidden-token-tool'}))['results'],[])
        self.assertEqual((await self.http.get('/api/search/global',params={'q':'needle','cursor':cursor})).status_code,422)
        self.assertEqual((await self.http.get('/api/search/global',params={'q':'x'*101})).status_code,422)

    async def test_explicit_memory_provenance_idempotency_and_concurrent_correction(self):
        body={'category':'fact','content':'Eu trabalho de manhã.','scope':'calendar'};headers=self.key()
        responses=await asyncio.gather(*(self.http.post('/api/command/memory',json=body,headers=headers) for _ in range(5)))
        ids={self.ok(r)['memory_id'] for r in responses};self.assertEqual(len(ids),1)
        values=self.ok(await self.http.get('/api/command/memory'));self.assertEqual(len(values),1)
        memory=values[0];self.assertEqual(memory['provenance']['origin'],'user_declared');self.assertFalse(memory['provenance']['verified'])
        self.assertEqual(memory['scope'],'calendar')
        bodies=[{**body,'content':'Correção '+str(i),'expected_version':memory['version']} for i in range(2)]
        edited=await asyncio.gather(*(self.http.put('/api/command/memory/'+memory['memory_id'],json=b,headers=self.key()) for b in bodies))
        self.assertEqual(sorted(r.status_code for r in edited),[200,409])
        async with unit_of_work() as s:
            self.assertEqual(await s.scalar(select(func.count()).select_from(Memory).where(Memory.user_id==self.uid)),1)
            self.assertEqual(await s.scalar(select(func.count()).select_from(CommandAudit).where(CommandAudit.user_id==self.uid)),2)
            receipts=(await s.scalars(select(ActivityReceipt).where(ActivityReceipt.user_id==self.uid))).all()
            self.assertNotIn('Eu trabalho',str([r.result for r in receipts]))
        foreign=await self.http.put('/api/command/memory/'+memory['memory_id'],json=bodies[0],headers=self.key(Authorization='Bearer bob'))
        self.assertEqual(foreign.status_code,404)

    async def test_memory_remove_blocks_relearning_and_does_not_duplicate_personal_content_in_audit(self):
        body={'category':'decision','content':'Domingo reservado para descanso.'}
        created=self.ok(await self.http.post('/api/command/memory',json=body,headers=self.key()))
        memory=self.ok(await self.http.get('/api/command/memory'))[0]
        response=await self.http.delete('/api/command/memory/'+created['memory_id'],params={'version':memory['version']},headers=self.key())
        self.ok(response);self.assertEqual(self.ok(await self.http.get('/api/command/memory')),[])
        self.assertEqual((await self.http.post('/api/command/memory',json=body,headers=self.key())).status_code,409)
        audit=self.ok(await self.http.get('/api/command/audit'))
        self.assertNotIn('Domingo reservado',str(audit));self.assertTrue(all(not v['undo_available'] for v in audit['items']))
        self.assertEqual((await self.http.post('/api/command/memory',json=body)).status_code,428)

    async def availability(self,value=480):
        return self.ok(await self.http.put('/api/life/availability',json={'weekdays':[[{'start_minute':value,'end_minute':1200}]]*7},headers=self.key()))

    async def test_undo_ownership_explicit_confirmation_replay_and_availability_aba(self):
        original=await self.availability();aid=original['audit_id'];url='/api/command/audit/'+aid+'/undo'
        self.assertEqual((await self.http.post(url,json={'confirmed':True},headers=self.key(Authorization='Bearer bob'))).status_code,404)
        self.assertEqual((await self.http.post(url,json={'confirmed':False},headers=self.key())).status_code,422)
        self.assertEqual((await self.http.post(url,json={'confirmed':True})).status_code,428)
        headers=self.key();first=self.ok(await self.http.post(url,json={'confirmed':True},headers=headers))
        second=self.ok(await self.http.post(url,json={'confirmed':True},headers=headers));self.assertTrue(first['undone']);self.assertTrue(second['replayed'])
        original=await self.availability();await self.availability(600);await self.availability()
        conflict=await self.http.post('/api/command/audit/'+original['audit_id']+'/undo',json={'confirmed':True},headers=self.key())
        self.assertEqual(conflict.status_code,409)

    async def test_simulations_do_not_write_or_award_xp(self):
        await self.availability()
        async with unit_of_work() as s:
            s.add(Task(user_id=self.uid,title='Study or train task',date=self.today,duration_minutes=30,xp_reward=5))
        async with unit_of_work() as s:
            before=(await s.get(User,self.uid)).xp
            counts=[await s.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)) for model in (CalendarEvent,FinancialTransaction,CommandAudit)]
        response=self.ok(await self.http.post('/api/command/scenarios',json={'routine':{'capacity_minutes':20},'finance':{'months':3,'monthly_income':'12.34','monthly_expense':'5.01'}}))
        self.assertTrue(response['read_only']);self.assertEqual(response['routine']['plan']['blocks'],[])
        self.assertEqual(response['finance']['scenario']['months'][0]['scenario_income'],'12.34')
        async with unit_of_work() as s:
            self.assertEqual((await s.get(User,self.uid)).xp,before)
            self.assertEqual(counts,[await s.scalar(select(func.count()).select_from(model).where(model.user_id==self.uid)) for model in (CalendarEvent,FinancialTransaction,CommandAudit)])

    async def accept_plan(self):
        await self.availability()
        day=self.today+timedelta(days=1)
        async with unit_of_work() as s:s.add(Task(user_id=self.uid,title='Future flexible',date=day,duration_minutes=30,xp_reward=5))
        simulated=self.ok(await self.http.post('/api/life/simulate',json={'date':str(day)}));self.assertTrue(simulated['plan']['blocks'])
        return self.ok(await self.http.post('/api/life/accept',json={'scenario':simulated['plan']['scenario'],
            'fingerprint':simulated['state']['fingerprint'],'blocks':simulated['plan']['blocks'],'confirmed':True},headers=self.key()))

    async def test_allocation_undo_is_atomic_and_preserves_fixed_events_and_source_records(self):
        accepted=await self.accept_plan()
        async with unit_of_work() as s:
            fixed=CalendarEvent(user_id=self.uid,title='Future fixed',start_at=datetime.now(timezone.utc)+timedelta(days=2),end_at=datetime.now(timezone.utc)+timedelta(days=2,hours=1));s.add(fixed)
        url='/api/command/audit/'+accepted['audit_id']+'/undo'
        responses=await asyncio.gather(*(self.http.post(url,json={'confirmed':True},headers=self.key()) for _ in range(3)))
        for r in responses:self.ok(r)
        async with unit_of_work() as s:
            self.assertEqual(await s.scalar(select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id==self.uid)),1)
            self.assertEqual(await s.scalar(select(func.count()).select_from(Task).where(Task.user_id==self.uid)),1)
            self.assertEqual(await s.scalar(select(func.count()).select_from(CommandAudit).where(CommandAudit.user_id==self.uid,CommandAudit.event=='command.undo')),1)

    async def test_undo_rejects_concurrent_changed_or_started_allocation(self):
        accepted=await self.accept_plan()
        async with unit_of_work() as s:
            row=await s.get(CalendarEvent,UUID(accepted['event_ids'][0]));row.title='Changed concurrently'
        response=await self.http.post('/api/command/audit/'+accepted['audit_id']+'/undo',json={'confirmed':True},headers=self.key())
        self.assertEqual(response.status_code,409)
        async with unit_of_work() as s:
            row=await s.get(CalendarEvent,UUID(accepted['event_ids'][0]));self.assertEqual(row.title,'Changed concurrently')

    async def test_undo_rejects_started_or_changed_then_restored_allocation(self):
        accepted=await self.accept_plan();url='/api/command/audit/'+accepted['audit_id']+'/undo'
        with patch('services.command_audit.datetime',wraps=datetime) as clock:
            clock.now.return_value=datetime.now(timezone.utc)+timedelta(days=3)
            self.assertEqual((await self.http.post(url,json={'confirmed':True},headers=self.key())).status_code,409)
        async with unit_of_work() as s:
            row=await s.get(CalendarEvent,UUID(accepted['event_ids'][0]));original=row.title;row.title='Temporary edit'
        async with unit_of_work() as s:
            row=await s.get(CalendarEvent,UUID(accepted['event_ids'][0]));row.title=original
        self.assertEqual((await self.http.post(url,json={'confirmed':True},headers=self.key())).status_code,409)

    async def test_audit_pagination_and_cursor_ownership(self):
        for value in (480,500,520):await self.availability(value)
        first=self.ok(await self.http.get('/api/command/audit',params={'limit':2}));self.assertEqual(len(first['items']),2)
        second=self.ok(await self.http.get('/api/command/audit',params={'limit':2,'cursor':first['next_cursor']}))
        self.assertFalse({r['id'] for r in first['items']}&{r['id'] for r in second['items']})
        foreign=await self.http.get('/api/command/audit',params={'cursor':first['next_cursor']},headers={'Authorization':'Bearer bob'})
        self.assertEqual(foreign.status_code,422)

    async def test_export_is_owned_paginated_exact_and_csv_formula_safe(self):
        async with unit_of_work() as s:
            s.add_all([FinancialTransaction(user_id=self.uid,type='expense',category='test',description='=HYPERLINK("bad")',amount=Decimal('1.01'),date=self.today) for _ in range(3)])
            s.add(FinancialTransaction(user_id=self.bob,type='expense',category='private',description='Foreign',amount=Decimal('999.99'),date=self.today))
        first=self.ok(await self.http.get('/api/command/export/finance/json',params={'limit':2}))
        self.assertEqual(len(first['records']),2);self.assertEqual(first['records'][0]['amount'],'1.01')
        second=self.ok(await self.http.get('/api/command/export/finance/json',params={'limit':2,'cursor':first['next_cursor']}))
        self.assertEqual(len(second['records']),1);self.assertNotIn('Foreign',str(first)+str(second))
        response=await self.http.get('/api/command/export/finance/csv',headers={'Origin':'https://sirius.test'});self.assertEqual(response.status_code,200,response.text)
        csv_rows=list(csv.DictReader(io.StringIO(response.text.lstrip('\ufeff'))));self.assertTrue(csv_rows[0]['description'].startswith("'="))
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertIn('X-Export-Next-Cursor',response.headers['access-control-expose-headers'])
        pdf=await self.http.get('/api/command/export/daily-report.pdf');self.assertEqual(pdf.status_code,200,pdf.text[:80] if pdf.status_code!=200 else '')
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertEqual((await self.http.get('/api/command/export/credentials/json')).status_code,422)

    async def test_export_oversized_next_record_remains_on_next_page_without_truncation(self):
        async with unit_of_work() as s:
            convo=Conversation(user_id=self.uid,title='Export sizing',external_id=str(uuid4()));s.add(convo);await s.flush()
            s.add(Message(id=UUID(int=1),user_id=self.uid,conversation_id=convo.id,sequence=1,role='user',content='Small first record'))
            s.add(Message(id=UUID(int=2),user_id=self.uid,conversation_id=convo.id,sequence=2,role='assistant',content='x'*2_000_001))
        first=self.ok(await self.http.get('/api/command/export/messages/json',params={'limit':1}))
        self.assertEqual(first['records'][0]['content'],'Small first record')
        self.assertEqual(first['next_cursor'],str(UUID(int=1)))
        next_page=await self.http.get('/api/command/export/messages/json',params={'limit':1,'cursor':first['next_cursor']})
        self.assertEqual(next_page.status_code,413)
        async with unit_of_work() as s:
            self.assertEqual(len((await s.get(Message,UUID(int=2))).content),2_000_001)

    async def test_context_ignores_client_facts_and_verifies_every_selected_owner(self):
        async with unit_of_work() as s:
            question=Question(user_id=self.uid,statement='Owned question',question_type='multiple_choice',source='manual');s.add(question)
            tx=FinancialTransaction(user_id=self.bob,type='expense',category='private',amount=Decimal('9999.99'),date=self.today);s.add(tx)
            material=FileRecord(user_id=self.uid,filename='Document.pdf',storage_provider='metadata_only',mime_type='application/pdf',size_bytes=10,sha256='a'*64);s.add(material);await s.flush()
            qid=str(question.id);tid=str(tx.id);fid=str(material.id)
        value=await page_context(self.uid,{'question_id':qid,'transaction_id':tid,'attachment_id':fid,
            'title':'Invented','facts':{'balance':999999},'intent':'explain'})
        self.assertEqual(value['question']['title'],'Owned question');self.assertEqual(value['intent'],'explain')
        self.assertNotIn('transaction',value);self.assertNotIn('Invented',str(value));self.assertNotIn('facts',value)
        foreign=await page_context(self.bob,{'question_id':qid,'attachment_id':fid});self.assertEqual(foreign,{})

    async def test_document_search_reuses_owned_index_and_never_returns_storage_or_chunk_data(self):
        async with unit_of_work() as s:
            for uid,letter in ((self.uid,'c'),(self.bob,'d')):
                file=FileRecord(user_id=uid,filename='Neutral.pdf',storage_provider='metadata_only',mime_type='application/pdf',size_bytes=100,sha256=letter*64);s.add(file);await s.flush()
                source=RagSource(user_id=uid,file_id=file.id,source_type='attachment',generation=letter);s.add(source);await s.flush()
                s.add(RagChunk(user_id=uid,source_id=source.id,chunk_index=0,content='Needle indexed confidential body',content_hash=letter*64,terms=['needle','indexed','confidential','body']))
        result=self.ok(await self.http.get('/api/search/global',params={'q':'needle','domain':'materials'}))
        self.assertEqual(len(result['results']),1);self.assertEqual(result['results'][0]['title'],'Neutral.pdf')
        self.assertNotIn('confidential body',str(result));self.assertNotIn('storage_key',str(result))

    async def test_latest_topic_review_resolves_debt_and_foreign_review_is_not_counted(self):
        _,_,book=await self.setup_catalog()
        async with unit_of_work() as s:
            topic=StudyTopic(user_id=self.uid,notebook_id=UUID(book['notebook_id']),topic_key='0',name='Debt topic',position=0);s.add(topic);await s.flush()
            s.add(ReviewEvent(user_id=self.uid,topic_id=topic.id,reviewed_at=datetime.now(timezone.utc)-timedelta(days=2),next_review=self.today-timedelta(days=1),result='practice'))
            tid=topic.id
        debt=self.ok(await self.http.get('/api/command/home'));self.assertTrue(any(r['id']=='overdue-topic-reviews' for r in debt['attention']))
        async with unit_of_work() as s:s.add(ReviewEvent(user_id=self.uid,topic_id=tid,reviewed_at=datetime.now(timezone.utc),next_review=self.today+timedelta(days=7),result='practice'))
        result=self.ok(await self.http.get('/api/command/home'));self.assertFalse(any(r['id']=='overdue-topic-reviews' for r in result['attention']))
        self.assertEqual(self.ok(await self.http.get('/api/command/home',headers={'Authorization':'Bearer bob'}))['attention'],[])

    async def test_audit_failure_rolls_back_domain_write_and_receipt(self):
        before=await self.availability()
        async with unit_of_work() as s:
            previous=dict((await s.get(User,self.uid)).preferences)
            count=await s.scalar(select(func.count()).select_from(ActivityReceipt).where(ActivityReceipt.user_id==self.uid))
        with patch('services.life_routes.record',side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):await self.availability(600)
        async with unit_of_work() as s:
            self.assertEqual((await s.get(User,self.uid)).preferences,previous)
            self.assertEqual(await s.scalar(select(func.count()).select_from(ActivityReceipt).where(ActivityReceipt.user_id==self.uid)),count)
            self.assertIsNotNone(await s.get(CommandAudit,UUID(before['audit_id'])))

    async def test_study_replan_and_entry_changes_have_atomic_explanations_without_duplicate_history(self):
        _,program,book=await self.setup_catalog();pid=program['program_id']
        body={'start_date':str(self.today),'end_date':str(self.today+timedelta(days=7)),'availability':[60]*7,'block_minutes':30}
        headers=self.key();result=self.ok(await self.http.post(f'/api/study/programs/{pid}/dated-plan',json=body,headers=headers))
        self.ok(await self.http.post(f'/api/study/programs/{pid}/dated-plan',json=body,headers=headers))
        async with unit_of_work() as s:
            self.assertEqual(await s.scalar(select(func.count()).select_from(CommandAudit).where(CommandAudit.user_id==self.uid,CommandAudit.event=='preparation.plan.updated')),1)
            entry=await s.scalar(select(StudyPlanEntry).where(StudyPlanEntry.user_id==self.uid).order_by(StudyPlanEntry.date,StudyPlanEntry.id).limit(1));eid=str(entry.id)
        self.ok(await self.http.patch(f'/api/study/programs/{pid}/dated-plan/{eid}',json={'completed':True},headers=self.key()))
        audit=self.ok(await self.http.get('/api/command/audit'));events={r['event'] for r in audit['items']}
        self.assertIn('preparation.plan.updated',events);self.assertIn('preparation.entry.updated',events)
        self.assertTrue(all(not r['undo_available'] for r in audit['items']))
        self.assertTrue(any(r['changes'] for r in audit['items']))
