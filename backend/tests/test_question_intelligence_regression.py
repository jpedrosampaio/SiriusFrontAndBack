import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from question_intelligence import error_bank,forensic_clusters,question_origin,validate_generated_question,canonical_generated_answer,PROVIDERS


class QuestionIntelligenceTests(unittest.TestCase):
    def row(self,index,correct=False,question_id='q1'):
        return {'attempt_id':str(index),'notebook_id':'n1','topic_key':'0','title':'Topic',
            'internal_question_id':question_id,'question':'Conceito tributário '+question_id,'correct':correct,
            'date':f'2026-10-{index:02d}','answered_at':f'2026-10-{index:02d}T12:00:00Z','error_reason':'forgot'}

    def test_recovery_requires_later_same_question_and_new_failure_resets(self):
        rows=[self.row(1),self.row(2,True,'q2')]
        self.assertEqual(error_bank(rows)['recovery_rate'],0)
        rows.append(self.row(3,True));self.assertEqual(error_bank(rows)['recovery_rate'],100)
        rows.append(self.row(4));self.assertEqual(error_bank(rows)['recovery_rate'],0)

    def test_clusters_require_distinct_question_text_and_are_only_suggestions(self):
        duplicate=[{**self.row(i,question_id='q'+str(i)),'question':'Same question'} for i in (1,2,3)]
        self.assertEqual(forensic_clusters(duplicate),[])
        cluster=forensic_clusters([self.row(i,question_id='q'+str(i)) for i in (1,2,3)])[0]
        self.assertEqual(cluster['question_count'],3);self.assertEqual(cluster['classification'],'suggestion')
        self.assertEqual(cluster['reason'],'memory');self.assertEqual(len(cluster['attempt_ids']),3)

    def test_provenance_never_promotes_ai_or_unverified_official(self):
        self.assertEqual(question_origin('ai_generated',{'official_evidence_verified':True}),'ai_generated')
        self.assertEqual(question_origin('official'),'unknown')
        self.assertEqual(question_origin('official',{'official_evidence_verified':True}),'official')
        self.assertEqual(question_origin('pdf_import'),'imported')
        self.assertFalse(PROVIDERS['future_external_provider'].available)

    def test_generated_validation_rejects_ambiguous_answer_and_low_confidence(self):
        valid={'question_text':'What?','options':['A) First','B) Second'],'correct_answer':'A','explanation':'Reason'}
        self.assertTrue(validate_generated_question(valid))
        for change in ({'correct_answer':'E'},{'correct_answer':'AB'},{'options':['A) Same','B) Same']},
            {'options':['B) First','A) Second']},{'options':['A) First','A) Second']},
            {'explanation':''},{'question_text':'   '},{'validation_confidence':'low'},{'question_text':{'bad':'type'}}):
            self.assertFalse(validate_generated_question({**valid,**change}))

    def test_textual_answers_match_the_same_protocol_as_exam_selection(self):
        question={'options':['A) Paris','B) Rome'],'correct_answer':'Paris'}
        self.assertEqual(canonical_generated_answer(question),'A')
        self.assertEqual(canonical_generated_answer({**question,'correct_answer':'B) Rome'}),'B')
        self.assertEqual(canonical_generated_answer({**question,'correct_answer':'b'}),'B')
        self.assertEqual(canonical_generated_answer({'options':['Certo','Errado'],'type':'certo_errado','correct_answer':'certo'}),'Certo')
        self.assertIsNone(canonical_generated_answer({**question,'correct_answer':'unknown'}))
