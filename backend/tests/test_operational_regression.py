import sys
import unittest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.planning import plan_day
from ai.registry import validate_call
from ai.daily_progress import progress_score


class OperationalTests(unittest.TestCase):
    def plan(self, tasks, commitments=(), at='2026-10-07T14:15:01-03:00', **kwargs):
        return plan_day(tasks, commitments, '2026-10-07', now=datetime.fromisoformat(at), **kwargs)

    def test_past_fixed_and_outside_window_never_move(self):
        result = self.plan([{'task_id':'wake','title':'Acordar','scheduled_time':'06:30'},
                            {'task_id':'night','scheduled_time':'19:00','duration_minutes':60}, {'task_id':'flex'}])
        wake, flex, night = result['blocks']
        self.assertEqual(wake['start_minute'],390)
        self.assertTrue(wake['past_due']); self.assertTrue(wake['duration_estimated'])
        self.assertEqual(flex['start_minute'],860)
        self.assertEqual(night['start_minute'],1140); self.assertFalse(night['duration_estimated'])
        self.assertEqual(result['available_minutes'],220)

    def test_fixed_conflicts_all_types_without_rescheduling(self):
        commitments=[{'event_id':'one','date':'2026-10-07','start_minute':900,'end_minute':960},
                     {'event_id':'two','date':'2026-10-07','start_minute':930,'end_minute':990}]
        result=self.plan([{'task_id':'a','scheduled_time':'15:00','duration_minutes':60},
                          {'task_id':'b','scheduled_time':'15:15','duration_minutes':60}],commitments)
        self.assertEqual(len(result['conflicts']),6)
        self.assertEqual(result['available_minutes'],130)
        self.assertEqual([b['start_minute'] for b in result['blocks']],[900,915])

    def test_multiple_gaps_and_oversized_task(self):
        result=self.plan([{'task_id':'big','duration_minutes':720}, {'task_id':'small','duration_minutes':45}, {'task_id':'estimate'}],
            [{'date':'2026-10-07','start_minute':900,'end_minute':1020}],at='2026-10-07T14:00:00-03:00')
        self.assertEqual(result['unscheduled'][0]['task_id'],'big')
        self.assertEqual([(b['start_minute'],b['end_minute']) for b in result['blocks']],[(840,870),(1020,1065)])

    def test_after_window_and_completed(self):
        result=self.plan([{'task_id':'fixed','scheduled_time':'19:00'}, {'task_id':'done','completed':True,'scheduled_time':'06:30'}, {'task_id':'flex'}],at='2026-10-07T18:00:00-03:00')
        self.assertEqual(result['available_minutes'],0)
        self.assertEqual([b['task_id'] for b in result['blocks']],['fixed'])
        self.assertEqual(len(result['unscheduled']),1)

    def test_timezone_and_rounding(self):
        result=self.plan([{'task_id':'a'}],at='2026-10-07T17:15:00+00:00')
        self.assertEqual(result['blocks'][0]['start_minute'],855)
        result=self.plan([{'task_id':'a'}],at='2026-10-07T17:15:00+00:00',timezone_name='UTC')
        self.assertEqual(result['blocks'][0]['start_minute'],1035)
        with self.assertRaises(ValueError): self.plan([],at='2026-10-07T14:00:00')

    def test_title_is_not_a_temporal_constraint(self):
        result=self.plan([{'title':'Acordar às 06:30'}])
        self.assertEqual(result['blocks'][0]['kind'],'flexible_task')

    def test_task_validation_and_optional_legacy_contract(self):
        args={'title':'Acordar','date':'2026-10-07','recurrence':'daily','scheduled_time':'06:30','duration_minutes':5}
        self.assertEqual(validate_call('create_task',args)['scheduled_time'],'06:30')
        self.assertIsNone(validate_call('create_task',{'title':'Legacy','date':'2026-10-07'})['duration_minutes'])
        for time in ('24:00','9:00','12:60','06:30:10','06:30Z'):
            with self.assertRaises(ValueError): validate_call('create_task',args|{'scheduled_time':time})
        for duration in (4,721,True,45.5,'30'):
            with self.assertRaises(ValueError): validate_call('create_task',args|{'duration_minutes':duration})

    def test_score_is_deterministic_with_empty_and_partial_plan(self):
        self.assertEqual(progress_score({}),0)
        self.assertEqual(progress_score({'tasks_pending':2}),0)
        self.assertEqual(progress_score({'tasks_done':1,'habits_done':1,'tasks_pending':1,'habits_pending':1}),50)
        self.assertEqual(progress_score({'tasks_done':3}),100)


class AgentScheduling(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_time_duration_examples_remain_confirmable_proposals(self):
        from ai.agent import SiriusAgent, AgentPlan, PlannedCall
        from ai.actions import Preferences
        cases=[('Crie uma tarefa diária para acordar às 06:30.', {'title':'Acordar','scheduled_time':'06:30','recurrence':'daily'}),
               ('Estudar Constitucional hoje por 1 hora.', {'title':'Estudar Constitucional','duration_minutes':60}),
               ('Estudar Constitucional às 19h por 45 minutos.', {'title':'Estudar Constitucional','scheduled_time':'19:00','duration_minutes':45})]
        for index,(message,fields) in enumerate(cases):
            core=SimpleNamespace(page_context=AsyncMock(return_value={}),read=AsyncMock(return_value=[]))
            router=SimpleNamespace(settings=SimpleNamespace(rag=False),generate=AsyncMock(return_value=SimpleNamespace(
                data=AgentPlan(reply='Proposta',calls=[PlannedCall(name='create_task',arguments=fields|{'date':'2026-10-07'})]),
                provider='mock',model='mock',fallback=False)))
            actions=SimpleNamespace(preferences=AsyncMock(return_value=Preferences()),propose=AsyncMock(return_value={'status':'pending'}))
            agent=SiriusAgent(core,router,SimpleNamespace(get=AsyncMock(return_value={'gemini':'mock'})),actions,
                SimpleNamespace(list=AsyncMock(return_value=[])),SimpleNamespace())
            result=await agent.respond('owner',SimpleNamespace(message=message,page='/tasks',page_context='{}',conversation_id='primary',request_id=str(index)),json.dumps({'history':[]}))
            args=actions.propose.call_args.args[4]
            for key,value in fields.items():self.assertEqual(args[key],value)
            self.assertEqual(result['actions'],[{'status':'pending'}])
            self.assertIn('Nada foi executado ainda',result['reply'])
            self.assertIn('scheduled_time HH:MM',router.generate.call_args.kwargs['system'])
