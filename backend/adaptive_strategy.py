"""Pure operational rankings. No LLM, calendar writes or approval probabilities."""
from collections import Counter
from datetime import date, timedelta
from math import exp
from study_planner import build_strategy_plan

VERSION = 'adaptive-strategy-1'


def rank_candidates(state, today):
    graph = state['syllabus_graph']
    disciplines = {d['id']: d for d in graph['disciplines']}
    counts = Counter(t['notebook_id'] for t in graph['topics'])
    candidates = []
    days = state.get('days_remaining')
    for topic in graph['topics']:
        discipline = disciplines[topic['notebook_id']]
        score = topic['mastery']['score']
        samples = topic['question_count']
        last = topic.get('last_answer_date')
        age = max(0, (today - date.fromisoformat(last)).days) if last else None
        decay = round(10 * (1 - exp(-age / 60)), 2) if age is not None else 0
        due = topic.get('review_due_date')
        overdue = bool(due and due <= today.isoformat())
        errors = topic.get('recent_errors', 0)
        trend = topic.get('accuracy_change')
        components = {
            'coverage': 0 if topic['covered'] else 15,
            'mastery_gap': round(30 * (1 - (score if score is not None else 50) / 100), 2),
            'recent_errors': min(15, errors * 3), 'review_due': 15 if overdue else 0,
            'evidence_age': decay, 'insufficient_evidence': 10 if samples < 5 else 0,
            'declining_accuracy': 5 if trend is not None and trend < -10 else 0,
        }
        urgency = 1.2 if days is not None and 0 <= days <= 30 else 1
        risk = round(min(100, sum(components.values()) * urgency), 2)
        weight = max(.1, min(100, float(discipline.get('weight') or 1)))
        incidence = max(1, min(200, discipline.get('question_count') or 1)) / max(1, counts[topic['notebook_id']])
        impact = round(weight * incidence, 4)
        reviewing = overdue or topic['covered']
        cost = 25 if reviewing else 50
        interval = topic.get('review_interval_days', 7)
        reasons = ['conteúdo já estudado' if topic['covered'] else 'conteúdo ainda não iniciado',
            'sem amostra de domínio' if score is None else f'domínio estimado {score}%',
            f'{errors} erros nas últimas 5 respostas', f'custo sugerido {cost} min']
        if overdue: reasons.append('revisão devida')
        if age is not None and age >= 14: reasons.append(f'pouca evidência recente: última resposta há {age} dias')
        if trend is not None and trend < -10: reasons.append('queda de acertos entre duas amostras de 5 respostas')
        if discipline.get('weight_status') != 'extraido_com_fonte': reasons.append('peso registrado a conferir')
        if discipline.get('question_count_status') != 'extraido_com_fonte': reasons.append('incidência registrada a conferir')
        candidates.append({
            'id': topic['id'], 'notebook_id': topic['notebook_id'], 'topic_key': topic['topic_key'],
            'title': topic['title'], 'discipline': discipline['title'], 'covered': topic['covered'],
            'risk': risk, 'risk_components': components, 'urgency_multiplier': urgency,
            'impact': impact, 'cost_minutes': cost, 'expected_return': round(impact * risk / 100 / cost, 6),
            'kind': 'Revisão' if reviewing else 'Teoria e questões',
            'review_interval_days': interval, 'review_due_date': due,
            'review_reason': topic.get('review_reason'), 'evidence_ids': topic['evidence_ids'],
            'weight_status': discipline.get('weight_status'), 'weight_source': discipline.get('weight_source'),
            'question_count_status': discipline.get('question_count_status'),
            'reasons': reasons, 'classification': 'operational_heuristic',
        })
    return sorted(candidates, key=lambda c: (-c['expected_return'], -c['risk'], c['id']))


def strategy_summary(state, today):
    candidates = rank_candidates(state, today)
    critical = [c['id'] for c in candidates if not c['covered'] and c['risk'] >= 40]
    lagging = [c['id'] for c in candidates if c['covered'] and c['risk_components']['evidence_age'] >= 5]
    missed = state.get('strategy_facts', {}).get('missed_entries', [])
    return {'version': VERSION, 'preparation_id': state['preparation_id'], 'computed_at': today.isoformat(),
        'candidates': candidates, 'debt': {
            'overdue_reviews': [c['id'] for c in candidates if c['review_due_date'] and c['review_due_date'] < today.isoformat()],
            'critical_unstarted': critical, 'lagging_topics': lagging,
            'missed_blocks': missed, 'missed_minutes': sum(e['minutes'] for e in missed),
            'late_milestones': state.get('strategy_facts', {}).get('late_milestones', []),
            'window_days': 28},
        'truncated': state.get('truncated', False), 'limits': state.get('limits'),
        'notice': 'Ranking operacional heurístico; não mede esquecimento nem probabilidade de aprovação.'}


