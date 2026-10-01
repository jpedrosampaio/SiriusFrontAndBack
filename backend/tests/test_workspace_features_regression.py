import asyncio
import sys
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_planner import build_plan
from edital_sources import source_pages, locate_subject


class PlannerTests(unittest.TestCase):
    def test_capacity_dates_reviews_and_preserved_completed_history(self):
        completed = [{'entry_id': 'done', 'date': '2026-09-28', 'minutes': 50, 'completed': True}]
        availability = [60, 90, 60, 60, 30, 0, 0]
        result = build_plan('program', [{'notebook_id': 'math', 'name': 'Matemática', 'weight': 3}, {'notebook_id': 'law', 'name': 'Direito', 'weight': 1}], availability, '2026-09-28', '2026-10-30', 50, completed)
        self.assertIn(completed[0], result)
        minutes = defaultdict(int)
        for row in result:
            minutes[row['date']] += row['minutes']
            self.assertLessEqual(row['date'], '2026-10-30')
        for day, total in minutes.items():
            self.assertLessEqual(total, availability[date.fromisoformat(day).weekday()])
        self.assertTrue(any(row.get('kind') == 'Revisão' for row in result))
        self.assertEqual(len({r['entry_id'] for r in result}), len(result))

    def test_zero_availability_never_creates_blocks(self):
        self.assertEqual(build_plan('p', [{'notebook_id': 'n'}], [0] * 7, '2026-01-01', '2026-01-30', 50), [])

    def test_sources_use_real_pages_and_preserve_original_text(self):
        pages = source_pages('[PÁGINA 1]\nRegras gerais\n[PÁGINA 50]\nLÍNGUA PORTUGUESA\nInterpretação de textos')
        evidence = locate_subject('Língua Portuguesa', pages)
        self.assertEqual(evidence[0]['page'], 50)
        self.assertIn('Interpretação', evidence[0]['quote'])
        self.assertEqual(locate_subject('Direito Penal', pages), [])
        self.assertEqual(source_pages('Legacy document without page markers'), [])






if __name__ == '__main__': unittest.main()
