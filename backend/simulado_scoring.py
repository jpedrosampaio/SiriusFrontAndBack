"""Deterministic grading and atomic evidence ingestion for owned simulations."""
from collections import defaultdict
from fastapi import HTTPException


def grade(questions, answers):
    if not questions or len(questions) > 500: raise HTTPException(422, 'Simulado sem questões válidas ou acima do limite.')
    selected = {}
    for answer in answers:
        index = answer.get('question_idx')
        value = answer.get('selected_answer')
        if type(index) is not int or not 0 <= index < len(questions) or index in selected or not isinstance(value, str) or len(value) > 100:
            raise HTTPException(422, 'Respostas duplicadas ou inválidas.')
        selected[index] = value.strip()
    results, disciplines, topics = [], defaultdict(lambda: {'total': 0, 'correct': 0}), defaultdict(lambda: {'total': 0, 'correct': 0})
    earned = total_weight = 0
    for index, q in enumerate(questions):
        expected = str(q.get('correct_answer') or '').strip()
        if not expected: raise HTTPException(422, 'Uma questão não tem gabarito. Confira a prova antes de responder.')
        answer = selected.get(index, '')
        correct = bool(answer) and answer.upper() == expected.upper()
        weight = max(.1, min(float(q.get('weight') or 1), 100))
        total_weight += weight
        if correct: earned += weight
        disc = q.get('disciplina') or 'Geral'
        topic = q.get('subdisciplina') or 'Sem tópico vinculado'
        for counter, key in [(disciplines, disc), (topics, topic)]:
            counter[key]['total'] += 1
            counter[key]['correct'] += int(correct)
        results.append({'question_idx': index, 'question_number': q.get('question_number', index + 1), 'selected_answer': answer,
                        'correct_answer': expected, 'is_correct': correct, 'answered': bool(answer), 'explanation': q.get('explanation', ''),
                        'disciplina': disc, 'topic': topic, 'weight': weight})
    for counter in (disciplines, topics):
        for v in counter.values(): v['accuracy'] = round(v['correct'] / v['total'] * 100, 1)
    return {'answers': results, 'correct_count': sum(r['is_correct'] for r in results), 'total_questions': len(questions),
            'total_answered': sum(r['answered'] for r in results), 'unanswered': sum(not r['answered'] for r in results),
            'score': round(100 * earned / total_weight, 1), 'accuracy': round(100 * sum(r['is_correct'] for r in results) / len(questions), 1),
            'by_disciplina': dict(disciplines), 'by_topic': dict(topics), 'score_basis': 'all_questions_weighted'}
