"""Coordinator: bounded owner-scoped state and the existing daily allocator."""
import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from pydantic import ValidationError
from db.models.identity import User
from db.session import unit_of_work
from life_contracts import Availability, LifeState, Scenario
from services.life_adapters import ADAPTERS
from ai.planning import plan_day


async def collect(session, uid, *, day=None, now=None, user=None):
    user=user or await session.get(User,uid)
    if user is None:raise HTTPException(404,'User not found')
    instant=now or datetime.now(timezone.utc)
    if instant.tzinfo is None:raise ValueError('Timezone-aware instant required')
    zone=ZoneInfo(user.timezone); local=instant.astimezone(zone)
    day=day or local.date()
    if not local.date()<=day<=local.date()+timedelta(days=30):
        raise HTTPException(422,'Planeje entre hoje e os próximos 30 dias.')
    warnings=[]
    try:availability=Availability.model_validate((user.preferences or {}).get('life_availability',{}))
    except ValidationError:
        availability=Availability();warnings.append('Disponibilidade inválida; configure novamente.')
    domains=[await adapter(session,uid,day,zone) for adapter in ADAPTERS]
    for domain in domains:
        if domain.domain=='training' and not domain.facts.get('active_session'):
            domain.candidates=[c for c in domain.candidates if c.source_id==str(availability.training_plan_id)
                and day.weekday() in availability.training_weekdays]
        for c in domain.candidates:
            estimate=availability.duration_estimates.get(c.domain)
            if c.duration_minutes is None and estimate:
                c.duration_minutes=estimate;c.duration_origin='user_estimate';c.reasons.append('Duração estimada por você nas preferências.')
    transition=datetime.combine(day,time(),zone).utcoffset()!=datetime.combine(day+timedelta(days=1),time(),zone).utcoffset()
    unsafe=any(d.truncated or (d.domain=='tasks' and d.facts.get('unknown_fixed_duration')) or
        (d.domain=='preparation' and d.warnings) for d in domains) or transition
    if transition:warnings.append('Dia com mudança de fuso/horário: alocação automática suspensa.')
    if any(d.truncated for d in domains):warnings.append('Limite de dados atingido; alocação suspensa para não ignorar restrições.')
    if not availability.weekdays[day.weekday()]:warnings.append('Informe sua disponibilidade real para este dia.')
    if any(d.domain=='tasks' and d.facts.get('unknown_fixed_duration') for d in domains):
        warnings.append('Defina a duração das tarefas com horário fixo antes de planejar.')
    raw={'owner':str(uid),'date':str(day),'timezone':user.timezone,'availability':availability.model_dump(mode='json'),
        'domains':[d.model_dump(mode='json') for d in domains]}
    digest=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return LifeState(date=day,timezone=user.timezone,availability=availability,domains=domains,
        fingerprint=digest,planning_safe=not unsafe,warnings=warnings)


async def snapshot(uid, *, day=None, now=None):
    async with unit_of_work() as session:
        # A coherent snapshot across adapters; no interleaved module writes.
        from sqlalchemy import text
        await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        return await collect(session,UUID(str(uid)),day=day,now=now)


def preview(state, scenario=None, *, now=None):
    scenario=scenario or Scenario(date=state.date)
    windows=scenario.windows if scenario.windows is not None else state.availability.weekdays[state.date.weekday()]
    accepted=set(next(d for d in state.domains if d.domain=='calendar').facts['accepted_candidate_ids'])
    candidates=[c for d in state.domains for c in d.candidates if c.id not in accepted]
    identities={c.id for c in candidates}
    if not set(scenario.exclude).issubset(identities) or not set(scenario.durations).issubset(identities):
        raise HTTPException(422,'O cenário contém candidatos indisponíveis nesta conta/data.')
    if any(c.date_locked and c.id in scenario.exclude for c in candidates):
        raise HTTPException(422,'Blocos com data protegida não podem ser excluídos do cenário.')
    constraints=[c for d in state.domains for c in d.constraints]
    items=[]
    for c in candidates:
        if c.id in scenario.exclude:continue
        duration=scenario.durations.get(c.id,c.duration_minutes)
        if c.date_locked and duration!=c.duration_minutes:raise HTTPException(422,'Não altere a duração de blocos protegidos.')
        items.append({'task_id':c.id,'candidate_id':c.id,'source_id':c.source_id,'domain':c.domain,'title':c.title,
            'duration_minutes':duration,'duration_origin':'user_estimate' if c.id in scenario.durations else c.duration_origin,
            'date':str(c.latest),'deadline':str(c.latest),'date_locked':c.date_locked,'priority':c.priority,
            'reasons':c.reasons,'link':c.link})
    fixed=[{'event_id':c.id,'date':str(state.date),**c.model_dump()} for c in constraints]
    result=plan_day(items,fixed,str(state.date),0,1440,scenario.capacity_minutes,timezone_name=state.timezone,
        now=now,windows=[w.model_dump() for w in windows] if state.planning_safe else [])
    result.update({'fingerprint':state.fingerprint,'version':'global-planner/1','planning_safe':state.planning_safe,
        'availability_origin':'scenario' if scenario.windows is not None else 'user_declared',
        'constraints':[c.model_dump() for c in constraints],'warnings':state.warnings,
        'scenario':scenario.model_dump(mode='json'),'apply_requires_confirmation':True})
    return result


async def daily(uid, *, day=None, scenario=None, now=None):
    state=await snapshot(uid,day=day,now=now)
    return {'state':state.model_dump(mode='json'),'plan':preview(state,scenario,now=now)}


def agent_context(state):
    """Small factual prompt projection; capacity was computed from ALL constraints."""
    raw=state.model_dump(mode='json') if isinstance(state,LifeState) else state
    domains=[]
    for d in raw['domains']:
        facts={k:(v[:5] if isinstance(v,list) else v) for k,v in d['facts'].items()}
        domains.append({'domain':d['domain'],'facts':facts,'candidates':[
            {'id':c['id'],'title':c['title'][:120],'duration_minutes':c['duration_minutes'],'duration_origin':c['duration_origin'],
             'latest':c['latest'],'reasons':c['reasons'][:2],'link':c['link']} for c in d['candidates'][:3]],
            'constraints_count':len(d['constraints']),'display_limited':len(d['candidates'])>3,'truncated':d['truncated']})
    return {'version':raw['version'],'date':raw['date'],'timezone':raw['timezone'],'domains':domains,
        'planning_safe':raw['planning_safe'],'warnings':raw['warnings']}


def agent_plan(plan):
    result={k:v for k,v in plan.items() if k not in ('scenario','constraints','blocks','unscheduled','conflicts')}
    result.update(blocks=plan['blocks'][:10],unscheduled=plan['unscheduled'][:10],conflicts=plan['conflicts'][:10],
        constraints_count=len(plan['constraints']),display_limited=any(len(plan[k])>10 for k in ('blocks','unscheduled','conflicts')))
    return result
