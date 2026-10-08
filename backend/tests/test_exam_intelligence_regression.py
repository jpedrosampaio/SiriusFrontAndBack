import unittest
from datetime import date,timedelta
from exam_intelligence import final_sprint,post_mortem

class Diagnostics(unittest.TestCase):
    def test_legacy_lowercase_answers_remain_valid(self):
        from types import SimpleNamespace
        from services.exam_sessions import validate_answers
        from simulado_scoring import grade
        questions=[(SimpleNamespace(correct_answer='A',options=['A) First','B) Second']),1)]
        answers=[{'question_idx':0,'selected_answer':'a'}]
        validate_answers(questions,answers)
        self.assertEqual(grade([{'correct_answer':'A','weight':1}],answers)['correct_count'],1)

    def test_penalties_require_source_and_preserve_negative_raw_points(self):
        from fastapi import HTTPException
        from simulado_scoring import grade
        q=[{'correct_answer':'A','weight':2},{'correct_answer':'A','weight':1}]
        with self.assertRaises(HTTPException):grade(q,[],{'wrong_penalty':1})
        r=grade(q,[{'question_idx':0,'selected_answer':'B'}],{'wrong_penalty':1,'blank_penalty':.5,
            'confirmation':'user_confirmed_source','source':'notice page 4','excerpt':'wrong minus one'})
        self.assertEqual(r['raw_points'],-2.5);self.assertEqual(r['score'],0);self.assertEqual(r['unanswered'],1)
        self.assertEqual(r['answers'][0]['points'],-2)
        small=grade([{'correct_answer':'A','weight':.05},{'correct_answer':'A','weight':1}],
            [{'question_idx':0,'selected_answer':'A'}])
        self.assertEqual(small['score'],4.8)
        with self.assertRaises(HTTPException):grade([{'correct_answer':'A','weight':float('inf')}],[])

    def test_canonical_discipline_identity_survives_rename(self):
        from study_blueprint import assemble
        source=[{'simulado_id':'s','questions':[{'question_id':'q','notebook_id':'n','disciplina':'Old name',
            'question_text':'Canonical','correct_answer':'A'}]}]
        result=assemble([{'notebook_id':'n','name':'Renamed','count':1,'weight':2}],source,'seed')
        self.assertEqual(result[0]['question_id'],'q');self.assertEqual(result[0]['weight'],2)
    def test_sprint_boundaries_unknown_and_past_are_read_only(self):
        today=date(2026,10,8)
        for days,stage in ((91,None),(90,90),(31,90),(30,30),(14,14),(7,7),(2,2),(0,2),(-1,None)):
            state={'exam_date':(today+timedelta(days=days)).isoformat()};r=final_sprint(state,[{'id':'canonical'}],today)
            self.assertEqual(r['stage_days'],stage);self.assertTrue(r['proposal_only']);self.assertEqual(r['priorities'],[{'id':'canonical'}])
            if stage:self.assertEqual(sum(r['suggested_percentages'].values()),100)
        self.assertIsNone(final_sprint({},[],today)['suggested_percentages'])
    def test_blank_confidence_time_and_repeat_error_are_distinct(self):
        result={'total_questions':3,'answers':[
            {'question_idx':0,'question_id':'q','disciplina':'A','weight':2,'is_correct':False,'answered':True,'seconds':80,'confidence':'confident','changed_answer':True},
            {'question_idx':1,'question_id':'blank','disciplina':'A','weight':1,'is_correct':False,'answered':False,'seconds':None,'confidence':'confident'},
            {'question_idx':2,'question_id':'ok','disciplina':'B','weight':1,'is_correct':True,'answered':True,'seconds':20,'confidence':'guess'}]}
        p=post_mortem(result,200,3,['q','blank'])
        self.assertEqual(p['repeated_wrong_question_ids'],['q']);self.assertEqual(p['slow_question_indexes'],[0])
        self.assertEqual(p['confidence']['confident']['answered'],1);self.assertEqual(p['by_discipline']['A']['points_lost'],3)
        self.assertEqual(p['by_discipline']['A']['mean_seconds'],80);self.assertTrue(p['time_overrun'])
