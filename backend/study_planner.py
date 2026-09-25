"""Deterministic dated study blocks; official content is never invented by the planner."""
from collections import defaultdict
from datetime import date, timedelta
import hashlib


def build_plan(program_id, notebooks, availability, start, end, block_minutes, completed=()):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    result = [dict(item) for item in completed]
    used = defaultdict(int)
    for item in completed:
        used[item['date']] += item['minutes']
    allocation = defaultdict(int)
    reviews = []
    serial = 0
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        iso = day.isoformat()
        budget = max(0, availability[day.weekday()] - used[iso])
        while budget >= 15 and notebooks:
            due = next((item for item in reviews if item['due'] <= day), None)
            if due:
                nb, kind = due['nb'], 'Revisão'
                reviews.remove(due)
                minutes = min(25, budget)
            else:
                nb = min(notebooks, key=lambda n: (allocation[n['notebook_id']] / max(.1, float(n.get('weight') or 1)), n['notebook_id']))
                kind, minutes = 'Teoria e questões', min(block_minutes, budget)
                allocation[nb['notebook_id']] += minutes
                for interval in (7, 21):
                    if day + timedelta(days=interval) <= end:
                        reviews.append({'due': day + timedelta(days=interval), 'nb': nb})
            serial += 1
            entry_id = hashlib.sha256(f'{program_id}:{iso}:{serial}:{nb["notebook_id"]}:{kind}'.encode()).hexdigest()[:24]
            # A regenerated plan must not reuse an identifier from completed history.
            while any(item['entry_id'] == entry_id for item in result):
                entry_id += '-next'
            result.append({'entry_id': entry_id, 'date': iso, 'notebook_id': nb['notebook_id'],
                           'name': nb.get('name', ''), 'minutes': minutes, 'kind': kind, 'completed': False})
            budget -= minutes
    return sorted(result, key=lambda row: (row['date'], row.get('entry_id', '')))
