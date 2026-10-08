"""Deterministic dated study blocks; official content is never invented by the planner."""
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import heapq


def build_strategy_plan(program_id, candidates, availability, start, end, block_minutes, preserved=(), reserved=None):
    """Allocate incrementally, crediting protected work only on its scheduled date."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    result = [dict(e) for e in preserved]
    identities = {e['entry_id'] for e in preserved}
    used, protected = defaultdict(int), defaultdict(list)
    by_id = {c['id']: c for c in candidates}
    topic_ids = {c.get('topic_id', c['id']): c['id'] for c in candidates if c.get('scope') != 'discipline'}
    discipline_ids = {c['notebook_id']: c['id'] for c in candidates if c.get('scope') == 'discipline'}
    for e in preserved:
        used[e['date']] += e['minutes']
        cid = topic_ids.get(e.get('topic_id')) or (discipline_ids.get(e.get('notebook_id')) if not e.get('topic_id') else None)
        if cid: protected[e['date']].append((cid, e['minutes']))
    allocated, progress, versions = defaultdict(int), defaultdict(int), defaultdict(int)
    ready = {c['id']: max(first, date.fromisoformat(c['review_due_date']))
        if c['kind'] == 'Revis\u00e3o' and c.get('review_due_date') else first for c in candidates}
    active, deferred = [], []

    def enqueue(cid, day):
        c = by_id[cid]
        if ready[cid] > day:
            heapq.heappush(deferred, (ready[cid], cid, versions[cid]))
        else:
            priority = -c['expected_return'] / (1 + allocated[cid] / c['cost_minutes'])
            heapq.heappush(active, (priority, cid, versions[cid]))

    def consume(cid, minutes, day):
        c = by_id[cid]
        allocated[cid] += minutes
        if c.get('scope') != 'discipline':
            progress[cid] += minutes
            if progress[cid] >= c['cost_minutes']:
                interval = c['review_interval_days'] if c['kind'] == 'Revis\u00e3o' else 1
                ready[cid] = max(ready[cid], day + timedelta(days=interval))
                progress[cid] = 0
        versions[cid] += 1
        enqueue(cid, day)

    for cid in by_id: enqueue(cid, first)
    serial = 0
    for offset in range(max(0, (last - first).days + 1)):
        day = first + timedelta(days=offset); iso = day.isoformat()
        while deferred and deferred[0][0] <= day:
            _, cid, version = heapq.heappop(deferred)
            if version == versions[cid]: enqueue(cid, day)
        for cid, minutes in protected[iso]: consume(cid, minutes, day)
        budget = max(0, availability[day.weekday()] - used[iso] - (reserved or {}).get(iso, 0))
        while budget >= 15 and active:
            _, cid, version = heapq.heappop(active)
            if version != versions[cid]: continue
            candidate = by_id[cid]
            remaining = max(15, candidate['cost_minutes'] - progress[cid])
            minutes = min(block_minutes, budget, remaining) if candidate.get('scope') != 'discipline' else min(block_minutes, budget)
            consume(cid, minutes, day)
            serial += 1
            identity = hashlib.sha256(f'{program_id}:{iso}:{serial}:{cid}:strategy'.encode()).hexdigest()[:24]
            while identity in identities: identity += '-next'
            identities.add(identity)
            result.append({'entry_id': identity, 'date': iso, 'notebook_id': candidate['notebook_id'],
                'candidate_id': cid, 'topic_id': candidate.get('topic_id', cid), 'topic_key': candidate['topic_key'],
                'name': f'{candidate["discipline"]} \u00b7 {candidate["title"]}', 'minutes': minutes,
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
