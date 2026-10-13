"""Cross-engine journeys through real authentication and disposable PostgreSQL.

No account mocks: independent hashed sessions prove server-side owner isolation.
External extraction/generation/delivery are synthetic and explicitly mocked.
"""
import asyncio
import hashlib
import json
import os
import sys
import unittest
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from db.engine import dispose_engine
from db.session import unit_of_work
from db.repositories.identity import IdentityRepository
from db.models.identity import User
from db.models.studies import StudySession, StudyTopic, QuestionAttempt, ReviewEvent, StudyPlan, StudyPlanEntry
from db.models.planning import Task, TaskInstance, CalendarEvent
from db.models.agent import EventDelivery
from db.models.telegram import TelegramLink
from db.models.health import WorkoutPlan, WorkoutSession, WorkoutSet, WorkoutLog, Meal, NutritionGoal
from db.models.finance import FinancialTransaction, MonthlyBill, CreditCard
from services.time import local_today

if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == 'true', 'Disposable PostgreSQL required')
class IntegratedHardening(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import server
        self.today = local_today('America/Sao_Paulo')
        self.tokens = [uuid4().hex + uuid4().hex for _ in range(2)]
        async with unit_of_work() as session:
            repo = IdentityRepository(session)
            users = [await repo.create(email=f'{uuid4()}@example.test',name=name,password_hash='test-only') for name in ('Alice','Bob')]
            self.uid, self.bob = [user.id for user in users]
            for user, token in zip(users,self.tokens):
                await repo.add_session(user.id,token,datetime.now(timezone.utc)+timedelta(days=1))
        self.http = AsyncClient(transport=ASGITransport(server.app),base_url='https://sirius.test',headers={'Authorization':'Bearer '+self.tokens[0]})
        self.foreign = {'Authorization':'Bearer '+self.tokens[1]}

    async def asyncTearDown(self):
        await self.http.aclose(); await dispose_engine()

    def ok(self,response):
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def key(self,value=None,**extra):
        return {'Idempotency-Key':value or uuid4().hex,**extra}

    async def count(self,model,uid=None):
        async with unit_of_work() as session:
            return await session.scalar(select(func.count()).select_from(model).where(model.user_id==(uid or self.uid)))

    async def catalog(self):
        area=self.ok(await self.http.get('/api/study/areas'))[0]
        program=self.ok(await self.http.post('/api/study/programs',json={'area_id':area['area_id'],'name':'Owned preparation'}))
        book=self.ok(await self.http.post('/api/study/notebooks',json={'area_id':area['area_id'],'program_id':program['program_id'],'name':'Português'}))
        self.ok(await self.http.patch('/api/study/notebooks/'+book['notebook_id'],json={'conteudo_programatico':[{'assunto':'Crase','subtopicos':[]}]}))
        return program['program_id'],book['notebook_id']

    async def test_A_import_study_error_review_strategy_preserves_one_evidence_lineage(self):
        from services import edital_analyses
        from test_postgres_runtime_editais import RuntimeEditais
        document=RuntimeEditais.document(self,name='Analista',discipline='Português')
        document['cargos'][0]['disciplinas'][0].update(peso=2,peso_status='explicito',peso_fonte='página 1',num_questoes=10)
        await edital_analyses.save(self.uid,document)
        area=self.ok(await self.http.get('/api/study/areas'))[1]['area_id']
        provider=AsyncMock(return_value=json.dumps({'cronograma_semanal':[{'dia':'Segunda','blocos':[{'disciplina':'Português','duracao_minutos':30}]}],'estrategia':{'resumo':'Mock schedule'}}))
        body={'area_id':area,'analysis_id':document['analysis_id'],'cargo_index':0,'hours_per_day':2,'days_per_week':4}
        with patch('services.edital_import_routes.call_llm',provider):
            result=self.ok(await self.http.post('/api/study/programs/import-edital-with-cargo',json=body,headers=self.key('import-lineage')))
            replay=self.ok(await self.http.post('/api/study/programs/import-edital-with-cargo',json=body,headers=self.key('import-lineage')))
            self.assertEqual(result['program']['program_id'],replay['program']['program_id'])
            calls=provider.await_count
            self.assertEqual((await self.http.post('/api/study/programs/import-edital-with-cargo',json=body,headers=self.key(**self.foreign))).status_code,404)
            self.assertEqual(provider.await_count,calls)
        pid=result['program']['program_id'];nid=result['disciplinas'][0]['notebook_id'];base='/api/study/programs/'+pid
        vertical=self.ok(await self.http.get(base+'/edital-verticalizado'))
        self.assertEqual(vertical['disciplinas'][0]['peso_fonte'],'página 1')
        focus={'notebook_id':nid,'focus_minutes':25,'break_minutes':5}
        for response in await asyncio.gather(*(self.http.post('/api/study/focus/complete',json=focus,headers=self.key('focus-lineage')) for _ in range(2))):self.ok(response)
        attempt={'notebook_id':nid,'topic_key':'0','question':'Tema do edital','correct':False,'confidence':'confident','error_reason':'knowledge_gap'}
        answers=[self.ok(response) for response in await asyncio.gather(*(self.http.post('/api/study/v2/attempts',json=attempt,headers=self.key('error-lineage')) for _ in range(3)))]
        self.assertEqual(len({row['attempt_id'] for row in answers}),1)
        self.assertIsNotNone(answers[0]['review'])
        state=self.ok(await self.http.get('/api/study/v2/programs/'+pid+'/state'))
        strategy=self.ok(await self.http.get(base+'/strategy'))
        self.assertTrue(state);self.assertTrue(strategy['candidates'])
        generated=self.ok(await self.http.post(base+'/dated-plan',json={'start_date':str(self.today),'end_date':str(self.today+timedelta(days=6)),
            'availability':[60]*7,'adaptive':True,'block_minutes':30},headers=self.key('strategy-lineage')))
        self.assertTrue(generated['entries'])
        for path in (base+'/strategy',base+'/dated-plan','/api/study/v2/programs/'+pid+'/state'):
            self.assertEqual((await self.http.get(path,headers=self.foreign)).status_code,404)
        async with unit_of_work() as session:
            topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==self.uid,StudyTopic.notebook_id==UUID(nid)))
            saved=await session.get(QuestionAttempt,UUID(answers[0]['attempt_id']))
            self.assertEqual(saved.topic_id,topic.id)
            reviews=(await session.scalars(select(ReviewEvent).where(ReviewEvent.user_id==self.uid))).all()
            self.assertTrue(reviews);self.assertTrue(all(row.topic_id==topic.id for row in reviews))
        self.assertEqual(await self.count(QuestionAttempt),1);self.assertEqual(await self.count(StudySession),1)
        tutor={'preparation_id':pid,'notebook_id':nid,'topic_key':'0','mode':'socratic','conversation_id':str(uuid4()),'request_id':'owned-lineage-tutor','message':'Explique o erro registrado'}
        tutor_provider=AsyncMock(return_value='Explicação assistida e estimada do tópico registrado.')
        async with unit_of_work() as session:xp_before=(await session.get(User,self.uid)).xp
        with patch('services.study_tutor._llm',tutor_provider):
            first=self.ok(await self.http.post('/api/study/tutor/turn',json=tutor))
            self.assertEqual(first,self.ok(await self.http.post('/api/study/tutor/turn',json=tutor)))
            self.assertEqual(tutor_provider.await_count,1)
            self.assertEqual((await self.http.post('/api/study/tutor/turn',json=tutor,headers=self.foreign)).status_code,404)
            self.assertEqual(tutor_provider.await_count,1)
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,xp_before)
        self.assertEqual(await self.count(QuestionAttempt),1,'Tutor must not turn an estimate into real performance')

    async def test_C_real_session_sets_completion_training_and_life_are_consistent(self):
        plan=self.ok(await self.http.post('/api/workout-plans',json={'name':'Owned workout','days':[{'day_label':'A','exercises':[
            {'name':'Supino','muscle_group':'Peito','sets':2,'reps':'8-12','weight':'20'}]}]}))
        start=self.ok(await self.http.post('/api/workout-sessions/start',json={'plan_id':plan['plan_id'],'day_index':0},headers=self.key('start-training')))
        sid=start['session_id'];path='/api/workout-sessions/'+sid
        body={'completed':True,'sets_data':[{'weight':'20','reps':12,'rpe':8,'completed':True},{'weight':'20','reps':10,'rpe':9,'completed':True}]}
        self.ok(await self.http.patch(path+'/exercise/0',json=body,headers=self.key('sets-training')))
        self.assertEqual((await self.http.patch(path+'/exercise/0',json=body,headers=self.key(**self.foreign))).status_code,404)
        for response in await asyncio.gather(*(self.http.post(path+'/complete',json={},headers=self.key('complete-training')) for _ in range(3))):self.ok(response)
        state=self.ok(await self.http.get('/api/workouts/intelligence/state'))
        life=self.ok(await self.http.get('/api/life/state'))
        training=next(row for row in life['domains'] if row['domain']=='training')
        self.assertEqual(training['facts']['completed_today'],1)
        self.assertNotIn(sid,str(self.ok(await self.http.get('/api/workouts/intelligence/state',headers=self.foreign))))
        self.assertTrue(state['exercises']);self.assertEqual(await self.count(WorkoutSession),1)
        self.assertEqual(await self.count(WorkoutLog),1);self.assertEqual(await self.count(WorkoutSet),2)
        stored=next(row for row in self.ok(await self.http.get('/api/workout-plans')) if row['plan_id']==plan['plan_id'])
        self.assertEqual(str(stored['days'][0]['exercises'][0]['weight']),'20')

    async def test_D_decimal_expense_budget_scenario_and_context_never_write_simulations(self):
        from services.agent_reads import page_context
        month=self.today.strftime('%Y-%m')
        budget=self.ok(await self.http.post('/api/budgets',json={'month':month,'category':'food','limit':'0.20'},headers=self.key('budget-lineage')))
        transactions=[]
        for amount in ('0.10','0.20'):
            transactions.append(self.ok(await self.http.post('/api/transactions',json={'date':str(self.today),'type':'expense','category':'food','amount':amount},headers=self.key())))
        state=self.ok(await self.http.get('/api/finance/intelligence/state'))
        self.assertEqual(state['expense'],'0.30');self.assertTrue(any(row['kind']=='budget_overrun' for row in state['insights']))
        before=await self.count(FinancialTransaction)
        preview=self.ok(await self.http.post('/api/finance/intelligence/simulate',json={'monthly_expense':'5.01','opening_balance':'10.00','fingerprint':state['fingerprint']}))
        self.assertTrue(preview['read_only']);self.assertEqual(await self.count(FinancialTransaction),before)
        identity=transactions[0]['transaction_id']
        context=await page_context(str(self.uid),json.dumps({'transaction_id':identity,'facts':{'balance':'999999'}}))
        self.assertEqual(context['transaction']['amount'],'0.10');self.assertNotIn('999999',str(context))
        self.assertNotIn('transaction',await page_context(str(self.bob),json.dumps({'transaction_id':identity})))
        other=self.ok(await self.http.get('/api/finance/intelligence/state',headers=self.foreign));self.assertEqual(other['expense'],'0.00')
        self.assertEqual((await self.http.delete('/api/transactions/'+identity,headers=self.key(**self.foreign))).status_code,404)

    async def test_E_reviewed_plan_consumption_targets_and_budget_keep_provenance(self):
        from services.nutrition_plan_dto import PlanBody
        from services.nutrition_previews import create_preview
        body=PlanBody.model_validate({'name':'Reviewed meal plan','start_date':str(self.today),'days':[{'meals':[{'name':'Owned lunch','meal_type':'lunch','foods':[
            {'name':'Arroz','quantity':'100','unit':'g','calories':100,'protein':2,'carbs':20,'fat':0}]}]}]})
        staged=await create_preview(str(self.uid),body,hashlib.sha256(uuid4().bytes).hexdigest())
        confirm={'preview_id':staged['preview_id'],'plan':staged['preview']}
        self.assertEqual((await self.http.post('/api/nutrition/intelligence/confirm-plan',json=confirm,headers=self.key(**self.foreign))).status_code,404)
        first=self.ok(await self.http.post('/api/nutrition/intelligence/confirm-plan',json=confirm,headers=self.key('confirm-meals')))
        replay=self.ok(await self.http.post('/api/nutrition/intelligence/confirm-plan',json=confirm,headers=self.key('confirm-meals')))
        self.assertEqual(first['plan']['plan_id'],replay['plan']['plan_id'])
        self.assertEqual(await self.count(Meal),0);self.assertEqual(await self.count(NutritionGoal),0)
        proposals=self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={}))
        candidate=proposals['candidates'][0];path='/api/nutrition/intelligence/templates/planned/'+candidate['template_id']+'/record'
        for response in await asyncio.gather(*(self.http.post(path,json={'date':str(self.today)},headers=self.key('consume-meal')) for _ in range(3))):self.ok(response)
        state=self.ok(await self.http.get('/api/nutrition/intelligence/state'))
        self.assertEqual(state['consumed']['calories']['estimated'],'100.000')
        self.assertIsNone(state['remaining']['calories']);self.assertEqual(await self.count(Meal),1)
        self.assertEqual((await self.http.post(path,json={'date':str(self.today)},headers=self.key(**self.foreign))).status_code,404)
        life=self.ok(await self.http.get('/api/life/state'))
        nutrition=next(row for row in life['domains'] if row['domain']=='nutrition')
        self.assertEqual(nutrition['facts']['consumed']['calories']['estimated'],'100.000')
        self.ok(await self.http.put('/api/nutrition/goals',json={'daily_calories':2000},headers=self.key()))
        state=self.ok(await self.http.get('/api/nutrition/intelligence/state'))
        self.assertEqual(Decimal(state['remaining']['calories']),Decimal('1900'))
        self.assertIsNone(state['remaining']['protein'],'Unconfirmed default must remain unknown')
        budget=self.ok(await self.http.post('/api/budgets',json={'month':self.today.strftime('%Y-%m'),'category':'food','limit':'10.00'},headers=self.key()))
        self.ok(await self.http.post('/api/transactions',json={'type':'expense','category':'food','date':str(self.today),'amount':'3.00'},headers=self.key()))
        alternatives=self.ok(await self.http.post('/api/nutrition/intelligence/alternatives',json={'finance_budget_id':budget['budget_id']}))
        self.assertEqual(Decimal(alternatives['budget']['amount']),Decimal('7.00'))
        self.assertEqual(alternatives['budget']['source'],'FinanceEngine')
        self.assertEqual((await self.http.post('/api/nutrition/intelligence/alternatives',json={'finance_budget_id':budget['budget_id']},headers=self.foreign)).status_code,404)
        async with unit_of_work() as session:
            session.add(WorkoutLog(user_id=self.uid,name='Recorded training',activity_type='strength',duration_minutes=40,date=self.today))
        state=self.ok(await self.http.get('/api/nutrition/intelligence/state'))
        self.assertEqual(state['training_context'][0]['recorded_minutes'],40)
        self.assertNotIn('expenditure',state);self.assertEqual(await self.count(FinancialTransaction),1)

    async def test_BG_realistic_day_stale_preview_confirmation_audit_safe_undo_and_completion(self):
        from services.command_center import home
        pid,nid=await self.catalog();day=self.today+timedelta(days=1)
        midnight=datetime.combine(day,time(),ZoneInfo('America/Sao_Paulo'))
        workout=self.ok(await self.http.post('/api/workout-plans',json={'name':'Day workout','exercises':[{'name':'Agachamento'}]},headers=self.key()))
        task_body={'title':'Prepare work presentation','date':str(day),'priority':'high','duration_minutes':30}
        task=self.ok(await self.http.post('/api/tasks',json=task_body,headers=self.key()))
        availability={'weekdays':[[{'start_minute':480,'end_minute':1320}]]*7,'training_plan_id':workout['plan_id'],
            'training_weekdays':[day.weekday()],'duration_estimates':{'training':45,'finance':15}}
        self.ok(await self.http.put('/api/life/availability',json=availability,headers=self.key()))
        async with unit_of_work() as session:
            plan=StudyPlan(user_id=self.uid,program_id=UUID(pid),start_date=day,end_date=day,availability=[60]*7,block_minutes=30)
            session.add(plan);await session.flush()
            entry=StudyPlanEntry(user_id=self.uid,plan_id=plan.id,notebook_id=UUID(nid),date=day,name='Review real errors',minutes=45,kind='review',fixed=True,manual=False)
            work=CalendarEvent(user_id=self.uid,title='Fixed work',start_at=midnight+timedelta(hours=8),end_at=midnight+timedelta(hours=17))
            appointment=CalendarEvent(user_id=self.uid,title='Fixed appointment',start_at=midnight+timedelta(hours=18),end_at=midnight+timedelta(hours=19))
            session.add_all([entry,work,appointment]);await session.flush()
            card=CreditCard(user_id=self.uid,name='Owned bill source',limit=Decimal('200.00'),closing_day=1,due_day=min(day.day,28))
            session.add(card);await session.flush()
            bill=MonthlyBill(user_id=self.uid,month=day.replace(day=1),description='Owned bill due',amount=Decimal('100.01'),category='food',card_id=card.id)
            session.add(bill);await session.flush()
            fixed_before={row.id:(row.start_at,row.end_at) for row in (work,appointment)}
            xp_before=(await session.get(User,self.uid)).xp
        preview=self.ok(await self.http.post('/api/life/simulate',json={'date':str(day)}))
        domains={row['domain'] for row in preview['plan']['blocks']}
        self.assertTrue({'preparation','tasks','training'}<=domains)
        for block in preview['plan']['blocks']:
            self.assertTrue(block['reasons']);self.assertGreater(block['end_minute'],block['start_minute'])
            self.assertFalse(block['start_minute']<1020 and block['end_minute']>480)
            self.assertFalse(block['start_minute']<1140 and block['end_minute']>1080)
        accept=lambda p:{'scenario':p['plan']['scenario'],'fingerprint':p['state']['fingerprint'],'blocks':p['plan']['blocks'],'confirmed':True}
        self.ok(await self.http.put('/api/tasks/'+task['task_id'],json={**task_body,'duration_minutes':35},headers=self.key()))
        self.assertEqual((await self.http.post('/api/life/accept',json=accept(preview),headers=self.key())).status_code,409)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id==self.uid,CalendarEvent.source_type=='global_plan')),0)
        fresh=self.ok(await self.http.post('/api/life/simulate',json={'date':str(day)}))
        accepted=[self.ok(r) for r in await asyncio.gather(*(self.http.post('/api/life/accept',json=accept(fresh),headers=self.key('day-plan')) for _ in range(3)))]
        self.assertTrue(accepted[0]['event_ids']);self.assertTrue(all(r['event_ids']==accepted[0]['event_ids'] for r in accepted))
        self.assertFalse(accepted[0]['fixed_moved']);self.assertEqual(accepted[0]['xp_earned'],0)
        read=await home(self.uid,now=midnight+timedelta(hours=17))
        self.assertTrue(read['today']);self.assertTrue(all(r['why']['source'] for r in read['today']))
        self.assertTrue(any(row['title']=='Owned bill due' for row in read['attention']))
        search=self.ok(await self.http.get('/api/search/global',params={'q':'presentation','domain':'tasks'}))
        self.assertTrue(search['results']);self.assertEqual(self.ok(await self.http.get('/api/search/global',params={'q':'presentation'},headers=self.foreign))['results'],[])
        undo='/api/command/audit/'+accepted[0]['audit_id']+'/undo'
        self.assertEqual((await self.http.post(undo,json={'confirmed':True},headers=self.key(**self.foreign))).status_code,404)
        for r in await asyncio.gather(*(self.http.post(undo,json={'confirmed':True},headers=self.key('day-undo')) for _ in range(3))):self.assertTrue(self.ok(r)['undone'])
        async with unit_of_work() as session:
            for identity,expected in fixed_before.items():
                row=await session.get(CalendarEvent,identity);self.assertEqual((row.start_at,row.end_at),expected)
            self.assertFalse((await session.get(StudyPlanEntry,entry.id)).completed)
            self.assertFalse((await session.get(MonthlyBill,bill.id)).paid)
            self.assertEqual((await session.get(User,self.uid)).xp,xp_before)
        status='/api/tasks/'+task['task_id']+'/status'
        for r in await asyncio.gather(*(self.http.patch(status,json={'status':'done','date':str(day)},headers=self.key('day-complete')) for _ in range(3))):self.ok(r)
        life=self.ok(await self.http.get('/api/life/state',params={'date':str(day)}))
        self.assertFalse(any(c['source_id']==task['task_id'] for d in life['domains'] for c in d['candidates']))
        self.assertEqual(await self.count(TaskInstance),1)

    async def test_F_canonical_overdue_policy_delivery_uncertainty_restart_and_owner_receipt(self):
        from services import event_queue as queue,event_engine as engine,event_delivery as delivery
        from services.event_sources import collect,candidate
        from db.engine import get_engine
        now=queue.utc_now();due=self.today-timedelta(days=2)
        task=self.ok(await self.http.post('/api/tasks',json={'title':'Owned overdue fact','date':str(due),'priority':'high','duration_minutes':20},headers=self.key()))
        prefs={'automations':True,'quiet_start':0,'quiet_end':0,'daily_cap':10,'event_automation':{'rules':{'task.overdue':{'channels':['in_app','telegram']}}}}
        self.ok(await self.http.put('/api/ai/preferences',json=prefs))
        chat=uuid4().int%10**14
        async with unit_of_work() as session:session.add(TelegramLink(user_id=self.uid,chat_id=chat,telegram_name='Alice',linked_at=now))
        facts,_,_=await collect(self.uid,now=now,target=candidate('task.overdue','task',due,{},'Owned deadline',UUID(task['task_id'])))
        self.assertEqual(len(facts),1)
        for _ in range(2):
            async with unit_of_work() as session:await queue.enqueue(session,self.uid,facts[0],self.today)
        claims=await asyncio.gather(*(queue.claim(self.uid,scans_only=False) for _ in range(4)))
        overdue=[row for row in claims if row and row['type']=='task.overdue']
        self.assertEqual(len(overdue),1);claim=overdue[0]
        calls=[]
        async def sender(recipient,message):
            self.assertEqual(get_engine().sync_engine.pool.checkedout(),0,'No SQL connection during external IO')
            self.assertEqual(recipient,chat);self.assertIn('Owned overdue fact',message);calls.append(message)
            return None # Ambiguous provider acknowledgement, never a real Telegram call.
        with patch.dict(os.environ,{'AUTOMATION_DRY_RUN':'false'}):
            await engine.process(claim,dry_run=False)
            self.assertTrue(await delivery.deliver_one(user_id=self.uid,sender=sender))
            await dispose_engine() # Simulate worker restart, durable records survive.
            self.assertFalse(await delivery.deliver_one(user_id=self.uid,sender=sender))
        self.assertEqual(len(calls),1)
        async with unit_of_work() as session:
            rows=(await session.scalars(select(EventDelivery).where(EventDelivery.user_id==self.uid))).all()
            self.assertEqual(len(rows),2);uncertain=next(row for row in rows if row.channel=='telegram')
            self.assertEqual(uncertain.status,'uncertain');self.assertEqual(uncertain.attempts,1)
            self.assertEqual(uncertain.history[-1]['outcome'],'uncertain')
        inbox=self.ok(await self.http.get('/api/automations/inbox'));self.assertIn('Owned overdue fact',str(inbox))
        self.assertNotIn('Owned overdue fact',str(self.ok(await self.http.get('/api/automations/inbox',headers=self.foreign))))
        receipt='/api/automations/deliveries/'+str(uncertain.id)
        self.assertEqual((await self.http.post(receipt,json={'action':'retry'},headers=self.key(**self.foreign))).status_code,404)
        self.assertEqual((await self.http.post(receipt,json={'action':'retry'},headers=self.key())).status_code,409)
        self.assertEqual(await self.count(TaskInstance),0)

    async def test_real_sessions_logout_expiry_and_sensitive_provider_failure_fallback(self):
        from db.models.identity import UserSession
        private='PRIVATE_PROVIDER_PROMPT_SENTINEL'
        provider=AsyncMock(side_effect=ValueError(private))
        with patch('services.daily_briefing.call_llm',provider),self.assertLogs(level='ERROR') as logs:
            summary=self.ok(await self.http.get('/api/dashboard/daily-summary'))
        self.assertEqual(summary['user_id'],str(self.uid));self.assertNotIn(private,' '.join(logs.output));self.assertIn('ValueError',' '.join(logs.output))
        self.ok(await self.http.post('/api/auth/logout'))
        self.assertEqual((await self.http.get('/api/command/home')).status_code,401)
        self.ok(await self.http.get('/api/command/home',headers=self.foreign))
        async with unit_of_work() as session:
            row=await session.scalar(select(UserSession).where(UserSession.user_id==self.bob));row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        for path in ('/api/auth/me','/api/life/state','/api/command/home','/api/tasks','/api/workouts/intelligence/state','/api/nutrition/intelligence/state','/api/finance/intelligence/state','/api/automations/inbox','/api/study/areas'):
            self.assertEqual((await self.http.get(path,headers=self.foreign)).status_code,401,path)
