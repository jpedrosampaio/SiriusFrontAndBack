"""Versioned, deterministic estimates. Coverage and self-confidence are not mastery."""
from datetime import date, timedelta
from math import exp, sqrt

VERSION = 'sirius-mastery-1'


def mastery(attempts, today=None):
    today = today or date.today()
    rows = [a for a in attempts if isinstance(a.get('correct'), bool)]
    if not rows:
        return {'score': None, 'confidence': 'insufficient', 'samples': 0, 'accuracy': None, 'version': VERSION,
                'reason': 'Sem questões individuais respondidas; exposição não comprova domínio.'}
    weighted_correct = weighted_total = 0.0
    for row in rows:
        age = max(0, (today - date.fromisoformat(row['date'][:10])).days)
        weight = exp(-age / 60)
        weighted_total += weight
        weighted_correct += weight * int(row['correct'])
    # Beta(2,2) prior: small samples never imply certainty. Recency shrinks stale
    # evidence toward 50%, rather than inventing new incorrect answers.
    estimate = (weighted_correct + 2) / (weighted_total + 4)
    n = len(rows)
    margin = min(.5, 1.96 * sqrt(estimate * (1 - estimate) / (weighted_total + 4)))
    return {'score': round(100 * estimate), 'confidence': 'high' if weighted_total >= 40 else 'medium' if weighted_total >= 15 else 'low',
            'samples': n, 'effective_samples': round(weighted_total, 1), 'accuracy': round(sum(r['correct'] for r in rows) / n * 100, 1),
            'range': [round(max(0, estimate - margin) * 100), round(min(1, estimate + margin) * 100)],
            'version': VERSION, 'reason': f'{n} respostas; evidências antigas têm menor peso. Estimativa, não previsão de aprovação.'}


def adaptive_review(attempts, today=None, previous_reviews=0, difficulty=None):
    today = today or date.today()
    result = mastery(attempts, today)
    score = result['score']
    recent = sorted(attempts, key=lambda a: a.get('created_at') or a.get('date', ''), reverse=True)[:5]
    recent_errors = sum(a.get('correct') is False for a in recent)
    if score is None:
        interval, reason = 1, 'Sem amostra; revisão inicial sugerida.'
    elif recent_errors >= 2 or score < 60:
        interval, reason = 1, 'Erros recentes ou domínio estimado abaixo de 60%.'
    elif score < 80 or result['samples'] < 10:
        interval, reason = 7, 'Consolidar conhecimento; amostra ou acertos ainda limitados.'
    else:
        interval, reason = min(45, 14 + max(0, previous_reviews) * 3), 'Bom desempenho sustentado; ampliar o intervalo gradualmente.'
    if difficulty == 'hard':
        interval = max(1, interval // 2)
        reason += ' Dificuldade alta reduz o intervalo.'
    return {'due_date': (today + timedelta(days=interval)).isoformat(), 'interval_days': interval, 'reason': reason, 'mastery': result}


def topic_priority(*, weight=1, question_count=None, estimate=None, errors=0, overdue=False, studied=False, days_left=None):
    official = max(.1, min(float(weight or 1), 100))
    incidence = max(1, min(int(question_count or 1), 200))
    gap = 1 - (estimate if estimate is not None else 50) / 100
    urgency = 1.25 if days_left is not None and 0 <= days_left <= 30 else 1
    score = official * incidence * (1 + gap + min(errors, 10) / 10 + .5 * overdue + .25 * (not studied)) * urgency
    reasons = [f'peso {official:g}', 'sem amostra de domínio' if estimate is None else f'domínio estimado {estimate}%']
    if overdue: reasons.append('revisão vencida')
    if not studied: reasons.append('conteúdo ainda não estudado')
    if errors: reasons.append(f'{errors} erros registrados')
    return {'priority': round(score, 2), 'reasons': reasons}
