"""Boundaries that must remain consistent across modules."""
import ast
import logging
import sys
import unittest
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CargoIdentityTests(unittest.TestCase):
    def dedup(self, cargos):
        tree = ast.parse((ROOT / 'server.py').read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if getattr(n, 'name', '') in {'_normalize_cargo_name', 'dedup_cargos_fuzzy'}]
        ns = dict(List=List, logging=logging)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'cargo', 'exec'), ns)
        return ns['dedup_cargos_fuzzy'](cargos)

    def test_levels_codes_areas_and_specialties_are_not_noise(self):
        for names in [
            ['Analista Junior', 'Analista Pleno', 'Analista Sênior'],
            ['Analista I', 'Analista II', 'Analista III', 'Analista IV'],
            ['G01 Analista Judiciário', 'G02 Analista Judiciário'],
            ['Analista - Área Judiciária', 'Analista - Área Judiciária Especial'],
            ['Analista - Engenharia Civil', 'Analista - Engenharia Naval'],
        ]:
            with self.subTest(names=names):
                self.assertEqual(len(self.dedup([{'nome': n} for n in names])), len(names))

    def test_separate_identity_fields_prevent_merge(self):
        for field in ['codigo', 'codigo_cargo', 'especialidade', 'area', 'nivel']:
            with self.subTest(field=field):
                self.assertEqual(len(self.dedup([{'nome': 'Analista', field: 'I'}, {'nome': 'Analista', field: 'II'}])), 2)

    def test_exact_typographical_duplicate_unions_subjects(self):
        result = self.dedup([{'nome': 'ANALISTA — JÚNIOR', 'disciplinas': [{'nome': 'Português'}]},
                             {'nome': 'Analista - Junior', 'disciplinas': [{'nome': 'Direito'}]}])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['disciplinas']), 2)


class RecurrenceTests(unittest.TestCase):
    def test_boundaries(self):
        from task_recurrence import expand_task_dates
        self.assertEqual(expand_task_dates({'date': '2026-01-31', 'recurrence': 'monthly'}, '2026-01-01', '2026-03-31'), ['2026-01-31', '2026-02-28', '2026-03-31'])
        self.assertEqual(expand_task_dates({'date': '2024-01-31', 'recurrence': 'monthly'}, '2024-02-01', '2024-02-29'), ['2024-02-29'])
        self.assertEqual(expand_task_dates({'date': '2026-12-28', 'recurrence': 'weekly'}, '2026-12-27', '2027-01-05'), ['2026-12-28', '2027-01-04'])
        self.assertEqual(expand_task_dates({'date': '2026-09-25', 'recurrence': 'daily'}, '2026-09-24', '2026-09-26'), ['2026-09-25', '2026-09-26'])
        self.assertEqual(expand_task_dates({'date': '2026-09-25', 'recurrence': 'once'}, '2026-09-26', '2026-09-27'), [])

    def test_legacy_created_at_uses_local_calendar_date(self):
        from task_recurrence import expand_task_dates
        self.assertEqual(expand_task_dates({'created_at': '2026-09-25T01:00:00+00:00'}, '2026-09-24', '2026-09-25'), ['2026-09-24'])


class ReportWindowTests(unittest.TestCase):
    def test_periods_cross_year_and_month(self):
        from report_metrics import report_window
        self.assertEqual(report_window('semanal', '2027-01-01'), ('2026-12-28', '2027-01-01'))
        self.assertEqual(report_window('mensal', '2024-02-29'), ('2024-02-01', '2024-02-29'))
        self.assertEqual(report_window('diário', '2026-09-25'), ('2026-09-25', '2026-09-25'))
        self.assertEqual(report_window('sprint', '2026-09-25', '2026-09-01', '2026-09-14'), ('2026-09-01', '2026-09-14'))
        for args in [('sprint', '2026-09-25'), ('sprint', '2026-09-25', '2026-09-24', '2026-09-26'), ('bad', '2026-09-25')]:
            with self.assertRaises(ValueError):
                report_window(*args)


if __name__ == '__main__':
    unittest.main()
