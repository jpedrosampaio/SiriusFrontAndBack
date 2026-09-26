import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_adaptation import next_review, adapt_notebooks
from study_planner import build_plan


class AdaptationTests(unittest.TestCase):
    def test_review_thresholds_and_calendar_boundary(self):
        self.assertEqual(next_review('2026-12-31', 10, 5), '2027-01-01')
        self.assertEqual(next_review('2026-12-31', 10, 6), '2027-01-07')
        self.assertEqual(next_review('2026-12-31', 100, 85), '2027-01-21')
        with self.assertRaises(ValueError):
            next_review('2026-01-01', 10, 11)

    def test_adaptive_weights_preserve_source_and_completed_history(self):
        notebooks = [{'notebook_id': 'a', 'weight': 1}, {'notebook_id': 'b', 'weight': 1}]
        updated = adapt_notebooks(notebooks, {'a': {'total': 10, 'correct': 2}}, {'a'})
        self.assertEqual(notebooks[0]['weight'], 1)
        self.assertGreater(updated[0]['weight'], updated[1]['weight'])
        completed = [{'entry_id': 'done', 'date': '2026-09-28', 'minutes': 30, 'completed': True}]
        plan = build_plan('p', updated, [120] * 7, '2026-09-28', '2026-10-04', 30, completed)
        self.assertIn(completed[0], plan)
        counts = {key: sum(e['minutes'] for e in plan if e.get('notebook_id') == key) for key in ('a', 'b')}
        self.assertGreater(counts['a'], counts['b'])
        self.assertTrue(all(e.get('reason') for e in plan if not e['completed']))

    def test_small_sample_does_not_change_weight(self):
        self.assertEqual(adapt_notebooks([{'notebook_id': 'a', 'weight': 2}], {'a': {'total': 4, 'correct': 0}}, set())[0]['weight'], 2)
