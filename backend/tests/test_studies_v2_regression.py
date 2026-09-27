import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi import HTTPException
from pydantic import ValidationError
from studies_v2 import AttemptInput, TargetInput, topic_title, studies_v2_router
from study_mastery import mastery, adaptive_review, topic_priority


class MasteryTests(unittest.TestCase):
    day = date(2026, 9, 26)

    def evidence(self, total, correct, day='2026-09-26'):
        return [{'date': day, 'correct': i < correct} for i in range(total)]

    def test_no_answers_does_not_claim_mastery(self):
        self.assertIsNone(mastery([], self.day)['score'])

    def test_small_sample_shrinks_and_exposes_confidence(self):
        result = mastery(self.evidence(5, 5), self.day)
        self.assertLess(result['score'], 100)
        self.assertEqual(result['confidence'], 'low')
        self.assertEqual(result['samples'], 5)
        self.assertLess(result['range'][0], result['score'])

    def test_improvement_monotonic_and_stale_evidence_loses_confidence(self):
        low = mastery(self.evidence(50, 15), self.day)
        high = mastery(self.evidence(50, 45), self.day)
        old = mastery(self.evidence(50, 45, '2025-01-01'), self.day)
        self.assertGreater(high['score'], low['score'])
        self.assertEqual(high['confidence'], 'high')
        self.assertEqual(old['confidence'], 'low')
        self.assertLess(old['score'], high['score'])

    def test_review_errors_short_interval_and_year_boundary(self):
        result = adaptive_review(self.evidence(10, 3, '2026-12-31'), date(2026, 12, 31))
        self.assertEqual(result['due_date'], '2027-01-01')
        strong = adaptive_review(self.evidence(50, 50), self.day, previous_reviews=4)
        hard = adaptive_review(self.evidence(50, 50), self.day, previous_reviews=4, difficulty='hard')
        self.assertGreater(strong['interval_days'], hard['interval_days'])

    def test_priority_is_explainable_and_weight_not_mutated(self):
        normal = topic_priority(weight=2, estimate=80, studied=True)
        weak = topic_priority(weight=2, estimate=40, errors=4, overdue=True)
        self.assertGreater(weak['priority'], normal['priority'])
        self.assertIn('revisão vencida', weak['reasons'])

    def test_late_same_day_errors_are_recent_even_if_appended(self):
        rows = [{**row, 'created_at': '2026-09-26T08:00:00+00:00'} for row in self.evidence(50, 50)]
        rows.extend({'date': '2026-09-26', 'correct': False, 'created_at': '2026-09-26T20:00:00+00:00'} for _ in range(2))
        self.assertEqual(adaptive_review(rows, self.day)['interval_days'], 1)

    def test_reference_validation_and_strict_correct(self):
        with self.assertRaises(ValidationError):
            AttemptInput(notebook_id='n', topic_key='0.$x', question='q', correct=True)
        with self.assertRaises(ValidationError):
            AttemptInput(notebook_id='n', topic_key='0', question='q', correct='false')
        with self.assertRaises(ValidationError):
            TargetInput(name='test', kind='trt22')
        self.assertEqual(topic_title({'topicos': [{'assunto': 'A', 'subtopicos': ['B']}]}, '0_0'), 'B')
        with self.assertRaises(HTTPException): topic_title({'topicos': []}, '0')


class OwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_foreign_attempt_cannot_write(self):
        db = SimpleNamespace(notebooks=SimpleNamespace(find_one=AsyncMock(return_value=None)))
        async def mutate(uid, key, args, operation): return await operation(None, 0)
        router = studies_v2_router(db, AsyncMock(return_value=SimpleNamespace(user_id='owner')), mutate)
        endpoint = next(r.endpoint for r in router.routes if r.path.endswith('/attempts'))
        with self.assertRaises(HTTPException) as error:
            await endpoint(SimpleNamespace(headers={'Idempotency-Key': 'test'}), AttemptInput(notebook_id='foreign', topic_key='0', question='q', correct=False), None)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(db.notebooks.find_one.call_args.args[0], {'user_id': 'owner', 'notebook_id': 'foreign'})

    async def test_foreign_program_cannot_read_performance(self):
        db = SimpleNamespace(study_programs=SimpleNamespace(find_one=AsyncMock(return_value=None)))
        router = studies_v2_router(db, AsyncMock(return_value=SimpleNamespace(user_id='owner')), None)
        endpoint = next(r.endpoint for r in router.routes if r.path.endswith('/performance'))
        with self.assertRaises(HTTPException) as error:
            await endpoint(SimpleNamespace(headers={}), 'foreign', None)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == '__main__': unittest.main()
