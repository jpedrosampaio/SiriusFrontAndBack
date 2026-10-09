"""Deterministic, owned training intelligence. No writes, AI or guessed performance."""
import re
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func, text
from db.models.health import WorkoutLog, WorkoutPlan, WorkoutDay, PlanExercise, WorkoutSet, SessionExercise, WorkoutLogExercise
from db.models.identity import User
from db.session import unit_of_work
from services.time import local_today
from training_contracts import TrainingState, SubstitutionArgs, SubstitutionResult

HISTORY_LIMIT = 300
PLAN_LIMIT = 20
EXERCISE_LIMIT = 200
SET_BUDGET = 10000
EXERCISE_BUDGET = 2000


def normalized(value):
    return ' '.join(str(value or '').split()).casefold()


def decimal(value):
    if value is None or value == '' or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def wire(value):
    return format(value, 'f') if value is not None else None


def rep_range(value):
    match = re.fullmatch(r'\s*(\d{1,3})(?:\s*[-–a]\s*(\d{1,3}))?\s*', str(value))
    if not match:
        return None
    low, high = int(match[1]), int(match[2] or match[1])
    return (low, high) if 1 <= low <= high <= 999 else None


def execution(log, ex):
    # Never replace missing actual sets with prescribed loads/repetitions.
    sets = [s for s in ex['sets_data'] if s['completed']]
    known = Decimal(0)
    valid = []
    rpes = []
    for s in sets:
        weight, reps, rpe = decimal(s['weight']), decimal(s['reps']), decimal(s['rpe'])
        if weight is not None and reps is not None and reps > 0:
            known += weight * reps
            valid.append((weight, int(reps)))
        if rpe is not None and 1 <= rpe <= 10:
            rpes.append(float(rpe))
    # Flags can be legacy/manual; the actual rows are the evidence.
    missing = max(0, ex['sets_completed'] - len(sets))
    complete = bool(sets) and len(sets) == ex['sets'] and len(valid) == len(sets) and missing == 0
    return {'date': log['date'], 'log_id': str(log['log_id']), 'plan_id': str(log['plan_id']) if log['plan_id'] else None,
        'day_index': log.get('day_index'),
        'prescribed_sets': ex['sets'], 'target_reps': ex['reps'], 'recorded_sets': len(sets),
        'legacy_sets_without_details': missing, 'known_volume': known, 'volume': known if complete else None,
        'valid': valid, 'rpes': rpes, 'actual': sets}


def progression(rows):
    base = {'action': 'insufficient_data', 'reason': 'São necessárias duas execuções comparáveis com séries, cargas, repetições e RPE registrados.'}
    if not rows:
        return base
    latest = rows[-1]
    context = {k: latest[k] for k in ('plan_id', 'day_index', 'prescribed_sets', 'target_reps')}
    return context | progression_for_day(rows)