def load_guard(state, entries, availability, reserved=None):
    daily = Counter()
    for e in entries:
        daily[e['date']] += e['minutes']
    warnings = []
    excessive = [d for d, minutes in daily.items() if minutes + (reserved or {}).get(d, 0) > availability[date.fromisoformat(d).weekday()]]
    if excessive: warnings.append({'code': 'protected_over_capacity', 'dates': sorted(excessive),
        'message': 'Blocos preservados e compromissos ultrapassam a disponibilidade; ajuste manualmente os compromissos protegidos.'})
    baseline = state.get('current_pace', {}).get('minutes_per_week', 0)
    max_week = max((sum(minutes for iso,minutes in daily.items() if day <= date.fromisoformat(iso) <= day+timedelta(days=6))
        for day in (date.fromisoformat(d) for d in daily)), default=0)
    if state.get('candidate_model', {}).get('completed_sessions', 0) >= 3 and max_week > max(180, baseline * 1.5):
        warnings.append({'code': 'above_recent_pattern', 'message': 'Carga planejada acima do seu padrão recente.'})
    consistency = state.get('candidate_model', {}).get('consistency')
    if consistency is not None and consistency < 50:
        warnings.append({'code': 'low_adherence', 'message': 'Baixa aderência registrada; considere o plano mínimo.'})
    days = sorted(date.fromisoformat(d) for d in daily if daily[d] > 0)
    run = longest = 0; previous = None
    for day in days:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        longest = max(longest, run); previous = day
    if longest >= 7: warnings.append({'code': 'no_rest_day', 'message': 'Sete ou mais dias seguidos programados; considere um dia de descanso.'})
    return {'warnings': warnings, 'break_after_minutes': 50,
        'notice': 'Alerta de carga operacional, sem diagnóstico clínico. Horários e pausas devem ser conferidos.'}


def preview_strategy(state, today, settings, previous, reserved, missed_days=0):
    summary = strategy_summary(state, today)
    first = max(today, settings.start_date)
    protected = [e for e in previous if e['completed'] or e['manual'] or e['fixed']]
    # Blocks outside the requested range also remain, but don't contaminate its projection.
    within = [e for e in protected if first.isoformat() <= e['date'] <= settings.end_date.isoformat()]
    scenarios = {}
    for mode, cap in (('A', 720), ('B', 45), ('C', 25)):
        availability = [min(m, cap) for m in settings.availability]
        excluded = { (first + timedelta(days=i)).isoformat(): 720 for i in range(missed_days) }
        constraints = {**reserved, **excluded}
        entries = build_strategy_plan(state['preparation_id'], summary['candidates'], availability,
            first.isoformat(), settings.end_date.isoformat(), settings.block_minutes, within, constraints)
        generated = [e for e in entries if e['entry_id'] not in {p['entry_id'] for p in within}]
        allocation = Counter()
        for e in generated: allocation[e['topic_id']] += e['minutes']
        new_topics = sum(not c['covered'] and allocation[c['id']] >= c['cost_minutes'] for c in summary['candidates'])
        total = len(summary['candidates']); covered = state['coverage']['studied']
        scheduled_reviews = {c['id'] for c in summary['candidates'] if c['kind']=='Revisão' and allocation[c['id']]>=c['cost_minutes']}
        scenarios[mode] = {'availability': availability, 'minutes': sum(e['minutes'] for e in entries),
            'generated_minutes': sum(e['minutes'] for e in generated), 'protected_minutes': sum(e['minutes'] for e in within),
            'entries': entries[:200], 'entries_count': len(entries), 'entries_truncated': len(entries) > 200,
            'projected_coverage': round(100 * min(total, covered + new_topics) / total, 1) if total else None,
            'new_topics_assuming_completion': new_topics,
            'unaddressed_due_reviews': [i for i in summary['debt']['overdue_reviews'] if i not in scheduled_reviews],
            'unaddressed_critical_topics': [i for i in summary['debt']['critical_unstarted'] if allocation[i] < 50],
            'load_guard': load_guard(state, entries, availability, constraints)}
    summary.update({'scenarios': scenarios, 'simulation': True, 'facts_changed': False,
        'settings': settings.model_dump(mode='json'), 'missed_days': missed_days,
        'recovery': {'enabled': bool(summary['debt']['missed_blocks']),
            'notice': 'Pendências críticas são priorizadas dentro do tempo disponível, sem somar dívida à carga diária.'},
        'assumptions': ['Custo sugerido: 50 min para contato inicial, 25 min para revisão; não é tempo medido de domínio.',
            'Cobertura projetada pressupõe conclusão dos blocos sugeridos; minutos não comprovam aprendizado.',
            'A usa sua disponibilidade; B limita a 45 min/dia; C limita a 25 min/dia. Dias perdidos afetam novas sugestões.',
            'Tarefas intermediárias e flashcards não são considerados automaticamente concluídos pela simulação.']})
    return summary
