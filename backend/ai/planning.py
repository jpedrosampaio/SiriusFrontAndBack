"""Read-only civil-time plan. Fixed items never move; flexible starts round up to 5 minutes."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def plan_day(tasks, commitments, day, start=480, end=1080, capacity=None,
             *, timezone_name='America/Sao_Paulo', now=None, windows=None):
    planned_date = date.fromisoformat(day)
    if not 0 <= start < end <= 1440 or (capacity is not None and not 0 <= capacity <= 1440):
        raise ValueError('Invalid planning window')
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('Current instant must include timezone')
    local = instant.astimezone(ZoneInfo(timezone_name))
    current = (local.hour * 60 + local.minute + (1 if local.second or local.microsecond else 0)) if planned_date == local.date() else (1440 if planned_date < local.date() else 0)
    flex_start = min(end, max(start, ((current + 4) // 5) * 5))
    pending = [t for t in tasks if not t.get('completed')]
    fixed = [{**c, 'kind': 'commitment'} for c in commitments if c.get('date') == day]
    blocks, unscheduled, conflicts = [], [], []
    for task in pending:
        if task.get('scheduled_time') is None:
            continue
        h, m = map(int, task['scheduled_time'].split(':'))
        duration = task.get('duration_minutes') or 30
        block = {'task_id': task.get('task_id'), 'title': task.get('title'),
                 'start_minute': h * 60 + m, 'end_minute': h * 60 + m + duration,
                 'duration_minutes': duration, 'duration_estimated': task.get('duration_minutes') is None,
                 'kind': 'fixed_task', 'past_due': h * 60 + m < current}
        blocks.append(block)
        fixed.append(block)
    fixed.sort(key=lambda b: b['start_minute'])
    conflicts_truncated=False
    for i, item in enumerate(fixed):
        for other in fixed[i + 1:]:
            if other['start_minute'] >= item['end_minute']:
                break
            if len(conflicts)>=50:
                conflicts_truncated=True;break
            conflicts.append({'start_minute': other['start_minute'],
                'end_minute': min(item['end_minute'], other['end_minute']),
                'items': [item.get('task_id') or item.get('event_id'), other.get('task_id') or other.get('event_id')]})
        if conflicts_truncated:break
    ranges = [(start,end)] if windows is None else sorted((w['start_minute'],w['end_minute']) for w in windows)
    if any(not 0<=a<b<=1440 for a,b in ranges) or any(b>c for (_,b),(c,_) in zip(ranges,ranges[1:])):
        raise ValueError('Invalid availability windows')
    gaps=[]
    for lower,upper in ranges:
        cursor=max(((lower+4)//5)*5,flex_start)
        for item in fixed:
            a,b=max(cursor,item['start_minute']),min(upper,item['end_minute'])
            if a>=b:continue
            if a>cursor:gaps.append([cursor,a])
            cursor=max(cursor,((b+4)//5)*5)
        if cursor<upper:gaps.append([cursor,upper])
    available = sum(b - a for a, b in gaps)
    capacity = available if capacity is None else min(capacity, available)
    budget = capacity
    def priority(task):
        deadline = task.get('deadline') or task.get('date') or day
        return (-int(deadline < day), -int(task.get('date_locked',False)), -{'high': 3, 'medium': 2, 'low': 1}.get(task.get('priority'), 2), deadline, str(task.get('task_id', '')))
    for task in sorted((t for t in pending if t.get('scheduled_time') is None), key=priority):
        duration = task.get('duration_minutes') or 30
        metadata={k:task[k] for k in ('domain','source_id','candidate_id','link','reasons','date_locked','duration_origin') if k in task}
        if task.get('duration_origin')=='unknown':
            unscheduled.append({'task_id':task.get('task_id'),'title':task.get('title'),**metadata,'reason':'Informe a duração antes de alocar.'})
            continue
        gap = next((g for g in gaps if g[1] - g[0] >= duration), None)
        if duration > capacity or gap is None:
            unscheduled.append({'task_id': task.get('task_id'), 'title': task.get('title'), **metadata, 'reason': 'Sem capacidade livre suficiente.'})
            continue
        blocks.append({'task_id': task.get('task_id'), 'title': task.get('title'), 'kind': 'flexible_task', **metadata,
            'start_minute': gap[0], 'end_minute': gap[0] + duration, 'duration_minutes': duration,
            'duration_estimated': task.get('duration_origin')=='user_estimate' or task.get('duration_minutes') is None,
            'reason': 'Prioridade por prazo vencido, data protegida e prioridade declarada; alocação em tempo livre.' if metadata else 'Sugestão nos horários livres restantes.'})
        gap[0] = ((gap[0]+duration+4)//5)*5
        capacity -= duration
        capacity=min(capacity,sum(max(0,b-a) for a,b in gaps))
    blocks.sort(key=lambda b: b['start_minute'])
    return {'date': day, 'timezone': timezone_name, 'blocks': blocks, 'unscheduled': unscheduled,
        'conflicts': conflicts, 'conflicts_truncated':conflicts_truncated, 'available_minutes': available, 'budget_minutes': budget,
        'remaining_minutes': capacity, 'window': {'start_minute': start, 'end_minute': end,
        'remaining_start_minute': flex_start}, 'preview': True}