def progression_for_day(rows):
    base = {'action': 'insufficient_data', 'reason': 'São necessárias duas execuções comparáveis do mesmo dia da ficha, com séries, cargas, repetições e RPE registrados.'}
    last = rows[-1]
    if last['day_index'] is None or not last['plan_id']:
        return base | {'reason': 'O dia de origem da ficha não foi registrado. Cargas, volume e recordes são analisáveis; progressão específica não é comprovável.'}
    rows = [r for r in rows if (r['plan_id'], r['day_index']) == (last['plan_id'], last['day_index'])]
    if len(rows) < 2:
        return base
    before, last = rows[-2:]
    dates = [before['date'], last['date']]
    if (not last['plan_id'] or before['plan_id'] != last['plan_id'] or before['date'] == last['date']
        or before['prescribed_sets'] != last['prescribed_sets'] or before['target_reps'] != last['target_reps']):
        return base | {'evidence_dates': dates, 'reason': 'As duas últimas execuções não têm plano, dia e prescrição comparáveis.'}
    target = rep_range(last['target_reps'])
    if not target:
        return base | {'evidence_dates': dates, 'reason': 'A prescrição de repetições não possui uma faixa numérica interpretável.'}
    for row in (before, last):
        if (len(row['actual']) != row['prescribed_sets'] or len(row['valid']) != len(row['actual'])
            or len(row['rpes']) != len(row['actual']) or row['legacy_sets_without_details']):
            return base | {'evidence_dates': dates}
    weights = {w for row in (before, last) for w, _ in row['valid']}
    if len(weights) != 1 or next(iter(weights)) <= 0:
        return base | {'evidence_dates': dates, 'reason': 'Cargas diferentes ou não positivas impedem uma comparação uniforme.'}
    weight = next(iter(weights))
    if any(r < target[1] for row in (before, last) for _, r in row['valid']) or any(r > 8 for row in (before, last) for r in row['rpes']):
        return {'action': 'maintain', 'reason': 'Mantenha a referência: o topo da faixa não foi atingido em todas as séries ou houve RPE acima de 8.',
            'current_weight': wire(weight), 'evidence_dates': dates}
    suggested = weight + min(weight * Decimal('0.025'), Decimal('2.5'))
    suggested = suggested.quantize(Decimal('0.001'))
    if suggested <= weight:
        return {'action': 'maintain', 'current_weight': wire(weight), 'evidence_dates': dates,
            'reason': 'O incremento conservador não é representável na precisão registrada. Avalie os incrementos disponíveis sem aumento automático.'}
    return {'action': 'review_increase', 'current_weight': wire(weight), 'suggested_weight': wire(suggested),
        'evidence_dates': dates, 'reason': 'Duas execuções completas na mesma carga atingiram o topo da faixa com RPE até 8. Avalie +2,5% (máximo 2,5 kg), ajustando aos incrementos disponíveis. Nada foi alterado.'}


