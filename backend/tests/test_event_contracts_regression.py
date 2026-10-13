import os
import sys
import unittest
from datetime import datetime, timezone, date
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from event_contracts import AutomationPolicy, Rule
from ai.actions import Preferences
from services.event_queue import quiet_at, next_allowed, period_key


class EventContracts(unittest.TestCase):
    def test_quiet_minutes_and_dst_do_not_fabricate_civil_times(self):
        user=SimpleNamespace(timezone='America/New_York')
        prefs=Preferences(event_automation=AutomationPolicy(quiet_start='01:00',quiet_end='03:00'))
        for instant in (datetime(2026,3,8,6,30,tzinfo=timezone.utc),datetime(2026,11,1,5,30,tzinfo=timezone.utc)):
            self.assertTrue(quiet_at(instant,user,prefs));allowed=next_allowed(instant,user,prefs)
            self.assertGreater(allowed,instant);self.assertFalse(quiet_at(allowed,user,prefs))
        prefs.event_automation=AutomationPolicy(quiet_start='22:30',quiet_end='07:15')
        self.assertFalse(quiet_at(datetime(2026,1,1,12,15,tzinfo=timezone.utc),user,prefs))

    def test_weekly_period_and_rules_are_bounded(self):
        self.assertEqual(period_key(date(2026,10,13),'weekly'),'2026-10-12')
        for args in ({'rules':{'invented':{}}},{'quiet_start':'25:10'},{'weekly_weekday':True}):
            with self.assertRaises(ValueError):AutomationPolicy.model_validate(args)
        with self.assertRaises(ValueError):Rule(channels=['in_app','in_app'])
