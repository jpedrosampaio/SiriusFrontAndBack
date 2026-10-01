import os
import sys
import uuid
import unittest
import asyncio
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
import httpx
from test_activity_regression import load_routes
from simulado_scoring import grade
from study_blueprint import blueprint, assemble


class ExamTests(unittest.TestCase):
    def test_duplicate_answers_rejected_and_blank_not_full_score(self):
        questions = [{'correct_answer': 'A', 'weight': 2}, {'correct_answer': 'B', 'weight': 1}]
        from fastapi import HTTPException
        with self.assertRaises(HTTPException): grade(questions, [{'question_idx': 0, 'selected_answer': 'A'}] * 2)
        result = grade(questions, [{'question_idx': 0, 'selected_answer': 'A'}])
        self.assertEqual(result['score'], 66.7)
        self.assertEqual(result['accuracy'], 50)
        self.assertEqual(result['unanswered'], 1)
        self.assertEqual(result['correct_count'], 1)

    def test_blueprint_exact_counts_and_missing_questions_explained(self):
        from fastapi import HTTPException
        plan = blueprint([{'notebook_id': 'n', 'name': 'Português', 'num_questoes_edital': 2, 'weight': 3}])
        exams = [{'simulado_id': 's', 'questions': [{'question_text': str(i), 'disciplina': 'Português', 'correct_answer': 'A'} for i in range(3)]}]
        result = assemble(plan['distribution'], exams, 'stable')
        self.assertEqual(len(result), 2)
        self.assertTrue(all(q['weight'] == 3 for q in result))
        self.assertEqual(result, assemble(plan['distribution'], exams, 'stable'))
        with self.assertRaises(HTTPException): assemble(plan['distribution'], [], 's')
        self.assertFalse(blueprint([{'notebook_id': 'n', 'name': 'Português'}])['complete'])




if __name__ == '__main__': unittest.main()