def exercise_state(key, name, group, rows):
    records = []
    candidates = [(weight, reps, row) for row in rows for weight, reps in row['valid'] if weight > 0]
    def record(kind, value, row, reps=None):
        return {'kind': kind, 'value': wire(value), 'date': row['date'], 'log_id': row['log_id'], 'reps': reps}
    if candidates:
        weight, reps, row = max(candidates, key=lambda x: x[0])
        records.append(record('max_load', weight, row, reps))
        for reps in sorted({c[1] for c in candidates}):
            weight, _, row = max((c for c in candidates if c[1] == reps), key=lambda x: x[0])
            records.append(record('load_at_reps', weight, row, reps))
    complete = [r for r in rows if r['volume'] is not None]
    if complete:
        row = max(complete, key=lambda r: r['volume'])
        records.append(record('max_volume', row['volume'], row))
    alerts = []
    if len(rows) >= 2:
        before, last = rows[-2:]
        comparable = (before['plan_id'] and before['plan_id'] == last['plan_id'] and before['date'] != last['date']
            and before['day_index'] is not None and before['day_index'] == last['day_index'])
        if comparable and before['volume'] and last['volume'] is not None and last['volume'] > before['volume'] * Decimal('1.3'):
            alerts.append({'code': 'volume_jump', 'reason': 'O volume registrado aumentou mais de 30% entre as duas últimas execuções. Confira séries, repetições e cargas.', 'evidence_dates': [before['date'], last['date']]})
        if comparable and before['valid'] and last['valid']:
            old, new = max(w for w, _ in before['valid']), max(w for w, _ in last['valid'])
            if old > 0 and new > old * Decimal('1.15'):
                alerts.append({'code': 'load_jump', 'reason': 'A maior carga registrada aumentou mais de 15%. Revise o registro e a execução antes de decidir outro aumento.', 'evidence_dates': [before['date'], last['date']]})
    if len(rows) >= 3:
        recent = rows[-3:]
        if (len({r['plan_id'] for r in recent}) == 1 and recent[0]['plan_id']
            and recent[0]['day_index'] is not None and len({r['day_index'] for r in recent}) == 1
            and len({r['date'] for r in recent}) == 3
            and len({(r['prescribed_sets'], r['target_reps']) for r in recent}) == 1
            and all(r['volume'] is not None and r['recorded_sets'] == r['prescribed_sets'] for r in recent)
            and recent[0]['volume'] > recent[1]['volume'] > recent[2]['volume']):
            alerts.append({'code': 'recorded_decline', 'reason': 'O volume registrado diminuiu em três execuções comparáveis. Confira os registros e a adequação do plano; isso não é um diagnóstico.', 'evidence_dates': [r['date'] for r in recent]})
    prescribed = sum(r['prescribed_sets'] for r in rows)
    recorded = sum(r['recorded_sets'] for r in rows)
    recent_prescribed = sum(r['prescribed_sets'] for r in rows[-3:])
    recent_recorded = sum(r['recorded_sets'] for r in rows[-3:])
    if len(rows) >= 3 and recent_prescribed and recent_recorded / recent_prescribed < .5:
        alerts.append({'code': 'low_set_adherence', 'reason': f'Nas três últimas execuções, {recent_recorded}/{recent_prescribed} séries prescritas possuem detalhes registrados (menos de metade). Isso mede cobertura dos registros, não frequência planejada.', 'evidence_dates': [r['date'] for r in rows[-3:]]})
    rpes = [value for r in rows for value in r['rpes']]
    known = sum((r['known_volume'] for r in rows), Decimal(0))
    history = [{**{k: wire(v) if k in ('known_volume', 'volume') else v for k, v in r.items() if k not in ('valid', 'rpes', 'actual')},
        'max_load': wire(max((w for w, _ in r['valid']), default=None)),
        'average_rpe': round(sum(r['rpes']) / len(r['rpes']), 2) if r['rpes'] else None} for r in rows[-20:]]
    contexts, unknown_positions, positions = {}, {}, {}
    for position, row in enumerate(rows):
        positions[id(row)] = position
        if row['plan_id'] and row['day_index'] is not None:
            contexts.setdefault((row['plan_id'], row['day_index']), []).append(row)
        elif row['plan_id']:
            unknown_positions[row['plan_id']] = position
    proposals = []
    for (plan_id, _), values in contexts.items():
        proposal = progression(values)
        if unknown_positions.get(plan_id, -1) > positions[id(values[-1])]:
            proposal.update(action='insufficient_data', suggested_weight=None,
                reason='Há um registro mais recente deste exercício/plano sem dia de origem. Registre uma nova execução identificada antes de avaliar aumento.')
        proposals.append(proposal)
    return {'key': key, 'name': name, 'muscle_group': group or None, 'executions': len(rows), 'recorded_sets': recorded,
        'prescribed_sets': prescribed, 'known_volume': wire(known), 'volume': wire(known) if len(complete) == len(rows) else None,
        'rpe_samples': len(rpes), 'average_rpe': round(sum(rpes) / len(rpes), 2) if rpes else None,
        'records': records, 'progression': progression(rows), 'progressions': proposals, 'alerts': alerts, 'history': history}


