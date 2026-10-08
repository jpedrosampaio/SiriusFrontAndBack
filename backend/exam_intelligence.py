"""Execution diagnostics from recorded facts; no independent mastery score."""
from collections import defaultdict


def post_mortem(result, duration_seconds, duration_minutes=None, recurring_ids=()):
    groups=defaultdict(lambda:{'questions':0,'timed_questions':0,'seconds':0,'wrong':0,'blank':0,'points_lost':0})
    confidence=defaultdict(lambda:{'answered':0,'correct':0})
    wrong_ids=[]; slow=[]
    speed={name:defaultdict(lambda:{'samples':0,'seconds':0}) for name in ('topic','question_type')}
    budget=duration_minutes*60/result['total_questions'] if duration_minutes else None
    for a in result['answers']:
        g=groups[a['disciplina']];g['questions']+=1
        g['blank']+=int(not a['answered']);g['wrong']+=int(a['answered'] and not a['is_correct'])
        g['points_lost']+=a['weight']-a.get('points',a['weight'] if a['is_correct'] else 0)
        if a.get('seconds') is not None:
            g['timed_questions']+=1;g['seconds']+=a['seconds']
            if budget and a['seconds']>budget:slow.append(a['question_idx'])
            for name in speed:
                key=a.get(name) or 'unknown';speed[name][key]['samples']+=1;speed[name][key]['seconds']+=a['seconds']
        if a['answered'] and a.get('confidence'):
            c=confidence[a['confidence']];c['answered']+=1;c['correct']+=int(a['is_correct'])
        if a['answered'] and not a['is_correct']:wrong_ids.append(a.get('question_id'))
    for g in groups.values():
        g['mean_seconds']=round(g['seconds']/g['timed_questions'],1) if g['timed_questions'] else None
        g['points_lost']=round(g['points_lost'],3)
    for c in confidence.values():c['accuracy']=round(100*c['correct']/c['answered'],1)
    for groups_by_key in speed.values():
        for v in groups_by_key.values():v['mean_seconds']=round(v['seconds']/v['samples'],1)
    return {'version':'exam-diagnostics-1','by_discipline':dict(groups),'confidence':dict(confidence),
        'slow_question_indexes':slow,'reference_seconds_per_question':budget,
        'time_overrun':bool(duration_minutes and duration_seconds>duration_minutes*60),
        'repeated_wrong_question_ids':sorted(set(wrong_ids)&set(recurring_ids)),
        'changed_answers':sum(a.get('changed_answer') is True for a in result['answers']),
        'speed_profile':{key:dict(value) for key,value in speed.items()},
        'notice':'Tempo e confiança são evidências declaradas. Lentidão relativa ao orçamento não comprova causa do erro. Revise erros no banco existente; domínio e prioridades usam as mesmas respostas canônicas.'}


def final_sprint(state, candidates, today):
    raw=state.get('exam_date')
    from datetime import date
    days=(date.fromisoformat(raw)-today).days if raw else None
    stage=next((n for n in (2,7,14,30,90) if days is not None and 0<=days<=n),None)
    shares={90:(35,30,20,15),30:(20,35,25,20),14:(10,40,30,20),7:(5,45,35,15),2:(0,50,45,5)}
    return {'days_remaining':days,'stage_days':stage,'proposal_only':True,
        'suggested_percentages':dict(zip(('new_content','questions','review_errors','simulations'),shares[stage])) if stage else None,
        'priorities':candidates[:10],
        'notice':'Proposta operacional, sem alterar agenda, excluir conteúdo ou compromissos. Ajuste ao objetivo pessoal. Na véspera prefira revisão breve e descanso; simulados completos não são obrigatórios.'}
