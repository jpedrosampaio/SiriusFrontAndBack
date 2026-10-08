"""Deterministic dated study blocks; official content is never invented by the planner."""
from collections import defaultdict
from datetime import date, timedelta
import hashlib


def build_strategy_plan(program_id, candidates, availability, start, end, block_minutes, preserved=(), reserved=None):
    """Fit ranked candidates into a fixed budget; never add missed minutes to a day."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    result = [dict(e) for e in preserved]
    identities = {e['entry_id'] for e in preserved}
    used = defaultdict(int)
    for e in preserved: used[e['date']] += e['minutes']
    allocated = defaultdict(int)
    review_progress = defaultdict(int)
    review_next = {}
    serial = 0
    for offset in range(max(0, (last - first).days + 1)):
        day = first + timedelta(days=offset); iso = day.isoformat()
        budget = max(0, availability[day.weekday()] - used[iso] - (reserved or {}).get(iso, 0))
        while budget >= 15:
            eligible = [c for c in candidates if c['kind'] != 'Revisão' or
                day >= review_next.get(c['id'], date.fromisoformat(c['review_due_date']) if c['review_due_date'] else first)]
            if not eligible: break
            candidate = min(eligible, key=lambda c: (-c['expected_return'] / (1 + allocated[c['id']] / c['cost_minutes']), c['id']))
            minutes = min(block_minutes, candidate['cost_minutes'], budget)
            allocated[candidate['id']] += minutes
            if candidate['kind'] == 'Revisão':
                review_progress[candidate['id']] += minutes
                if review_progress[candidate['id']] >= candidate['cost_minutes']:
                    review_next[candidate['id']] = day + timedelta(days=candidate['review_interval_days'])
                    review_progress[candidate['id']] = 0
            serial += 1
            identity = hashlib.sha256(f'{program_id}:{iso}:{serial}:{candidate["id"]}:strategy'.encode()).hexdigest()[:24]
            while identity in identities: identity += '-next'
            identities.add(identity)
            result.append({'entry_id': identity, 'date': iso, 'notebook_id': candidate['notebook_id'],
                'topic_id': candidate['id'], 'topic_key': candidate['topic_key'],
                'name': f'{candidate["discipline"]} · {candidate["title"]}', 'minutes': minutes,
                'kind': candidate['kind'], 'completed': False, 'manual': False, 'fixed': False,
                'reason': '; '.join(candidate['reasons']), 'suggested_break': minutes >= 50})
            budget -= minutes
    return sorted(result, key=lambda e: (e['date'], e['entry_id']))


def build_plan(program_id, notebooks, availability, start, end, block_minutes, completed=(), reserved=None):
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
        budget = max(0, availability[day.weekday()] - used[iso] - (reserved or {}).get(iso, 0))
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
                           'name': nb.get('name', ''), 'minutes': minutes, 'kind': kind, 'completed': False,
                           'reason': nb.get('planning_reason', '')})
            budget -= minutes
    return sorted(result, key=lambda row: (row['date'], row.get('entry_id', '')))