def build_state(logs, *, day, start, zone, count, truncated=False):
    logs = [{**l, 'date': date.fromisoformat(l['date']) if isinstance(l['date'], str) else l['date']} for l in logs]
    by_exercise, weeks, groups = {}, defaultdict(lambda: {'workouts': 0, 'days': set()}), {}
    for log in sorted(logs, key=lambda l: (l['date'], l['created_at'], str(l['log_id']))):
        week = log['date'] - timedelta(days=log['date'].weekday())
        weeks[week]['workouts'] += 1
        weeks[week]['days'].add(log['date'])
        for ex in log['exercises_completed']:
            identity = (normalized(ex['name']), normalized(ex['muscle_group']))
            if identity not in by_exercise:
                by_exercise[identity] = {'name': ex['name'], 'group': ex['muscle_group'].strip(), 'rows': []}
            rows = by_exercise[identity]['rows']
            row = execution(log, ex)
            if rows and rows[-1]['log_id'] == row['log_id']:
                previous = rows[-1]
                previous['prescribed_sets'] += row['prescribed_sets']
                previous['recorded_sets'] += row['recorded_sets']
                previous['legacy_sets_without_details'] += row['legacy_sets_without_details']
                previous['known_volume'] += row['known_volume']
                previous['volume'] = previous['volume'] + row['volume'] if previous['volume'] is not None and row['volume'] is not None else None
                for field in ('valid', 'rpes', 'actual'):
                    previous[field].extend(row[field])
                if previous['target_reps'] != row['target_reps']:
                    previous['target_reps'] = 'mixed'
            else:
                rows.append(row)
    exercises = [exercise_state(json.dumps(key, ensure_ascii=False), data['name'], data['group'], data['rows']) for key, data in sorted(by_exercise.items())]
    for ex in exercises:
        if not ex['muscle_group']:
            continue
        group = groups.setdefault(normalized(ex['muscle_group']), {'name': ex['muscle_group'], 'recorded_sets': 0, 'known_volume': Decimal(0), 'complete': True})
        group['recorded_sets'] += ex['recorded_sets']
        group['known_volume'] += Decimal(ex['known_volume'])
        group['complete'] &= ex['volume'] is not None
    prescribed = sum(e['prescribed_sets'] for e in exercises)
    recorded = sum(e['recorded_sets'] for e in exercises)
    limitations = ['Recordes e evolução referem-se apenas à janela analisada, não a toda a vida.',
        'Séries sem detalhes não comprovam desempenho; prescrição nunca substitui registro.',
        'Aderência mede séries registradas/prescritas nas execuções analisadas. Frequência planejada não está disponível.',
        'Volume é carga × repetições, não trabalho mecânico nem diagnóstico; grupos usam somente rótulos registrados.']
    if truncated:
        limitations.append('Leitura limitada a 300 logs, 2.000 exercícios e 10.000 séries; métricas detalhadas e frequência cobrem somente a amostra analisada.')
    if not truncated:
        week = start - timedelta(days=start.weekday())
        while week <= day:
            weeks[week]  # Include genuinely empty weeks, including partial boundary weeks.
            week += timedelta(days=7)
    return TrainingState(as_of=day, start=start, timezone=zone, truncated=truncated or len(exercises) > EXERCISE_LIMIT,
        completed_workouts=count, analyzed_workouts=len(logs), training_days=len({l['date'] for l in logs}),
        recorded_minutes=sum(l['duration_minutes'] for l in logs),
        weekly_frequency=[{'week_start': str(w), 'workouts': v['workouts'], 'training_days': len(v['days'])} for w, v in sorted(weeks.items())],
        set_adherence=round(recorded / prescribed * 100, 1) if prescribed else None,
        exercises=exercises[:EXERCISE_LIMIT], muscle_groups=[{'name': g['name'], 'recorded_sets': g['recorded_sets'],
            'known_volume': wire(g['known_volume']), 'volume': wire(g['known_volume']) if g['complete'] else None} for _, g in sorted(groups.items())],
        alerts=[], limitations=limitations + (['Lista de exercícios limitada a 200 identidades.'] if len(exercises) > EXERCISE_LIMIT else []))


