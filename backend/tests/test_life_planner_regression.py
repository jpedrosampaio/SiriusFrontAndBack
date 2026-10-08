import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime
from pydantic import ValidationError
from life_contracts import Availability, Scenario
from ai.planning import plan_day


class GlobalAllocator(unittest.TestCase):
    def plan(self,items,fixed=(),windows=None,**kwargs):
        return plan_day(items,fixed,'2026-10-09',0,1440,now=datetime.fromisoformat('2026-10-09T10:03:01-03:00'),
            windows=windows if windows is not None else [{'start_minute':600,'end_minute':720},{'start_minute':1080,'end_minute':1200}],**kwargs)

    def item(self,identity,minutes,**kwargs):
        return {'task_id':identity,'candidate_id':identity,'duration_minutes':minutes,'duration_origin':'recorded',
            'domain':'preparation','date':'2026-10-09',**kwargs}

    def test_cross_domain_competes_without_overlap_and_priority_is_factual(self):
        items=[self.item('workout',45,domain='training'),self.item('review',45,date_locked=True),
            self.item('bill-task',5,domain='tasks',deadline='2026-10-08',priority='high')]
        fixed=[{'date':'2026-10-09','event_id':'work','start_minute':660,'end_minute':1080}]
        result=self.plan(items,fixed)
        self.assertEqual([(b['task_id'],b['start_minute'],b['end_minute']) for b in result['blocks']],
            [('bill-task',605,610),('review',610,655),('workout',1080,1125)])
        self.assertEqual(result['available_minutes'],175)
        self.assertEqual(fixed[0]['start_minute'],660)

    def test_unknown_duration_and_empty_real_availability_fail_closed(self):
        result=self.plan([self.item('unknown',None,duration_origin='unknown')])
        self.assertFalse(result['blocks']);self.assertIn('duração',result['unscheduled'][0]['reason'])
        result=self.plan([self.item('a',20)],windows=[])
        self.assertEqual(result['available_minutes'],0);self.assertFalse(result['blocks'])

    def test_rounds_fixed_seconds_outward_and_does_not_span_windows(self):
        result=self.plan([self.item('a',60)],[{'date':'2026-10-09','start_minute':630,'end_minute':661}])
        self.assertEqual(result['blocks'][0]['start_minute'],1080)
        result=self.plan([self.item('a',130)])
        self.assertFalse(result['blocks']);self.assertEqual(len(result['unscheduled']),1)

    def test_typed_windows_and_integer_estimates(self):
        for values in ([{'start_minute':600,'end_minute':590}],
            [{'start_minute':600,'end_minute':700},{'start_minute':650,'end_minute':750}]):
            with self.assertRaises(ValidationError):Availability(weekdays=[values]+[[] for _ in range(6)])
        for value in (True,4,721,1.5):
            with self.assertRaises(ValidationError):Scenario(durations={'a':value})

    def test_many_overlapping_fixed_items_have_bounded_conflict_payload(self):
        fixed=[{'date':'2026-10-09','event_id':str(i),'start_minute':600,'end_minute':720} for i in range(1000)]
        result=self.plan([self.item('a',20)],fixed)
        self.assertEqual(len(result['conflicts']),50);self.assertTrue(result['conflicts_truncated'])
        self.assertEqual(result['blocks'][0]['start_minute'],1080)
