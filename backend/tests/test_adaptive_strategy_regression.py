import sys
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adaptive_strategy import rank_candidates, preview_strategy, load_guard
from study_planner import build_strategy_plan
from study_workspace_routes import StrategyScenario
from study_mastery import adaptive_review


class AdaptiveStrategyTests(unittest.TestCase):
    def state(self):
        return {'preparation_id':'p','days_remaining':20,'coverage':{'studied':0},
            'syllabus_graph':{'disciplines':[{'id':'n','title':'Law','weight':2,'question_count':10}],
            'topics':[{'id':i,'notebook_id':'n','topic_key':str(k),'title':i,'covered':False,
                'mastery':{'score':None},'question_count':0,'recent_errors':0,'evidence_ids':[]} for k,i in enumerate(['a','b'])]},
            'strategy_facts':{'missed_entries':[]},'candidate_model':{'completed_sessions':4,'consistency':40},
            'current_pace':{'minutes_per_week':60}}

    def test_deterministic_risk_and_return_show_unknowns_and_do_not_mutate(self):
        state=self.state(); before=deepcopy(state)
        rows=rank_candidates(state,date(2026,10,8))
        self.assertEqual(rows,rank_candidates(state,date(2026,10,8)))
        self.assertEqual(state,before)
        self.assertEqual(rows[0]['risk'],48)
        self.assertEqual(rows[0]['expected_return'],.096)
        self.assertIn('sem amostra de domínio',rows[0]['reasons'])
        self.assertIn('peso registrado a conferir',rows[0]['reasons'])

    def test_decay_is_smooth_bounded_and_never_invents_incorrect_answers(self):
        state=self.state(); topic=state['syllabus_graph']['topics'][0]
        topic.update(covered=True,last_answer_date='2026-01-01',question_count=50,mastery={'score':90})
        early=rank_candidates(state,date(2026,1,2)); late=rank_candidates(state,date(2026,10,8))
        early=next(c for c in early if c['id']=='a'); late=next(c for c in late if c['id']=='a')
        self.assertLess(early['risk_components']['evidence_age'],late['risk_components']['evidence_age'])
        self.assertLessEqual(late['risk_components']['evidence_age'],10)
        self.assertEqual(late['risk_components']['recent_errors'],0)
        self.assertEqual(topic['mastery']['score'],90)

    def test_planner_keeps_protected_rows_and_calendar_capacity(self):
        candidates=rank_candidates(self.state(),date(2026,10,8))
        protected=[{'entry_id':'fixed','date':'2026-10-08','minutes':20,'completed':False,'manual':True,'fixed':True}]
        rows=build_strategy_plan('p',candidates,[60]*7,'2026-10-08','2026-10-09',50,protected,{'2026-10-08':25})
        self.assertIn(protected[0],rows)
        self.assertEqual(sum(e['minutes'] for e in rows if e['date']=='2026-10-08'),35)
        self.assertEqual(sum(e['minutes'] for e in rows if e['date']=='2026-10-09'),50)  # remaining 10 min is below the 15 min minimum
        self.assertTrue(all(e.get('topic_id') in ('a','b') for e in rows if e['entry_id']!='fixed'))

    def test_scenarios_and_lost_week_do_not_stack_debt_or_write_facts(self):
        state=self.state(); state['strategy_facts']['missed_entries']=[{'entry_id':'past','minutes':600}]
        settings=StrategyScenario(start_date='2026-10-08',end_date='2026-10-21',availability=[120]*7)
        result=preview_strategy(state,date(2026,10,8),settings,[],{},7)
        self.assertFalse(result['facts_changed']); self.assertTrue(result['simulation'])
        self.assertEqual(result['debt']['missed_minutes'],600)
        self.assertEqual(result['scenarios']['A']['minutes'],840)
        self.assertEqual(result['scenarios']['B']['minutes'],315)
        self.assertEqual(result['scenarios']['C']['minutes'],175)
        self.assertTrue(all(e['date']>='2026-10-15' for e in result['scenarios']['A']['entries']))
        self.assertTrue(any(w['code']=='above_recent_pattern' for w in result['scenarios']['A']['load_guard']['warnings']))

    def test_review_interval_respects_due_date_and_safe_limits(self):
        state=self.state(); topic=state['syllabus_graph']['topics'][0]
        topic.update(covered=True,review_due_date='2026-10-10',review_interval_days=2)
        rows=build_strategy_plan('p',[c for c in rank_candidates(state,date(2026,10,8)) if c['id']=='a'],
            [120]*7,'2026-10-08','2026-10-12',50)
        self.assertEqual([e['date'] for e in rows],['2026-10-10','2026-10-12'])
        attempts=[{'correct':True,'date':'2026-10-08','confidence':'guess'}]*50
        review=adaptive_review(attempts,date(2026,10,8),previous_reviews=100,importance=5)
        self.assertTrue(1<=review['interval_days']<=45)
        self.assertIn('não altera domínio',review['reason'])

    def test_projection_requires_full_suggested_initial_cost(self):
        settings=StrategyScenario(start_date='2026-10-08',end_date='2026-10-08',availability=[15]*7)
        result=preview_strategy(self.state(),date(2026,10,8),settings,[],{})
        self.assertEqual(result['scenarios']['A']['new_topics_assuming_completion'],0)
        self.assertEqual(result['scenarios']['A']['projected_coverage'],0)

    def test_calendar_and_preserved_conflicts_are_explicit(self):
        entries=[{'date':'2026-10-08','minutes':30,'completed':True}]
        guard=load_guard(self.state(),entries,[60]*7,{'2026-10-08':45})
        self.assertIn('protected_over_capacity',[w['code'] for w in guard['warnings']])

    def test_small_positive_returns_still_distribute_large_manual_syllabus(self):
        state=self.state(); state['syllabus_graph']['disciplines'][0].update(weight=.1,question_count=None)
        template=state['syllabus_graph']['topics'][0]
        state['syllabus_graph']['topics']=[{**template,'id':f't{i:04d}','topic_key':str(i),
            'question_count':10,'mastery':{'score':90}} for i in range(1000)]
        candidates=rank_candidates(state,date(2026,10,8))
        self.assertTrue(all(c['expected_return']>0 for c in candidates))
        entries=build_strategy_plan('p',candidates,[120]*7,'2026-10-08','2026-10-08',50)
        self.assertEqual(len({e['topic_id'] for e in entries}),3)

    def test_partial_review_finishes_before_starting_its_interval(self):
        state=self.state(); topic=state['syllabus_graph']['topics'][0]
        topic.update(covered=True,review_due_date='2026-10-07',review_interval_days=7)
        candidate=next(c for c in rank_candidates(state,date(2026,10,8)) if c['id']=='a')
        rows=build_strategy_plan('p',[candidate],[15]*7,'2026-10-08','2026-10-19',15)
        self.assertEqual([e['date'] for e in rows],['2026-10-08','2026-10-09','2026-10-16','2026-10-17'])
        self.assertTrue(all(e['minutes']==15 for e in rows))
