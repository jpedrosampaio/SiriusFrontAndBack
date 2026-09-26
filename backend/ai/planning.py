"""Deterministic planning: no model chooses capacity or moves appointments."""
from datetime import date


def plan_day(tasks, commitments, day, start=480, end=1080, capacity=240):
    date.fromisoformat(day)
    if not 0 <= start < end <= 1440 or not 0 <= capacity <= 1440:
        raise ValueError('Invalid planning window')
    occupied = sorted((max(start, int(c['start_minute'])), min(end, int(c['end_minute']))) for c in commitments if c.get('date') == day and int(c['start_minute']) < end and int(c['end_minute']) > start)
    gaps, conflicts, cursor = [], [], start
    for a, b in occupied:
        if a < cursor: conflicts.append({'start_minute': a, 'end_minute': min(cursor, b)})
        if a > cursor: gaps.append([cursor, a])
        cursor = max(cursor, b)
    if cursor < end: gaps.append([cursor, end])
    def priority(t):
        deadline = t.get('deadline') or t.get('date') or day
        overdue = deadline < day
        return (-int(overdue), -{'high': 3, 'medium': 2, 'low': 1}.get(t.get('priority'), 2), deadline, str(t.get('task_id', '')))
    blocks, unscheduled = [], []
    for task in sorted((t for t in tasks if not t.get('completed')), key=priority):
        duration = task.get('duration_minutes') or 30
        duration = max(5, min(480, int(duration)))
        gap = next((g for g in gaps if g[1]-g[0] >= duration), None)
        if duration > capacity or not gap:
            unscheduled.append({'task_id': task.get('task_id'), 'title': task.get('title'), 'reason': 'Sem capacidade livre suficiente.'})
            continue
        blocks.append({'task_id': task.get('task_id'), 'title': task.get('title'), 'start_minute': gap[0], 'end_minute': gap[0]+duration, 'duration_minutes': duration, 'duration_estimated': not bool(task.get('duration_minutes')), 'reason': 'Prazo, prioridade e disponibilidade; compromissos fixos preservados.'})
        gap[0] += duration
        capacity -= duration
    return {'date': day, 'blocks': blocks, 'unscheduled': unscheduled, 'conflicts': conflicts, 'remaining_minutes': capacity, 'preview': True}