async def load_state(session, uid, day, zone, days=90, plan_id=None):
    from services.workout_logs import serialize_logs
    start = day - timedelta(days=days - 1)
    where = (WorkoutLog.user_id == uid, WorkoutLog.completed.is_(True), WorkoutLog.date >= start, WorkoutLog.date <= day)
    if plan_id is not None:
        where += (WorkoutLog.plan_id == plan_id,)
    count = await session.scalar(select(func.count()).select_from(WorkoutLog).where(*where))
    rows = (await session.scalars(select(WorkoutLog).where(*where).order_by(WorkoutLog.date.desc(), WorkoutLog.created_at.desc(), WorkoutLog.id).limit(HISTORY_LIMIT))).all()
    # Bound child materialization as well as parent rows, even for very large imported logs.
    sizes = {}
    for model, parent, set_fk, ids in (
        (SessionExercise, SessionExercise.session_id, WorkoutSet.exercise_id, [r.session_id for r in rows if r.session_id]),
        (WorkoutLogExercise, WorkoutLogExercise.log_id, WorkoutSet.log_exercise_id, [r.id for r in rows if not r.session_id]),
    ):
        if not ids:
            continue
        values = (await session.execute(select(parent, func.count(func.distinct(model.id)), func.count(WorkoutSet.id))
            .outerjoin(WorkoutSet, (set_fk == model.id) & (WorkoutSet.user_id == uid))
            .where(model.user_id == uid, parent.in_(ids)).group_by(parent))).all()
        sizes.update({identity: (ex_count, set_count) for identity, ex_count, set_count in values})
    chosen, ex_total, set_total = [], 0, 0
    for row in rows:
        ex_count, set_count = sizes.get(row.session_id or row.id, (0, 0))
        if ex_total + ex_count > EXERCISE_BUDGET or set_total + set_count > SET_BUDGET:
            break
        chosen.append(row); ex_total += ex_count; set_total += set_count
    rows = chosen
    logs = await serialize_logs(session, uid, rows, include_session_origin=True)
    return build_state(logs, day=day, start=start, zone=zone, count=count, truncated=count > len(rows))


class TrainingEngine:
    async def get_state(self, user_id, days=90):
        uid = UUID(str(user_id))
        async with unit_of_work() as session:
            # Consistent snapshot across log/set queries while another tab saves.
            await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            owner = await session.get(User, uid)
            if owner is None:
                raise HTTPException(404, 'Usuário não encontrado.')
            return await load_state(session, uid, local_today(owner.timezone), owner.timezone, days)


# Explicit metadata, never inferred from an arbitrary substring or AI.
MOVEMENTS = {normalized(name): movement for movement, names in {
    'horizontal_push': ['Supino', 'Supino reto', 'Supino reto com halteres', 'Supino reto com barra', 'Chest press'],
    'vertical_push': ['Desenvolvimento', 'Desenvolvimento com halteres', 'Desenvolvimento militar'],
    'horizontal_pull': ['Remada baixa', 'Remada curvada', 'Remada unilateral'],
    'vertical_pull': ['Puxada frontal', 'Puxada alta', 'Barra fixa'],
    'knee_dominant': ['Agachamento', 'Agachamento livre', 'Leg press', 'Leg press 45'],
    'hip_hinge': ['Levantamento terra', 'Terra romeno', 'Stiff'],
    'elbow_flexion': ['Rosca direta', 'Rosca alternada', 'Rosca martelo'],
    'elbow_extension': ['Tríceps pulley', 'Tríceps corda', 'Tríceps testa'],
}.items() for name in names}


