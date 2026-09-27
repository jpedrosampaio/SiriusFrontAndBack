"""Build exam distributions from recorded edital counts, never guessed percentages."""
import hashlib
import random
import unicodedata
from fastapi import HTTPException


def normalize(value):
    return unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().casefold().strip()


def blueprint(notebooks):
    rows = []
    for nb in notebooks:
        count = nb.get('num_questoes_edital')
        try: count = int(count)
        except (ValueError, TypeError): count = 0
        if count <= 0: continue
        rows.append({'notebook_id': nb['notebook_id'], 'name': nb.get('name', ''), 'count': count, 'weight': float(nb.get('weight') or 1), 'provenance': 'extracted'})
    return {'distribution': rows, 'total': sum(r['count'] for r in rows), 'complete': bool(rows) and len(rows) == len(notebooks),
            'notice': 'Distribuição extraída dos registros do edital; confira a análise e os pesos antes de usar.'}


def assemble(distribution, exams, seed):
    rng, selected, seen = random.Random(seed), [], set()
    for item in distribution:
        candidates = []
        for exam in exams:
            for index, q in enumerate(exam.get('questions', [])):
                if normalize(q.get('disciplina', '')) != normalize(item['name']) or not q.get('correct_answer'): continue
                digest = hashlib.sha256((str(q.get('question_text', '')) + str(q.get('options', []))).encode()).hexdigest()
                if digest in seen: continue
                seen.add(digest)
                candidate = {**q, 'weight': item['weight'], 'notebook_id': item['notebook_id'], 'source_simulado_id': exam['simulado_id'], 'source_question_index': index}
                if q.get('notebook_id') != item['notebook_id']: candidate.pop('topic_key', None)
                candidates.append(candidate)
        if len(candidates) < item['count']:
            raise HTTPException(422, f"{item['name']}: são necessárias {item['count']} questões com gabarito; há {len(candidates)} disponíveis. Importe ou gere mais questões dessa disciplina.")
        rng.shuffle(candidates)
        selected.extend(candidates[:item['count']])
    return [{**q, 'question_number': i + 1} for i, q in enumerate(selected)]
