import sys
import unittest
from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.training_intelligence import build_state, decimal, rep_range, agent_context
from ai.registry import TOOLS, validate_call


DAY = date(2026, 10, 8)
PLAN = str(uuid4())
DAY_ID = str(uuid4())


def log(delta=0, *, weight='20', reps=12, rpe=8, count=3, target='8-12', group='Peito'):
    return {'log_id': str(uuid4()), 'plan_id': PLAN, 'day_index': 0, 'day_id': DAY_ID, 'origin_current': True, 'day_label': 'A', 'plan_name': 'Factual', 'date': str(DAY - timedelta(days=delta)), 'created_at': f'2026-10-08T10:{delta:02d}:00Z',
        'duration_minutes': 30, 'exercises_completed': [{'name': 'Supino', 'muscle_group': group, 'sets': 3, 'sets_completed': count,
        'reps': target, 'weight': '999', 'completed': True, 'sets_data': [{'weight': weight, 'reps': reps, 'rpe': rpe, 'completed': True} for _ in range(count)]}]}


def state(logs, **kwargs):
    return build_state(logs, day=DAY, start=DAY - timedelta(days=89), zone='America/Sao_Paulo', count=len(logs), **kwargs)


class TrainingRegression(unittest.TestCase):
    def test_progression_requires_all_evidence_and_never_writes(self):
        logs = [log(5), log()]; before = deepcopy(logs)
        ex = state(logs).exercises[0]
        self.assertEqual(ex.progression.suggested_weight, '20.500')
        self.assertFalse(ex.progression.automatic)
        self.assertEqual(logs, before)
        for field, value in [('rpe', ''), ('reps', None), ('weight', '')]:
            changed = deepcopy(logs); changed[1]['exercises_completed'][0]['sets_data'][0][field] = value
            self.assertIsNone(state(changed).exercises[0].progression.suggested_weight)

    def test_incomplete_high_effort_and_different_prescriptions_hold(self):
        for latest in (log(count=2), log(weight='0'), log(weight='21'), log(target='10'), log(target='até falhar')):
            self.assertIsNone(state([log(5), latest]).exercises[0].progression.suggested_weight)
        self.assertEqual(state([log(5), log(rpe=9)]).exercises[0].progression.action, 'maintain')
        self.assertEqual(state([log(5), log(reps=10)]).exercises[0].progression.action, 'maintain')
        latest = log(); latest['plan_id'] = str(uuid4())
        self.assertIsNone(state([log(5), latest]).exercises[0].progression.suggested_weight)
        self.assertIsNone(state([log(), log()]).exercises[0].progression.suggested_weight)

    def test_unknown_volume_is_not_zero_or_prescription(self):
        ex = state([log(weight='')]).exercises[0]
        self.assertIsNone(ex.volume); self.assertEqual(ex.known_volume, '0'); self.assertEqual(ex.records, [])
        zero = state([log(weight='0')]).exercises[0]
        self.assertEqual(zero.volume, '0'); self.assertFalse(any(r.kind == 'max_load' for r in zero.records))
        old = log(count=0); old['exercises_completed'][0]['sets_completed'] = 3
        legacy = state([old]).exercises[0]
        self.assertIsNone(legacy.volume); self.assertEqual(legacy.recorded_sets, 0)
        self.assertEqual(legacy.records, [])
        for recorded in (1, 2):
            partial = state([log(count=recorded)]).exercises[0]
            self.assertIsNone(partial.volume)
            self.assertEqual(partial.known_volume, str(240 * recorded))
            self.assertFalse(any(r.kind == 'max_volume' for r in partial.records))
            self.assertIsNone(state([log(count=recorded)]).muscle_groups[0].volume)

    def test_records_are_deterministic_and_equivalent_reps_are_separate(self):
        rows = [log(7, weight='30', reps=8), log(5, weight='20', reps=12), log(1, weight='30', reps=8)]
        ex = state(rows).exercises[0]
        maximum = next(r for r in ex.records if r.kind == 'max_load')
        self.assertEqual(str(maximum.log_id), rows[0]['log_id']); self.assertEqual(maximum.scope, 'analysis_window')
        equivalent = {r.reps: r.value for r in ex.records if r.kind == 'load_at_reps'}
        self.assertEqual(equivalent, {8: '30', 12: '20'})
        self.assertEqual(next(r.value for r in ex.records if r.kind == 'max_volume'), '720')
        self.assertEqual(state(list(reversed(rows))), state(rows))

    def test_group_identity_missing_labels_and_partial_volume(self):
        result = state([log(5, group='Peito'), log(group=''), log(3, weight='', group='peito')])
        self.assertEqual(len(result.exercises), 2)
        self.assertEqual(len(result.muscle_groups), 1)
        self.assertIsNone(result.muscle_groups[0].volume)
        self.assertEqual(result.muscle_groups[0].known_volume, '720')

    def test_duplicate_positions_do_not_create_fake_executions_or_records(self):
        row = log(); row['exercises_completed'].append(deepcopy(row['exercises_completed'][0]))
        result = state([row]); ex = result.exercises[0]
        self.assertEqual(ex.executions, 1); self.assertEqual(ex.recorded_sets, 6)
        self.assertEqual(ex.volume, '1440'); self.assertEqual(len(ex.history), 1)
        self.assertIsNone(ex.progression.suggested_weight)

    def test_conservative_alerts_have_operational_evidence(self):
        ex = state([log(5, weight='20'), log(weight='30')]).exercises[0]
        self.assertEqual({a.code for a in ex.alerts}, {'volume_jump', 'load_jump'})
        ex = state([log(7, weight='30'), log(4, weight='25'), log(weight='20')]).exercises[0]
        self.assertIn('recorded_decline', {a.code for a in ex.alerts})
        ex = state([log(7, count=1), log(4, count=1), log(count=1)]).exercises[0]
        self.assertIn('low_set_adherence', {a.code for a in ex.alerts})
        self.assertIsNone(state([log()]).scheduled_adherence)

    def test_truncation_empty_state_and_tools_remain_explicit_readonly(self):
        self.assertTrue(state([log()], truncated=True).truncated)
        self.assertIsNone(state([]).set_adherence)
        context = agent_context(state([log()]))
        self.assertNotIn('history', context['exercises'][0])
        self.assertEqual({r['kind'] for r in context['exercises'][0]['records']}, {'max_load', 'max_volume'})
        for tool in ('get_training_state', 'get_exercise_substitutions'):
            self.assertEqual(TOOLS[tool].permission, 'read')
        with self.assertRaises(ValueError): validate_call('get_training_state', {'user_id': PLAN})
        with self.assertRaises(ValueError): validate_call('get_exercise_substitutions', {'plan_id': PLAN, 'day_index': True, 'exercise_index': 0})

    def test_numeric_parsing_does_not_invent_values(self):
        for value in ('peso corporal', 'nan', '-1', True, None): self.assertIsNone(decimal(value))
        self.assertEqual(rep_range('8–12'), (8, 12)); self.assertIsNone(rep_range('12-8'))

    def test_identity_delimiters_and_tiny_loads_remain_safe(self):
        first, second = log(5, group='B|C'), log(group='C')
        first['exercises_completed'][0]['name'] = 'A'
        second['exercises_completed'][0]['name'] = 'A|B'
        self.assertEqual(len({e.key for e in state([first, second]).exercises}), 2)
        self.assertEqual(state([log(5, weight='0.001'), log(weight='0.001')]).exercises[0].progression.action, 'maintain')

    def test_progression_never_borrows_other_days_or_unknown_manual_origins(self):
        a, b, recent_a = log(7), log(3), log()
        b['day_index'] = 1; b['day_id'] = str(uuid4())
        self.assertIsNone(state([a, b]).exercises[0].progression.suggested_weight)
        ex = state([a, b, recent_a]).exercises[0]
        contexts = {p.day_index: p for p in ex.progressions}
        self.assertEqual(contexts[0].suggested_weight, '20.500')
        self.assertIsNone(contexts[1].suggested_weight)
        for row in (a, b): row.pop('day_index'); row.pop('day_id'); row['origin_current'] = False
        self.assertIsNone(state([a, b]).exercises[0].progression.suggested_weight)
        older, prior, unknown = log(10), log(5), log()
        unknown.pop('day_index'); unknown.pop('day_id'); unknown['origin_current'] = False
        ex = state([older, prior, unknown]).exercises[0]
        self.assertIsNone(ex.progressions[0].suggested_weight)
        self.assertEqual(ex.progressions[0].action, 'insufficient_data')

    def test_low_coverage_alert_uses_exactly_the_cited_executions(self):
        older = [log(delta, count=0) for delta in range(20, 10, -1)]
        recent = [log(7), log(4), log()]
        ex = state(older + recent).exercises[0]
        self.assertNotIn('low_set_adherence', {a.code for a in ex.alerts})
        recent = [log(7, count=1), log(4, count=1), log(count=1)]
        alert = next(a for a in state([log(20)] + recent).exercises[0].alerts if a.code == 'low_set_adherence')
        self.assertEqual(alert.evidence_dates, [date.fromisoformat(r['date']) for r in recent])
        self.assertIn('3/9', alert.reason)