async def substitutions(user_id, args: SubstitutionArgs):
    uid = UUID(str(user_id))
    async with unit_of_work() as session:
        await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        query = select(WorkoutPlan).where(WorkoutPlan.user_id == uid, WorkoutPlan.archived_at.is_(None))
        source = await session.scalar(query.where(WorkoutPlan.id == args.plan_id))
        if source is None:
            raise HTTPException(404, 'Plano não encontrado.')
        day = await session.scalar(select(WorkoutDay).where(WorkoutDay.user_id == uid, WorkoutDay.plan_id == source.id)
            .order_by(WorkoutDay.position).offset(args.day_index).limit(1))
        exercise = await session.scalar(select(PlanExercise).where(PlanExercise.user_id == uid, PlanExercise.day_id == day.id)
            .order_by(PlanExercise.position).offset(args.exercise_index).limit(1)) if day else None
        if exercise is None:
            raise HTTPException(422, 'Exercício inválido.')
        movement = MOVEMENTS.get(normalized(exercise.name))
        objective, group = normalized(source.objective), normalized(exercise.muscle_group)
        limitations = ['Propostas não alteram ficha nem sessão. Verifique equipamento, execução e adequação com um profissional.']
        if not objective or not group:
            return SubstitutionResult(exercise=exercise.name, objective=source.objective, movement=movement, suggestions=[],
                limitations=limitations + ['Objetivo ou grupo muscular não registrado; não há equivalência demonstrável.'])
        plans = (await session.scalars(query.order_by(WorkoutPlan.created_at.desc(), WorkoutPlan.id).limit(PLAN_LIMIT + 1))).all()
        plans_truncated = len(plans) > PLAN_LIMIT
        plans = [source] + [p for p in plans[:PLAN_LIMIT] if p.id != source.id]
        eligible = {p.id: p for p in plans if normalized(p.objective) == objective}
        def sql_normalized(column):
            return func.lower(func.regexp_replace(func.trim(column), r'\s+', ' ', 'g'))
        candidates = select(PlanExercise.name, PlanExercise.muscle_group, WorkoutDay.plan_id).join(WorkoutDay,
            (WorkoutDay.id == PlanExercise.day_id) & (WorkoutDay.user_id == PlanExercise.user_id)).where(
                PlanExercise.user_id == uid, WorkoutDay.plan_id.in_(eligible), sql_normalized(PlanExercise.muscle_group) == group)
        if movement:
            candidates = candidates.where(sql_normalized(PlanExercise.name).in_([name for name, value in MOVEMENTS.items() if value == movement]))
        candidates = (await session.execute(candidates.order_by(WorkoutDay.plan_id, WorkoutDay.position, PlanExercise.position).limit(1001))).all()
        suggestions, seen = [], {normalized(exercise.name)}
        for ex in candidates[:1000]:
            name = normalized(ex.name)
            other_movement = MOVEMENTS.get(name)
            if name in seen:
                continue
            seen.add(name)
            suggestions.append({'name': ex.name, 'muscle_group': ex.muscle_group, 'objective': eligible[ex.plan_id].objective,
                'movement': other_movement, 'movement_confirmed': bool(movement and movement == other_movement),
                'source_plan_id': ex.plan_id, 'reason': 'Mesmo objetivo e grupo muscular registrados.' + (' Mesmo padrão de movimento da tabela explícita.' if movement else ' Padrão de movimento não confirmado; apenas candidato para avaliação.')})
        if not movement:
            limitations.append('Movimento do exercício original desconhecido; não é possível garantir equivalência biomecânica.')
        return SubstitutionResult(exercise=exercise.name, objective=source.objective, movement=movement,
            suggestions=suggestions[:10], limitations=limitations, truncated=plans_truncated or len(candidates) > 1000 or len(suggestions) > 10)


def agent_context(state):
    data = state.model_dump(mode='json')
    data['exercises'] = [{**{k: v for k, v in e.items() if k not in ('history', 'records', 'progressions')},
        'records': [r for r in e['records'] if r['kind'] != 'load_at_reps']} for e in data['exercises'][:20]]
    data['agent_exercises_truncated'] = len(state.exercises) > 20
    data['agent_groups_truncated'] = len(data['muscle_groups']) > 20
    data['muscle_groups'] = data['muscle_groups'][:20]
    data['agent_weeks_truncated'] = len(data['weekly_frequency']) > 12
    data['weekly_frequency'] = data['weekly_frequency'][-12:]
    return data


async def life_facts(session, uid, day):
    """Cheap aggregate for the existing Life State, not the full exercise history."""
    start = day - timedelta(days=27)
    count, days, minutes = (await session.execute(select(func.count(), func.count(func.distinct(WorkoutLog.date)),
        func.coalesce(func.sum(WorkoutLog.duration_minutes), 0)).where(WorkoutLog.user_id == uid,
        WorkoutLog.completed.is_(True), WorkoutLog.date >= start, WorkoutLog.date <= day))).one()
    return {'period_start': str(start), 'period_end': str(day), 'completed_workouts': count,
        'training_days': days, 'recorded_minutes': minutes, 'source': 'completed_workout_logs',
        'detail_route': '/workouts', 'scheduled_adherence': None}
