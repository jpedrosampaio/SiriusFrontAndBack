"""Transparent planning adjustments based on recorded answers, never AI estimates."""
from datetime import date, timedelta


def next_review(today, total, correct):
    if total < 1 or not 0 <= correct <= total:
        raise ValueError('Invalid answer counts')
    accuracy = correct / total
    interval = 1 if accuracy < .6 else 7 if accuracy < .85 else 21
    return (date.fromisoformat(today) + timedelta(days=interval)).isoformat()


def adapt_notebooks(notebooks, performance, overdue):
    result = []
    for source in notebooks:
        item = dict(source)
        stats = performance.get(item['notebook_id'], {})
        total, correct = stats.get('total', 0), stats.get('correct', 0)
        factor = 1 + (1 - min(1, max(0, correct / total))) if total >= 5 else 1
        reasons = []
        if total >= 5:
            reasons.append(f'{round(correct / total * 100)}% de acertos em {total} questões')
        if item['notebook_id'] in overdue:
            factor += .25
            reasons.append('há blocos pendentes anteriores ao início do plano')
        item['weight'] = max(.1, float(item.get('weight') or 1)) * factor
        item['planning_reason'] = '; '.join(reasons) or 'peso da disciplina; sem amostra suficiente de questões'
        result.append(item)
    return result
