import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.preparation_state import learning_stage
from study_mastery import mastery


class LearningStageRegression(unittest.TestCase):
    def test_contact_does_not_become_mastery_and_old_strong_evidence_needs_maintenance(self):
        today = date(2026, 10, 7)
        empty = mastery([], today)
        self.assertEqual(learning_stage(False, empty, None, today), 'not_started')
        self.assertEqual(learning_stage(True, empty, None, today), 'exposed')
        one = [{'correct': True, 'date': today.isoformat()}]
        self.assertEqual(learning_stage(True, mastery(one, today), today, today), 'practicing')
        strong = [{'correct': True, 'date': today.isoformat()} for _ in range(80)]
        self.assertEqual(learning_stage(True, mastery(strong, today), today, today), 'mastered')
        old_day = today - timedelta(days=20)
        old = [{'correct': True, 'date': old_day.isoformat()} for _ in range(80)]
        self.assertEqual(learning_stage(True, mastery(old, today), old_day, today), 'maintenance')
        self.assertEqual(len(old), 80)
        self.assertTrue(all(r['correct'] for r in old))
        very_old_day = today - timedelta(days=200)
        very_old = [{'correct': True, 'date': very_old_day.isoformat()} for _ in range(80)]
        self.assertNotEqual(learning_stage(True, mastery(very_old, today), very_old_day, today), 'mastered')
