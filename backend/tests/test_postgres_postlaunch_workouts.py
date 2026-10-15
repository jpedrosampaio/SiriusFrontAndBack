"""A-J real persistence contracts; providers are mocked and no session is executed."""
import os, asyncio, json, copy, unittest
from unittest.mock import patch
from sqlalchemy import select, func
from db.models.health import WorkoutPlan, WorkoutSession, WorkoutLog
from db.models.identity import User
from db.engine import get_engine
from db.session import unit_of_work
from workout_generation_fixtures import bases
import test_postgres_runtime_workout_generation as setup


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS')=='true','Disposable PostgreSQL required')
class PostlaunchWorkouts(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=setup.RuntimeWorkoutGeneration.asyncSetUp
    asyncTearDown=setup.RuntimeWorkoutGeneration.asyncTearDown
    ok=setup.RuntimeWorkoutGeneration.ok

    def request(self,**changes):
        return {'objective':'condicionamento','level':'iniciante','workout_type':'calistenia',
            'training_location':'casa','available_equipment':[],'duration':'mes','cycle_weeks':4,
            'training_days_per_week':3,'session_minutes':45,'calisthenics_focus':'full_body',**changes}

    async def create(self,body,key='postlaunch-workout-001',headers=None):
        return await self.http.post('/api/workout-plans/generate',json=body,headers={'Idempotency-Key':key,**(headers or {})})

    async def test_invalid_or_unrepresented_splits_fail_before_provider_or_writes(self):
        body=self.request(workout_type='musculacao',available_equipment=['halteres'],generation_mode='tipo_treino',
            split_type='ABCDE',split_config=[{'label':label,'muscle_groups':['peito']} for label in 'ABCDE'],
            include_cardio=True,cardio_mode='hibrido_alternado',training_days_per_week=2)
        for index,changes in enumerate([
                {},
                {'split_type':'AB','split_config':[{'label':'A','muscle_groups':['peito']},{'label':'B','muscle_groups':[]}]},
                {'split_type':'A','split_config':[{'label':'A'}]},
                {'split_type':'A','split_config':[{'label':'A','muscle_groups':[' ']}]},
                {'split_type':None,'split_config':[{'label':[],'muscle_groups':['peito']}]},
                {'include_cardio':False,'cycle_weeks':1,'duration':'ciclo'},
            ]):
            response=await self.create({**body,**changes},key=f'postlaunch-invalid-split-{index}')
            self.assertEqual(response.status_code,422,response.text)
        self.llm.assert_not_awaited()
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_single_session_requires_combined_not_alternating_conditioning(self):
        for modality in ('musculacao','hibrido'):
            body=self.request(workout_type=modality,available_equipment=['halteres'],duration='dia',cycle_weeks=1,
                include_cardio=True,cardio_mode='hibrido_alternado')
            response=await self.create(body,key=f'postlaunch-single-alternating-{modality}')
            self.assertEqual(response.status_code,422,response.text)
        self.llm.assert_not_awaited()
        data=bases(labels=('A',))
        data['base_sessions'][0]['session_kind']='misto'
        data['base_sessions'][0]['exercises']+=bases(labels=('CARDIO',),kind='corrida',equipment=[])['base_sessions'][0]['exercises']
        self.llm.return_value=json.dumps(data)
        plan=self.ok(await self.create({**body,'cardio_mode':'hibrido'},key='postlaunch-single-combined'))['plan']
        self.assertEqual(len(plan['days']),1)
        self.assertTrue(any(ex['muscle_group']=='cardio' for ex in plan['days'][0]['exercises']))
        self.assertTrue(any(ex['muscle_group']=='peito' for ex in plan['days'][0]['exercises']))

    async def test_conditioning_selection_is_preserved_in_combined_and_alternating_plans(self):
        activities={'corrida':('Corrida leve',[]),'bike':('Bicicleta ergométrica',['bicicleta']),
            'HIIT':('Intervalos de movimentos corporais',[]),'caminhada':('Caminhada',[]),
            'natacao':('Natação',['piscina']),'pular_corda':('Pular corda',['corda']),
            'eliptico':('Elíptico',['eliptico']),'remo':('Remo ergométrico',['remo'])}
        for activity,(name,apparatus) in activities.items():
            for mode in ('hibrido','hibrido_alternado'):
                cardio=bases(labels=('CARDIO',),kind='corrida',equipment=apparatus)
                cardio['base_sessions'][0]['session_kind']='corrida' if activity=='corrida' else 'cardio'
                for ex in cardio['base_sessions'][0]['exercises']:
                    ex.update(name=name,conditioning_type=activity,exercise_kind='corrida' if activity=='corrida' else 'cardio')
                force=bases()
                if mode=='hibrido':
                    for base in force['base_sessions']:
                        base['exercises']+=copy.deepcopy(cardio['base_sessions'][0]['exercises'])
                        base['session_kind']='misto'
                    self.llm.side_effect=None;self.llm.return_value=json.dumps(force)
                else: self.llm.side_effect=[json.dumps(force),json.dumps(cardio)]
                body=self.request(workout_type='musculacao',available_equipment=['halteres',*apparatus],
                    include_cardio=True,cardio_type=activity,cardio_mode=mode)
                plan=self.ok(await self.create(body,key=f'postlaunch-conditioning-{activity}-{mode}'))['plan']
                executed_cardio=[ex for day in plan['days'] for ex in day['exercises'] if ex['muscle_group']=='cardio']
                self.assertTrue(executed_cardio);self.assertTrue(all(ex['name']==name for ex in executed_cardio))
                self.assertTrue(all(ex['weight']=='Intensidade a definir' for ex in executed_cardio))

                # A wrong generic running response must not replace the visible activity.
                if mode=='hibrido':
                    wrong=copy.deepcopy(force)
                    for base in wrong['base_sessions']:
                        for ex in base['exercises']:
                            if ex['muscle_group']=='cardio':
                                ex.update(name='Corrida leve' if activity!='corrida' else 'Caminhada',
                                    conditioning_type='corrida' if activity!='corrida' else 'caminhada',
                                    exercise_kind='corrida' if activity!='corrida' else 'cardio',required_equipment=[])
                    self.llm.side_effect=None;self.llm.return_value=json.dumps(wrong)
                    response=await self.create(body,key=f'postlaunch-conditioning-wrong-{activity}')
                    self.assertEqual(response.status_code,502,response.text)

    async def test_conditioning_requires_declared_apparatus_before_provider(self):
        for activity in ('bike','natacao','pular_corda','eliptico','remo'):
            response=await self.create(self.request(workout_type='hibrido',available_equipment=['halteres'],
                include_cardio=True,cardio_type=activity,cardio_mode='hibrido'),key=f'postlaunch-cardio-no-gear-{activity}')
            self.assertEqual(response.status_code,422,response.text)
        self.llm.assert_not_awaited()

    async def test_punctuation_only_exclusion_is_rejected_before_provider(self):
        response=await self.create(self.request(avoid_exercises=['---']))
        self.assertEqual(response.status_code,422,response.text);self.llm.assert_not_awaited()
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_conditioning_cannot_hide_behind_strength_tags_or_conflicting_kinds(self):
        for index,(group,kind,activity) in enumerate([
                ('pernas','corrida','corrida'),('pernas','corrida',None),
                ('pernas','resistencia',None),('peito','resistencia','bike'),('cardio','peso_corporal','bike')]):
            for mode in ('hibrido','hibrido_alternado'):
                force=bases()
                cardio=bases(labels=('CARDIO',),kind='corrida',equipment=['bicicleta'])
                cardio['base_sessions'][0]['session_kind']='cardio'
                for ex in cardio['base_sessions'][0]['exercises']:
                    ex.update(name='Bicicleta ergométrica',exercise_kind='cardio',conditioning_type='bike')
                disguised={**cardio['base_sessions'][0]['exercises'][0], 'name':'Corrida leve',
                    'muscle_group':group,'exercise_kind':kind,'conditioning_type':activity,'required_equipment':[]}
                if mode=='hibrido':
                    for base in force['base_sessions']:
                        base['session_kind']='misto'
                        base['exercises']+=copy.deepcopy(cardio['base_sessions'][0]['exercises'][:1])+[copy.deepcopy(disguised)]
                    self.llm.side_effect=None;self.llm.return_value=json.dumps(force)
                else:
                    cardio['base_sessions'][0]['exercises'].append(disguised)
                    self.llm.side_effect=[json.dumps(force),json.dumps(cardio),json.dumps(cardio)]
                response=await self.create(self.request(workout_type='hibrido',available_equipment=['halteres','bicicleta'],
                    include_cardio=True,cardio_type='bike',cardio_mode=mode),key=f'postlaunch-cardio-disguised-{index}-{mode}')
                self.assertEqual(response.status_code,502,response.text)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_legacy_hybrid_split_includes_conditioning_without_optional_flag(self):
        force=bases(labels=('A','B'))
        force['base_sessions']+=bases(labels=('CARDIO',),kind='corrida',equipment=[])['base_sessions']
        self.llm.return_value=json.dumps(force)
        body=self.request(workout_type='hibrido',available_equipment=['halteres'],generation_mode='tipo_treino',
            split_type='AB',split_config=[{'label':label,'muscle_groups':['peito']} for label in 'AB'],cardio_mode='hibrido_alternado')
        for index,changes in enumerate(({}, {'include_cardio':False})):
            plan=self.ok(await self.create({**body,**changes},key=f'postlaunch-implicit-hybrid-{index}'))['plan']
            self.assertEqual(len(plan['days']),12)
            self.assertEqual(sum(d['split_label']=='CARDIO' for d in plan['days']),4)
            self.assertEqual({d['split_label'] for d in plan['days']},{'A','B','CARDIO'})
            self.assertTrue(plan['include_cardio'])
        short=bases(labels=('A',))
        short['base_sessions']+=bases(labels=('CARDIO',),kind='corrida',equipment=[])['base_sessions']
        self.llm.return_value=json.dumps(short)
        plan=self.ok(await self.create({**body,'generation_mode':'periodo','split_type':None,'split_config':None,
            'cycle_weeks':1,'duration':'semana','training_days_per_week':2},key='postlaunch-short-alternating'))['plan']
        self.assertEqual([day['split_label'] for day in plan['days']],['A','CARDIO'])
        self.assertEqual({base['label'] for base in plan['base_sessions']},{day['split_label'] for day in plan['days']})

    async def test_hybrid_revision_preserves_declared_constraints_receipts_and_parent(self):
        data=bases(labels=('A','B'))
        cardio=bases(labels=('CARDIO',),kind='corrida',equipment=['bicicleta'],count=1)['base_sessions'][0]
        cardio['session_kind']='cardio'
        cardio['exercises'][0].update(name='Bicicleta ergométrica',exercise_kind='cardio',conditioning_type='bike')
        data['base_sessions'].append(cardio)
        self.llm.return_value=json.dumps(data)
        body=self.request(workout_type='hibrido',available_equipment=['halteres','bicicleta'],generation_mode='tipo_treino',
            split_type='AB',split_config=[{'label':label,'muscle_groups':['peito']} for label in 'AB'],
            cardio_type='bike',cardio_mode='hibrido_alternado',avoid_exercises=['Paralelas'])
        original=self.ok(await self.create(body))['plan'];pid=original['plan_id']
        self.assertTrue(original['include_cardio']);self.assertEqual(original['avoid_exercises'],['Paralelas'])
        url=f'/api/workout-plans/{pid}/improve'
        self.llm.reset_mock()
        self.assertEqual((await self.http.post(url,headers={'Authorization':'Bearer bob'})).status_code,404)
        self.llm.assert_not_awaited()
        wrong=copy.deepcopy(data);wrong['base_sessions'][0]['exercises'][0]['name']='Paralelas'
        self.llm.return_value=json.dumps(wrong)
        self.assertEqual((await self.http.post(url,headers={'Idempotency-Key':'postlaunch-revision-invalid'})).status_code,502)
        self.llm.reset_mock();self.llm.return_value=json.dumps(data)
        result=self.ok(await self.http.post(url,headers={'Idempotency-Key':'postlaunch-revision-valid'}));plan=result['plan']
        replay=self.ok(await self.http.post(url,headers={'Idempotency-Key':'postlaunch-revision-valid'}))
        self.assertTrue(replay['replayed']);self.assertEqual(replay['plan']['plan_id'],plan['plan_id']);self.llm.assert_awaited_once()
        self.assertIn('não informada',self.llm.call_args.args[0])
        self.assertEqual(plan['improved_from'],pid);self.assertEqual(len(plan['days']),12)
        self.assertEqual(sum(day['split_label']=='CARDIO' for day in plan['days']),4)
        self.assertFalse(any(ex['muscle_group']=='descanso' for day in plan['days'] for ex in day['exercises']))
        for field in ('available_equipment','training_location','session_minutes','avoid_exercises','cardio_type','cardio_mode'):
            self.assertEqual(plan[field],original[field])
        self.assertTrue(plan['include_cardio']);self.assertTrue(plan['composition_policy']['proposal_only'])
        self.assertTrue(all(ex['weight'] in ('A definir','Intensidade a definir') for day in plan['days'] for ex in day['exercises']))
        saved=self.ok(await self.http.get('/api/workout-plans'))
        self.assertEqual(len(saved),2);self.assertEqual(next(p for p in saved if p['plan_id']==pid)['days'],original['days'])
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,8)
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutSession).where(WorkoutSession.user_id==self.uid)),0)

    async def test_historical_plan_revision_keeps_legacy_full_calendar_contract(self):
        from services import workout_plan_writes
        days=[{'week':i//3+1,'day_name':f'sem{i//3+1}_dia{i%3+1}',
            'day_label':f'Semana {i//3+1} - Dia {i%3+1}',
            'exercises':[{'name':'Supino legado','sets':3,'reps':'10','muscle_group':'peito'}]} for i in range(12)]
        original=(await workout_plan_writes.save(str(self.uid),None,['legacy-fixture'],{
            'name':'Plano anterior','days':days,'objective':'hipertrofia','level':'intermediario',
            'workout_type':'musculacao','plan_duration':'mes','generation_mode':'periodo',
            'training_days_per_week':3,'cycle_weeks':4},0))['plan']
        self.llm.return_value=json.dumps({'name':'Nova versão legada','days':days,'improvements_summary':'Variações para revisão'})
        plan=self.ok(await self.http.post(f"/api/workout-plans/{original['plan_id']}/improve"))['plan']
        self.assertEqual(len(plan['days']),12);self.assertEqual(plan['improved_from'],original['plan_id'])
        self.assertFalse(plan.get('composition_policy'));self.assertEqual(plan['improvements_summary'],'Variações para revisão')
        self.llm.assert_awaited_once()

    async def test_period_revision_retains_selected_muscles_instead_of_default_full_body(self):
        self.llm.return_value=json.dumps(bases())
        original=self.ok(await self.create(self.request(workout_type='musculacao',available_equipment=['halteres'],muscle_groups=['pernas'])))['plan']
        self.assertEqual(original['muscle_groups'],['pernas'])
        revised=bases()
        for base in revised['base_sessions']:
            for ex in base['exercises']: ex['muscle_group']='pernas'
        self.llm.return_value=json.dumps(revised)
        plan=self.ok(await self.http.post(f"/api/workout-plans/{original['plan_id']}/improve"))['plan']
        self.assertEqual(plan['muscle_groups'],['pernas']);self.assertEqual(len(plan['days']),12)
        self.assertTrue(all(ex['muscle_group']=='pernas' for day in plan['days'] for ex in day['exercises']))

    async def test_revision_context_uses_all_current_edits_not_stale_generation_bases(self):
        for mode in ('days','flat'):
            self.llm.return_value=json.dumps(bases())
            source=self.ok(await self.create(self.request(workout_type='musculacao',available_equipment=['halteres']),key=f'postlaunch-edited-source-{mode}'))['plan']
            edited=copy.deepcopy(source['days'])
            for day in edited:
                for ex in day['exercises']:
                    if ex['name']=='Exercício A-0': ex['name']='Agachamento editado manualmente'
            edited[-1]['exercises'][-1].update(name='Última alteração manual do ciclo',rest_seconds=71,reps='11-13',weight='25 kg')
            payload={'name':source['name'],'days':edited} if mode=='days' else {
                'name':source['name'],'exercises':[ex for day in edited for ex in day['exercises']]}
            self.assertEqual((await self.http.patch(f"/api/workout-plans/{source['plan_id']}",json=payload)).status_code,200)
            current=next(plan for plan in self.ok(await self.http.get('/api/workout-plans')) if plan['plan_id']==source['plan_id'])
            self.assertEqual(current['plan_duration'],'mes','PATCH must preserve an omitted duration')
            self.assertTrue(any(ex['name']=='Exercício A-0' for base in current['base_sessions'] for ex in base['exercises']))
            self.llm.reset_mock();self.llm.return_value=json.dumps(bases())
            revised=self.ok(await self.http.post(f"/api/workout-plans/{source['plan_id']}/improve"))['plan']
            prompt=self.llm.call_args.args[0]
            self.assertIn('Agachamento editado manualmente',prompt);self.assertIn('Última alteração manual do ciclo',prompt)
            self.assertIn('25 kg',prompt);self.assertIn('11-13',prompt);self.assertNotIn('Exercício A-0',prompt)
            self.assertEqual(len(revised['days']),12);self.llm.assert_awaited_once()
            parent=next(plan for plan in self.ok(await self.http.get('/api/workout-plans')) if plan['plan_id']==source['plan_id'])
            self.assertEqual(parent['days'],current['days'])

    async def test_unselected_conditioning_is_rejected_without_plan_or_xp(self):
        data=bases()
        extra=bases(labels=('CARDIO',),kind='corrida',equipment=[],count=1)['base_sessions'][0]['exercises']
        for base in data['base_sessions']:
            base['exercises']+=copy.deepcopy(extra);base['session_kind']='misto'
        self.llm.return_value=json.dumps(data)
        response=await self.create(self.request(workout_type='musculacao',available_equipment=['halteres'],include_cardio=False))
        self.assertEqual(response.status_code,502,response.text)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_oversized_current_revision_is_rejected_instead_of_using_stale_bases(self):
        self.llm.return_value=json.dumps(bases())
        source=self.ok(await self.create(self.request(workout_type='musculacao',available_equipment=['halteres'])))['plan']
        days=copy.deepcopy(source['days'])
        for index,day in enumerate(days):
            for ordinal,ex in enumerate(day['exercises']):
                ex.update(name=f'Exercício editado {index}-{ordinal}',tutorial='PRIVATE_TUTORIAL_SOURCE'+'á'*5000)
        self.assertEqual((await self.http.patch(f"/api/workout-plans/{source['plan_id']}",json={'name':source['name'],'days':days})).status_code,200)
        self.llm.reset_mock()
        response=await self.http.post(f"/api/workout-plans/{source['plan_id']}/improve")
        self.assertEqual(response.status_code,422,response.text);self.assertNotIn('PRIVATE_TUTORIAL_SOURCE',response.text)
        self.llm.assert_not_awaited()
        self.assertEqual(len(self.ok(await self.http.get('/api/workout-plans'))),1)
        async with unit_of_work() as session: self.assertEqual((await session.get(User,self.uid)).xp,5)

    async def test_omitted_and_explicit_duration_are_distinct_idempotent_edits(self):
        self.llm.return_value=json.dumps(bases())
        source=self.ok(await self.create(self.request(workout_type='musculacao',available_equipment=['halteres'])))['plan']
        url=f"/api/workout-plans/{source['plan_id']}";body={'name':source['name'],'days':source['days']}
        headers={'Idempotency-Key':'postlaunch-patch-duration'}
        self.assertEqual((await self.http.patch(url,json=body,headers=headers)).status_code,200)
        self.assertEqual((await self.http.patch(url,json=body,headers=headers)).status_code,200)
        self.assertEqual((await self.http.patch(url,json={**body,'plan_duration':'dia'},headers=headers)).status_code,409)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans'))[0]['plan_duration'],'mes')
        self.assertEqual((await self.http.patch(url,json={**body,'plan_duration':'dia'},headers={'Idempotency-Key':'postlaunch-patch-explicit-duration'})).status_code,200)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans'))[0]['plan_duration'],'dia')

    async def test_running_implicitly_selects_running_not_another_cardio_activity(self):
        body=self.request(workout_type='corrida',available_equipment=['bicicleta'],preferred_terrain='asfalto')
        for index,activity in enumerate(('bike','caminhada')):
            data=bases(kind='corrida',equipment=[])
            for base in data['base_sessions']:
                for ex in base['exercises']:
                    ex.update(name='Bicicleta ergométrica' if activity=='bike' else 'Caminhada',
                        conditioning_type=activity,exercise_kind='cardio',required_equipment=['bicicleta'] if activity=='bike' else [])
            self.llm.return_value=json.dumps(data)
            self.assertEqual((await self.create(body,key=f'postlaunch-running-wrong-{index}')).status_code,502)
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
        self.llm.return_value=json.dumps(bases(kind='corrida',equipment=[],terrain='asfalto'))
        self.assertEqual(len(self.ok(await self.create(body,key='postlaunch-running-compatible'))['plan']['days']),12)

    async def test_strength_row_names_do_not_become_a_different_conditioning_activity(self):
        data=bases()
        for base in data['base_sessions']:
            base['exercises'][1].update(name='Remada com halteres',muscle_group='costas')
        self.llm.return_value=json.dumps(data)
        plan=self.ok(await self.create(self.request(workout_type='musculacao',available_equipment=['halteres'])))['plan']
        self.assertTrue(all(day['exercises'][1]['name']=='Remada com halteres' for day in plan['days']))

    async def test_odd_frequency_alternation_includes_every_declared_split_in_order(self):
        first=bases(labels=('A','B','C'))
        second=bases(labels=('D','E'))
        second['base_sessions']+=bases(labels=('CARDIO',),kind='corrida',equipment=[])['base_sessions']
        self.llm.side_effect=[json.dumps(first),json.dumps(second)]
        body=self.request(workout_type='musculacao',available_equipment=['halteres'],generation_mode='tipo_treino',
            split_type='ABCDE',split_config=[{'label':label,'muscle_groups':['peito']} for label in 'ABCDE'],
            include_cardio=True,cardio_mode='hibrido_alternado',training_days_per_week=3)
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12)
        self.assertEqual([d['split_label'] for d in plan['days'] if d['split_label']!='CARDIO'],list('ABCDEABC'))
        self.assertEqual(sum(d['split_label']=='CARDIO' for d in plan['days']),4)

    async def test_A_declared_none_four_weeks_three_days_complete_not_performance(self):
        data=bases(kind='peso_corporal',equipment=[])
        names=[['Agachamento livre','Flexão de joelhos','Ponte de glúteos'],
            ['Afundo estacionário','Flexão na parede','Elevação de panturrilha'],
            ['Agachamento isométrico','Flexão no solo','Ponte unilateral']]
        for session,variant in zip(data['base_sessions'],names):
            for exercise,name in zip(session['exercises'],variant): exercise['name']=name
        self.llm.return_value=json.dumps(data)
        result=self.ok(await self.create(self.request()))['plan']
        self.assertEqual(len(result['days']),12)
        for week in range(1,5): self.assertEqual(sum(d['week']==week for d in result['days']),3)
        self.assertEqual(result['available_equipment'],[]);self.assertEqual(result['training_location'],'casa')
        self.assertEqual(len(result['weekly_progression']),4)
        self.assertFalse(result['composition_policy']['automatic_load_changes'])
        self.assertEqual(result['composition_policy']['unallocated_recovery_days_per_week'],4)
        self.assertEqual(self.llm.await_count,1)
        self.assertNotIn('Retorne TODOS os dias',self.llm.call_args.args[0])
        self.assertTrue(all(ex['weight']=='Peso corporal' for d in result['days'] for ex in d['exercises']))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutSession).where(WorkoutSession.user_id==self.uid)),0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutLog).where(WorkoutLog.user_id==self.uid)),0)

    async def test_calisthenics_conditioning_requires_an_actual_circuit_proposal(self):
        ordinary=bases(kind='peso_corporal',equipment=[])
        self.llm.return_value=json.dumps(ordinary)
        body=self.request(calisthenics_focus='condicionamento')
        self.assertEqual((await self.create(body,key='postlaunch-conditioning-ordinary')).status_code,502)
        single=bases(kind='peso_corporal',equipment=[],count=1)
        for base in single['base_sessions']: base['training_method']='circuito'
        self.llm.return_value=json.dumps(single)
        self.assertEqual((await self.create(body,key='postlaunch-conditioning-one-station')).status_code,502)
        for base in ordinary['base_sessions']: base['training_method']='circuito'
        self.llm.return_value=json.dumps(ordinary)
        plan=self.ok(await self.create(body,key='postlaunch-conditioning-valid-circuit'))['plan']
        self.assertEqual(len(plan['days']),12)
        self.assertTrue(all(day['progression_notes'].startswith('Método: circuito.') for day in plan['days']))
        self.assertTrue(all('Método: circuito.' in ex['notes'] for day in plan['days'] for ex in day['exercises']))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,5)

    async def test_calisthenics_skills_require_technical_practice_and_identifiable_content(self):
        ordinary=bases(kind='peso_corporal',equipment=[])
        body=self.request(calisthenics_focus='habilidades')
        for index,method in enumerate(('series','tecnica')):
            for base in ordinary['base_sessions']: base.update(training_method=method,skill_target='controle_corporal')
            self.llm.return_value=json.dumps(ordinary)
            self.assertEqual((await self.create(body,key=f'postlaunch-skills-ordinary-{index}')).status_code,502)
        for index,name in enumerate(('Handstand','Apoio invertido','Bananeira','Parada de mão','  Apoio-invertido  ')):
            advanced=copy.deepcopy(ordinary)
            for base in advanced['base_sessions']:
                base['skill_target']='apoios' if 'Apoio' in name else 'equilibrio'
                base['exercises'][0]['name']=name
            self.llm.return_value=json.dumps(advanced)
            self.assertEqual((await self.create(body,key=f'postlaunch-skills-novice-advanced-{index}')).status_code,502)
        for base,name in zip(ordinary['base_sessions'],('Hollow hold básico','Prancha baixa controlada','Dead bug controlado')):
            base['exercises'][0].update(name=name,muscle_group='abdomen')
        self.llm.return_value=json.dumps(ordinary)
        plan=self.ok(await self.create(body,key='postlaunch-skills-valid-practice'))['plan']
        self.assertEqual(len(plan['days']),12)
        self.assertTrue(all(day['progression_notes'].startswith('Prática técnica de controle corporal.') for day in plan['days']))
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),1)
            self.assertEqual((await session.get(User,self.uid)).xp,5)
        secondary=copy.deepcopy(ordinary)
        for base in secondary['base_sessions']: base['exercises'][1]['name']='Apoio-invertido'
        self.llm.return_value=json.dumps(secondary)
        self.assertEqual((await self.create(body,key='postlaunch-skills-inversion-after-foundation')).status_code,502)
        advanced=copy.deepcopy(ordinary)
        for base in advanced['base_sessions']:
            base['skill_target']='apoios';base['exercises'][0].update(name='Apoio invertido',difficulty='avancado')
        self.llm.return_value=json.dumps(advanced)
        advanced_plan=self.ok(await self.create({**body,'level':'avancado'},key='postlaunch-skills-declared-advanced'))['plan']
        self.assertTrue(all(day['exercises'][0]['name']=='Apoio invertido' for day in advanced_plan['days']))

    async def test_B_and_C_declared_resistance_equipment_and_frequency(self):
        for frequency,equipment,location in [(4,['halteres','banco'],'casa'),(5,['halteres','banco','maquinas','polias'],'academia')]:
            data=bases(kind='resistencia',equipment=['halteres','banco'])
            data['base_sessions'][0]['exercises'][0]['name']='Supino com halteres'
            self.llm.return_value=json.dumps(data)
            body=self.request(workout_type='musculacao',level='intermediario',training_location=location,
                available_equipment=equipment,training_days_per_week=frequency,calisthenics_focus=None)
            plan=self.ok(await self.create(body,key=f'postlaunch-gym-{frequency}'))['plan']
            self.assertEqual(len(plan['days']),4*frequency);self.assertEqual(plan['available_equipment'],equipment)
            self.assertTrue(all(ex['weight']=='A definir' for d in plan['days'] for ex in d['exercises']))

    async def test_D_outdoor_bars_and_parallel_equipment_do_not_imply_gym(self):
        data=bases(kind='peso_corporal',equipment=['barra_fixa','paralelas'])
        data['base_sessions'][0]['exercises'][1]['name']='Barra fixa'
        self.llm.return_value=json.dumps(data)
        body=self.request(training_location='ar_livre',available_equipment=['barra_fixa','paralelas'],level='intermediario')
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12);self.assertEqual(plan['training_location'],'ar_livre')
        self.assertEqual(plan['available_equipment'],['barra_fixa','paralelas'])

    async def test_E_hybrid_alternates_without_counting_rest_as_training(self):
        force=bases(labels=('A','B','C'),kind='resistencia',equipment=['halteres'])
        cardio=bases(labels=('CARDIO',),kind='corrida',equipment=[])
        self.llm.side_effect=[json.dumps(force),json.dumps(cardio)]
        body=self.request(workout_type='hibrido',available_equipment=['halteres'],include_cardio=True,
            cardio_mode='hibrido_alternado',cardio_type='corrida')
        mixed=copy.deepcopy(force)
        for base in mixed['base_sessions']:
            base['session_kind']='misto';base['exercises']+=copy.deepcopy(cardio['base_sessions'][0]['exercises'][:1])
        self.llm.side_effect=[json.dumps(mixed),json.dumps(mixed),json.dumps(cardio)]
        invalid=await self.create(body,key='postlaunch-mixed-alternating')
        self.assertEqual(invalid.status_code,502);self.assertEqual(invalid.json()['detail']['code'],'workout_generation_modality_mismatch')
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
        self.llm.side_effect=[json.dumps(force),json.dumps(cardio)]
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12)
        for week in range(1,5):
            days=[d for d in plan['days'] if d['week']==week]
            self.assertEqual([d['split_label'] for d in days if d['split_label']=='CARDIO'],['CARDIO'])
        self.assertFalse(any(ex['muscle_group']=='descanso' for d in plan['days'] for ex in d['exercises']))

    async def test_F_running_no_devices_exact_duration_frequency(self):
        self.llm.return_value=json.dumps(bases(kind='corrida',equipment=[],terrain='asfalto'))
        body=self.request(workout_type='corrida',training_location='ar_livre',running_goal='5km',preferred_terrain='asfalto')
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12);self.assertEqual(plan['workout_type'],'corrida')
        self.assertEqual(plan['training_days_per_week'],3);self.assertEqual(plan['available_equipment'],[])

    async def test_running_terrain_matches_both_names_and_apparatus_in_both_directions(self):
        for requested in ('asfalto','trilha','esteira'):
            body=self.request(workout_type='corrida',available_equipment=['esteira'],preferred_terrain=requested)
            wrong='asfalto' if requested=='esteira' else 'esteira'
            data=bases(kind='corrida',equipment=['esteira'] if wrong=='esteira' else [],terrain=wrong)
            for base in data['base_sessions']:
                for ex in base['exercises']: ex['name']=('Corrida na esteira — ' if wrong=='esteira' else 'Corrida no asfalto — ')+ex['name']
            self.llm.return_value=json.dumps(data)
            invalid=await self.create(body,key=f'postlaunch-wrong-terrain-{requested}')
            self.assertEqual(invalid.status_code,502);self.assertEqual(invalid.json()['detail']['code'],'workout_generation_terrain_mismatch')
            # Matching metadata cannot conceal the opposite surface in the name/device.
            for base in data['base_sessions']:
                for ex in base['exercises']: ex['running_terrain']=requested
            self.llm.return_value=json.dumps(data)
            invalid=await self.create(body,key=f'postlaunch-disguised-terrain-{requested}')
            self.assertEqual(invalid.status_code,502);self.assertEqual(invalid.json()['detail']['code'],'workout_generation_terrain_mismatch')
        async with unit_of_work() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(WorkoutPlan).where(WorkoutPlan.user_id==self.uid)),0)
            self.assertEqual((await session.get(User,self.uid)).xp,0)
        for requested in ('asfalto','trilha','esteira','misto'):
            data=bases(kind='corrida',equipment=['esteira'] if requested=='esteira' else [],terrain=requested)
            self.llm.return_value=json.dumps(data)
            plan=self.ok(await self.create(self.request(workout_type='corrida',available_equipment=['esteira'],preferred_terrain=requested),
                key=f'postlaunch-valid-terrain-{requested}'))['plan']
            self.assertEqual(len(plan['days']),12)
            self.assertTrue(all(f'Terreno proposto: {requested}.' in ex['notes'] for day in plan['days'] for ex in day['exercises']))
        combined=bases()
        run=bases(labels=('CARDIO',),kind='corrida',equipment=[],terrain='asfalto',count=1)['base_sessions'][0]['exercises']
        for base in combined['base_sessions']:
            base['session_kind']='misto';base['exercises'][1].update(exercise_kind='peso_corporal',required_equipment=[])
            base['exercises']+=copy.deepcopy(run)
        self.llm.return_value=json.dumps(combined)
        plan=self.ok(await self.create(self.request(workout_type='hibrido',available_equipment=['halteres'],
            cardio_type='corrida',cardio_mode='hibrido',preferred_terrain='asfalto'),key='postlaunch-terrain-mixed-session'))['plan']
        for day in plan['days']:
            self.assertIn('Terrenos propostos: asfalto.',day['progression_notes'])
            self.assertNotIn('Terreno',day['exercises'][1]['notes'])
            self.assertIn('Terreno proposto: asfalto.',day['exercises'][-1]['notes'])

    async def test_G_invalid_json_missing_bases_apparatus_level_duration_never_save(self):
        invalid=[]
        missing=bases(labels=('A','B'),kind='peso_corporal',equipment=[]);invalid.append(missing)
        apparatus=bases(kind='peso_corporal',equipment=[]);apparatus['base_sessions'][0]['exercises'][0]['name']='Paralelas';invalid.append(apparatus)
        advanced=bases(kind='peso_corporal',equipment=[]);advanced['base_sessions'][0]['exercises'][0]['name']='Planche';invalid.append(advanced)
        volume=bases(kind='peso_corporal',equipment=[]);volume['base_sessions'][0]['exercises'][0].update(sets=99,rest_seconds=0);invalid.append(volume)
        too_long=bases(kind='peso_corporal',equipment=[],minutes=90);invalid.append(too_long)
        wrong_calendar=bases(kind='peso_corporal',equipment=[]);wrong_calendar['days']=[{'week':3}];invalid.append(wrong_calendar)
        for index,data in enumerate(invalid+['{"base_sessions":']):
            self.llm.side_effect=None;self.llm.return_value=data if isinstance(data,str) else json.dumps(data)
            response=await self.create(self.request(),key=f'postlaunch-invalid-{index}')
            self.assertEqual(response.status_code,502,response.text)
            self.assertIn('Nenhum',response.json()['detail']['message'])
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans')),[])
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,0)

    async def test_H_timeout_lost_response_concurrent_replay_and_foreign_owner(self):
        from ai.types import AIError
        self.llm.side_effect=AIError('timeout')
        self.assertEqual((await self.create(self.request())).status_code,504)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans')),[])
        self.llm.side_effect=None;self.llm.return_value=json.dumps(bases(kind='peso_corporal',equipment=[]))
        left,right=await asyncio.gather(self.create(self.request()),self.create(self.request()))
        first=self.ok(left);self.assertEqual(first['plan']['plan_id'],self.ok(right)['plan']['plan_id'])
        count=self.llm.await_count
        replay=self.ok(await self.create(self.request()))
        self.assertTrue(replay['replayed']);self.assertEqual(self.llm.await_count,count)
        conflict=await self.create(self.request(training_days_per_week=4))
        self.assertEqual(conflict.status_code,409);self.assertEqual(self.llm.await_count,count)
        other=self.ok(await self.create(self.request(),headers={'Authorization':'Bearer bob'}))
        self.assertNotEqual(other['plan']['plan_id'],first['plan']['plan_id'])
        self.assertEqual(other['plan']['user_id'],str(self.bob))
        async with unit_of_work() as session:
            self.assertEqual((await session.get(User,self.uid)).xp,5);self.assertEqual((await session.get(User,self.bob)).xp,5)

    async def test_I_historical_plan_without_new_parameters_is_untouched(self):
        old={'name':'Ficha anterior','plan_duration':'mes','days':[{'day_name':'dia1','exercises':[{'name':'Supino','sets':3,'reps':'12','weight':'20'}]}]}
        result=self.ok(await self.http.post('/api/workout-plans',json=old))
        listed=self.ok(await self.http.get('/api/workout-plans'))
        previous=next(p for p in listed if p['plan_id']==result['plan_id'])
        self.assertEqual(previous['name'],old['name']);self.assertEqual(previous['days'],result['days'])
        self.assertNotIn('available_equipment',previous);self.assertNotIn('professional_review_required',previous)
        self.llm.assert_not_awaited()

    async def test_J_sensitive_restrictions_private_warning_and_exclusion(self):
        body=self.request(training_days_per_week=5,health_condition='HISTORICO_PRIVADO_DE_LESAO_NO_OMBRO')
        self.llm.return_value=json.dumps(bases(kind='peso_corporal',equipment=[]))
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),20);self.assertTrue(plan['professional_review_required'])
        self.assertEqual(plan['health_condition'],body['health_condition'])
        self.assertNotIn(body['health_condition'],plan['name']+plan['description']+repr([d['day_label'] for d in plan['days']]))
        async with unit_of_work() as session:self.assertNotEqual((await session.get(User,self.uid)).preferences.get('health_condition'),body['health_condition'])
        forbidden=bases(kind='peso_corporal',equipment=[]);forbidden['base_sessions'][0]['exercises'][0]['name']='Exercício a evitar'
        self.llm.return_value=json.dumps(forbidden)
        response=await self.create(self.request(avoid_exercises=['Exercício a evitar']),key='postlaunch-avoid-001')
        self.assertEqual(response.status_code,502)
        medical=bases(kind='peso_corporal',equipment=[]);medical['description']='Protocolo de reabilitação e cura garantida'
        self.llm.return_value=json.dumps(medical)
        response=await self.create(self.request(),key='postlaunch-clinical-001')
        self.assertEqual(response.status_code,502);self.assertEqual(len(self.ok(await self.http.get('/api/workout-plans'))),1)

    async def test_provider_work_holds_no_database_connection_and_unknown_is_not_none(self):
        async def provider(*args,**kwargs):
            self.assertEqual(get_engine().pool.checkedout(),0)
            return json.dumps(bases(kind='peso_corporal',equipment=[]))
        self.llm.side_effect=provider
        self.ok(await self.create(self.request()))
        before=self.llm.await_count
        self.assertEqual((await self.create(self.request(available_equipment=None),key='postlaunch-unknown-001')).status_code,422)
        self.assertEqual(self.llm.await_count,before)

    async def test_twelve_weeks_seven_days_and_single_session_bounds(self):
        self.llm.return_value=json.dumps(bases(kind='peso_corporal',equipment=[]))
        plan=self.ok(await self.create(self.request(duration='ciclo',cycle_weeks=12,training_days_per_week=7)))['plan']
        self.assertEqual(len(plan['days']),84);self.assertEqual(plan['days'][-1]['week'],12)
        self.llm.return_value=json.dumps(bases(labels=('A',),kind='peso_corporal',equipment=[]))
        plan=self.ok(await self.create(self.request(duration='dia',cycle_weeks=1,training_days_per_week=None),key='postlaunch-single-001'))['plan']
        self.assertEqual(len(plan['days']),1);self.assertEqual(plan['training_days_per_week'],1)

    async def test_resistance_period_alternating_cardio_and_honest_time_lower_bound(self):
        data=bases(labels=('A','B','C'),kind='resistencia',equipment=['halteres'])
        data['description']='Não substitui diagnóstico. Bases variadas.'
        cardio=bases(labels=('CARDIO',),kind='corrida',equipment=[])
        self.llm.side_effect=[json.dumps(data),json.dumps(cardio)]
        body=self.request(workout_type='musculacao',calisthenics_focus=None,available_equipment=['halteres'],include_cardio=True,cardio_mode='hibrido_alternado')
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12);self.assertEqual(sum(day['split_label']=='CARDIO' for day in plan['days']),4)
        too_short=bases(kind='peso_corporal',equipment=[],minutes=10)
        for base in too_short['base_sessions']:
            for exercise in base['exercises']:exercise.update(sets=4,rest_seconds=180)
        self.llm.side_effect=None;self.llm.return_value=json.dumps(too_short)
        self.assertEqual((await self.create(self.request(session_minutes=10),key='postlaunch-rest-budget')).status_code,502)
        self.assertEqual(len(self.ok(await self.http.get('/api/workout-plans'))),1)

    async def test_new_weekly_proposal_today_and_life_agree_without_agenda_writes(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        from workout_calendar import scheduled_plan_index
        from services.life_adapters import training
        self.llm.return_value=json.dumps(bases(kind='peso_corporal',equipment=[]))
        plan=self.ok(await self.create(self.request()))['plan']
        parameters={'composition_policy':plan['composition_policy']}
        indices=[scheduled_plan_index(12,parameters,d) for d in range(28)]
        self.assertEqual([i for i in indices if i is not None],list(range(12)))
        self.assertEqual([sum(i is not None for i in indices[start:start+7]) for start in range(0,28,7)],[3]*4)
        self.assertIsNone(scheduled_plan_index(12,parameters,28));self.assertEqual(scheduled_plan_index(12,{},13),1)
        async with unit_of_work() as session:
            row=await session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id==self.uid));start=row.created_at.astimezone(ZoneInfo('America/Sao_Paulo')).date()
        for offset,expected in [(0,0),(1,None),(2,1),(7,3),(28,None)]:
            target=start+timedelta(days=offset)
            with patch('services.workout_plan_routes.local_today',return_value=target):schedule=self.ok(await self.http.get('/api/workouts/today-schedule'))
            self.assertEqual(schedule['scheduled'],expected is not None)
            if expected is not None:self.assertEqual(schedule['day_index'],expected)
            async with unit_of_work() as session:state=await training(session,self.uid,target,ZoneInfo('America/Sao_Paulo'))
            self.assertEqual(len(state.candidates),int(expected is not None));self.assertNotIn('health_condition',str(state.model_dump()))
        async with unit_of_work() as session:
            from db.models.planning import CalendarEvent
            self.assertEqual(await session.scalar(select(func.count()).select_from(CalendarEvent).where(CalendarEvent.user_id==self.uid)),0)

    async def test_declared_focus_and_split_identity_are_checked_before_save(self):
        data=bases(kind='peso_corporal',equipment=[])
        for base in data['base_sessions']:
            for exercise in base['exercises']:exercise['muscle_group']='pernas'
        self.llm.return_value=json.dumps(data)
        self.assertEqual((await self.create(self.request(calisthenics_focus='forca_upper'))).status_code,502)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans')),[])
        before=self.llm.await_count
        mismatch=self.request(workout_type='musculacao',available_equipment=['halteres'],generation_mode='tipo_treino',split_type='AB',split_config=[{'label':'A'}])
        self.assertEqual((await self.create(mismatch)).status_code,422);self.assertEqual(self.llm.await_count,before)

    async def test_apparatus_is_not_a_load_and_running_has_no_invented_numeric_intensity(self):
        for kind,modality,equipment,expected in [('peso_corporal','calistenia',['barra_fixa'],'Peso corporal'),('corrida','corrida',[],'Intensidade a definir')]:
            self.llm.return_value=json.dumps(bases(kind=kind,equipment=equipment))
            plan=self.ok(await self.create(self.request(workout_type=modality,available_equipment=equipment),key='postlaunch-intensity-'+kind))['plan']
            self.assertTrue(all(ex['weight']==expected for day in plan['days'] for ex in day['exercises']))

    async def test_every_selected_group_is_required_for_period_and_each_split(self):
        body=self.request(workout_type='musculacao',available_equipment=['halteres'],muscle_groups=['peito','triceps','ombros'])
        partial=bases()
        for base in partial['base_sessions']:
            for exercise in base['exercises']:exercise['muscle_group']='peito'
        self.llm.return_value=json.dumps(partial)
        self.assertEqual((await self.create(body)).status_code,502)
        split_groups=[['peito','triceps','ombros'],['costas','biceps'],['pernas','gluteos','abdomen']]
        split_body={**body,'muscle_groups':None,'generation_mode':'tipo_treino','split_type':'ABC',
            'split_config':[{'label':label,'muscle_groups':groups} for label,groups in zip('ABC',split_groups)]}
        self.assertEqual((await self.create(split_body,key='postlaunch-split-missing-groups')).status_code,502)
        self.assertEqual(self.ok(await self.http.get('/api/workout-plans')),[])
        async with unit_of_work() as session:self.assertEqual((await session.get(User,self.uid)).xp,0)
        complete=bases()
        for base,groups in zip(complete['base_sessions'],split_groups):
            for index,exercise in enumerate(base['exercises']):exercise['muscle_group']=groups[index%len(groups)]
        self.llm.return_value=json.dumps(complete)
        plan=self.ok(await self.create(split_body,key='postlaunch-complete-split-focus'))['plan']
        for day in plan['days']:
            expected=split_groups['ABC'.index(day['split_label'])]
            self.assertTrue(set(expected).issubset({exercise['muscle_group'] for exercise in day['exercises']}))
