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
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12)
        for week in range(1,5):
            days=[d for d in plan['days'] if d['week']==week]
            self.assertEqual([d['split_label'] for d in days if d['split_label']=='CARDIO'],['CARDIO'])
        self.assertFalse(any(ex['muscle_group']=='descanso' for d in plan['days'] for ex in d['exercises']))

    async def test_F_running_no_devices_exact_duration_frequency(self):
        self.llm.return_value=json.dumps(bases(kind='corrida',equipment=[]))
        body=self.request(workout_type='corrida',training_location='ar_livre',running_goal='5km',preferred_terrain='asfalto')
        plan=self.ok(await self.create(body))['plan']
        self.assertEqual(len(plan['days']),12);self.assertEqual(plan['workout_type'],'corrida')
        self.assertEqual(plan['training_days_per_week'],3);self.assertEqual(plan['available_equipment'],[])

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
