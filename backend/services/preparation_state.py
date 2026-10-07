"""Preparation projections from owner-scoped facts; no AI and no copied ledger."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from sqlalchemy import select, func
from db.models.studies import (Notebook, StudyTopic, TopicProgress, StudySession,
    StudyPlan, StudyPlanEntry, StudyTarget, QuestionAttempt, ReviewEvent,
    Flashcard, FlashcardReview, StudyNote, StudyDraft)
from services.study_evidence import attempts, latest_reviews
from study_mastery import mastery, topic_priority
from db.models.exams import Exam, ExamAttempt
from services.study_workspace import entry_json

VERSION = 'preparation-state-3.0.1'
LIMIT = 2000


def learning_stage(covered, estimate, last_date, today):
    if not estimate['samples']:
        return 'exposed' if covered else 'not_started'
    if estimate['samples'] < 10 or estimate['score'] < 60:
        return 'practicing'
    if estimate['confidence'] != 'high' or estimate['score'] < 80:
        return 'consolidating'
    return 'maintenance' if last_date and (today-last_date).days > 14 else 'mastered'


async def preparation_state(session, uid, program, zone, today):
    """Bounded batched reads. Truncation is explicit, never presented as complete."""
    target = await session.scalar(select(StudyTarget).where(
        StudyTarget.user_id == uid, StudyTarget.program_id == program.id))
    books = list((await session.scalars(select(Notebook).where(
        Notebook.user_id == uid, Notebook.program_id == program.id,
        Notebook.archived_at.is_(None)).order_by(Notebook.id).limit(LIMIT+1))).all())
    truncated = len(books) > LIMIT
    books = books[:LIMIT]; ids = [b.id for b in books]
    topic_rows = (await session.execute(select(StudyTopic, TopicProgress.studied)
        .outerjoin(TopicProgress, (TopicProgress.topic_id == StudyTopic.id) &
            (TopicProgress.user_id == StudyTopic.user_id))
        .where(StudyTopic.user_id == uid, StudyTopic.notebook_id.in_(ids),
            StudyTopic.archived_at.is_(None)).order_by(StudyTopic.notebook_id,
            StudyTopic.position, StudyTopic.id).limit(LIMIT+1))).all()
    truncated |= len(topic_rows) > LIMIT; topic_rows = topic_rows[:LIMIT]
    individual = await attempts(session, uid, zone, program_id=program.id, limit=5000, active_topics=True)
    truncated |= len(individual) == 5000
    reviews = await latest_reviews(session, uid, program_id=program.id, limit=LIMIT+1)
    truncated |= len(reviews) > LIMIT; reviews = reviews[:LIMIT]
    sessions = list((await session.scalars(select(StudySession).where(
        StudySession.user_id == uid, StudySession.notebook_id.in_(ids),
        StudySession.completed.is_(True), StudySession.date.between(today-timedelta(days=27), today))
        .order_by(StudySession.date.desc(), StudySession.id).limit(LIMIT+1))).all())
    truncated |= len(sessions) > LIMIT; sessions = sessions[:LIMIT]
    plan = await session.scalar(select(StudyPlan).where(
        StudyPlan.user_id == uid, StudyPlan.program_id == program.id))
    entries = list((await session.scalars(select(StudyPlanEntry).where(
        StudyPlanEntry.user_id == uid, StudyPlanEntry.plan_id == plan.id,
        StudyPlanEntry.date.between(today-timedelta(days=27), today+timedelta(days=6)))
        .order_by(StudyPlanEntry.date, StudyPlanEntry.id).limit(LIMIT+1))).all()) if plan else []
    truncated |= len(entries) > LIMIT; entries = entries[:LIMIT]
    upcoming = await session.scalar(select(StudyPlanEntry).where(
        StudyPlanEntry.user_id == uid, StudyPlanEntry.plan_id == plan.id,
        StudyPlanEntry.notebook_id.in_(ids), StudyPlanEntry.completed.is_(False), StudyPlanEntry.date >= today)
        .order_by(StudyPlanEntry.date, StudyPlanEntry.id).limit(1)) if plan else None
    question_totals = (await session.execute(select(func.coalesce(func.sum(QuestionAttempt.total), 0),
        func.coalesce(func.sum(QuestionAttempt.correct), 0)).where(
        QuestionAttempt.user_id == uid, QuestionAttempt.notebook_id.in_(ids)))).one()
    card_reviews = (await session.execute(select(FlashcardReview, Flashcard.notebook_id)
        .join(Flashcard, (Flashcard.id == FlashcardReview.flashcard_id) &
            (Flashcard.user_id == FlashcardReview.user_id)).where(
        FlashcardReview.user_id == uid, Flashcard.notebook_id.in_(ids), Flashcard.archived_at.is_(None))
        .order_by(FlashcardReview.reviewed_at.desc(), FlashcardReview.id).limit(101))).all()
    flashcards_due = await session.scalar(select(func.count()).select_from(Flashcard).where(
        Flashcard.user_id == uid, Flashcard.notebook_id.in_(ids),
        Flashcard.archived_at.is_(None), Flashcard.next_review <= today))
    groups = defaultdict(list)
    for a in individual: groups[(a['notebook_id'], a['topic_key'])].append(a)
    due = [r for r in reviews if r['due_date'] and r['due_date'] <= today.isoformat()]
    overdue_keys = {(r['notebook_id'], r['topic_key']) for r in due}
    review_ids = defaultdict(list)
    for r in reviews: review_ids[(r['notebook_id'], r['topic_key'])].append(r['review_id'])
    materials = defaultdict(list)
    for model, kind in ((StudyNote, 'note'), (StudyDraft, 'summary'), (Flashcard, 'flashcard')):
        query = select(model).where(model.user_id == uid, model.notebook_id.in_(ids))
        if model is Flashcard: query = query.where(model.archived_at.is_(None))
        linked = list((await session.scalars(query.order_by(model.id).limit(LIMIT+1))).all())
        truncated |= len(linked) > LIMIT
        for m in linked[:LIMIT]: materials[m.notebook_id].append({'id': str(m.id), 'kind': kind,
            'topic_key': m.topic_key if model is StudyDraft else None})
    exam_date = (target.exam_date if target else None) or program.target_date
    days = (exam_date-today).days if exam_date else None
    graph = []; candidates = []; covered_count = 0
    books_by_id = {b.id: b for b in books}
    for topic, studied in topic_rows:
        evidence = groups[(str(topic.notebook_id), topic.topic_key)]
        estimate = mastery(evidence, today)
        last = max((date.fromisoformat(a['date']) for a in evidence), default=None)
        covered = bool(studied); covered_count += covered
        book = books_by_id[topic.notebook_id]
        priority = topic_priority(weight=book.weight, question_count=book.num_questoes_edital,
            estimate=estimate['score'], errors=sum(not a['correct'] for a in evidence),
            overdue=(str(book.id), topic.topic_key) in overdue_keys, studied=covered, days_left=days)
        if book.peso_status != 'extraido_com_fonte': priority['reasons'].append('peso registrado a conferir')
        if book.num_questoes_status != 'extraido_com_fonte': priority['reasons'].append('incidência de questões a conferir')
        node = {'id': str(topic.id), 'parent_id': str(topic.parent_id) if topic.parent_id else str(book.id),
            'notebook_id': str(book.id), 'topic_key': topic.topic_key, 'title': topic.name,
            'covered': covered, 'mastery': estimate, 'stage': learning_stage(covered, estimate, last, today),
            'evidence_ids': [a['attempt_id'] for a in evidence[:100]],
            'question_ids': [a['internal_question_id'] for a in evidence[:100]],
            'exam_attempt_ids': sorted({a['exam_attempt_id'] for a in evidence if a['exam_attempt_id']}),
            'question_count': len(evidence), 'error_count': sum(not a['correct'] for a in evidence),
            'review_ids': review_ids[(str(book.id), topic.topic_key)],
            'sources': topic.evidence or {}, 'evidence_ids_truncated': len(evidence) > 100}
        graph.append(node)
        candidates.append({**{k: node[k] for k in ('id', 'notebook_id', 'topic_key', 'title')},
            'discipline': book.name, 'weight_status': book.peso_status,
            'question_count_status': book.num_questoes_status,
            'weight_source': book.peso_fonte, **priority})
    recent = [s for s in sessions if s.date >= today-timedelta(days=6)]
    current = sum(s.duration_minutes for s in recent)
    planned = sum(e.minutes for e in entries if today-timedelta(days=6) <= e.date <= today)
    debt_entries = [e for e in entries if e.date < today and not e.completed]
    past_entries = [e for e in entries if e.date <= today]
    consistency = round(100*sum(e.completed for e in past_entries)/len(past_entries), 1) if past_entries else None
    total_topics = len(graph)
    coverage = {'studied': covered_count, 'total': total_topics,
        'percent': round(100*covered_count/total_topics, 1) if total_topics else None}
    estimate = mastery(individual, today)
    accuracy = round(100*question_totals[1]/question_totals[0], 1) if question_totals[0] else None
    review_percent = round(100*(len(reviews)-len(due))/len(reviews), 1) if reviews else None
    components = [
        {'key': 'coverage', 'title': 'Cobertura', 'value': coverage['percent'], 'reason': f'{covered_count}/{total_topics} assuntos marcados como estudados; contato não comprova domínio.'},
        {'key': 'mastery', 'title': 'Domínio estimado', 'value': estimate['score'], 'reason': estimate['reason']},
        {'key': 'reviews', 'title': 'Revisões em dia', 'value': review_percent, 'reason': f'{len(due)} de {len(reviews)} últimas revisões de assuntos vencidas. Flashcards são contabilizados separadamente.'},
        {'key': 'pace', 'title': 'Ritmo do plano', 'value': min(100, round(100*current/planned, 1)) if planned else None, 'reason': f'{current} min registrados / {planned} min planejados nos últimos 7 dias; minutos não comprovam conclusão do plano.'},
        {'key': 'questions', 'title': 'Acertos registrados', 'value': accuracy, 'reason': f'{question_totals[1]}/{question_totals[0]} questões; inclui registros agregados, que não aumentam o domínio estimado.'},
        {'key': 'consistency', 'title': 'Consistência do plano', 'value': consistency, 'reason': f'{sum(e.completed for e in past_entries)}/{len(past_entries)} blocos concluídos nos últimos 28 dias.'}]
    values = [c['value'] for c in components if c['value'] is not None]
    health = 'insufficient' if len(values) < 3 else 'attention' if any(v < 50 for v in values) else 'moderate' if any(v < 80 for v in values) else 'stable'
    ledger = [{'id': a['attempt_id'], 'kind': 'question', 'at': a['answered_at'],
        'topic_key': a['topic_key'], 'notebook_id': a['notebook_id'], 'correct': a['correct'],
        'affects_mastery': True} for a in individual[:100]]
    ledger += [{'id': str(s.id), 'kind': 'session', 'at': s.date.isoformat(),
        'notebook_id': str(s.notebook_id), 'minutes': s.duration_minutes, 'affects_mastery': False} for s in sessions[:100]]
    # Ledger shows actual occurrence time, never a future review due date.
    review_facts = (await session.execute(select(ReviewEvent, StudyTopic.notebook_id, StudyTopic.topic_key)
        .join(StudyTopic, (StudyTopic.id == ReviewEvent.topic_id) & (StudyTopic.user_id == ReviewEvent.user_id))
        .where(ReviewEvent.user_id == uid, StudyTopic.notebook_id.in_(ids), StudyTopic.archived_at.is_(None))
        .order_by(ReviewEvent.reviewed_at.desc(), ReviewEvent.id).limit(100))).all()
    ledger += [{'id': str(r.id), 'kind': 'review', 'at': r.reviewed_at.isoformat(),
        'notebook_id': str(nid), 'topic_key': key, 'affects_mastery': False,
        'due_date': r.next_review.isoformat() if r.next_review else None} for r, nid, key in review_facts]
    aggregate_facts = list((await session.scalars(select(QuestionAttempt).where(
        QuestionAttempt.user_id == uid, QuestionAttempt.notebook_id.in_(ids),
        QuestionAttempt.question_id.is_(None)).order_by(QuestionAttempt.answered_at.desc(), QuestionAttempt.id).limit(100))).all())
    ledger += [{'id': str(r.id), 'kind': 'practice', 'at': r.answered_at.isoformat(),
        'notebook_id': str(r.notebook_id), 'total': r.total, 'correct_count': r.correct,
        'affects_mastery': False} for r in aggregate_facts]
    exam_facts = (await session.execute(select(ExamAttempt, Exam.kind)
        .join(Exam, (Exam.id == ExamAttempt.exam_id) & (Exam.user_id == ExamAttempt.user_id))
        .where(ExamAttempt.user_id == uid, Exam.program_id == program.id, Exam.archived_at.is_(None))
        .order_by(ExamAttempt.completed_at.desc(), ExamAttempt.id).limit(100))).all()
    ledger += [{'id': str(r.id), 'kind': 'exam',
        'at': r.completed_at.isoformat(), 'score': r.score, 'affects_mastery': False,
        'notice': 'Resultado do simulado; respostas individuais vinculadas alimentam o domínio.'} for r, kind in exam_facts]
    ledger += [{'id': str(r.id), 'kind': 'flashcard', 'at': r.reviewed_at.isoformat(),
        'notebook_id': str(nid), 'quality': r.quality, 'affects_mastery': False} for r, nid in card_reviews[:100]]
    weekly = []
    for offset in (21, 14, 7, 0):
        end = today-timedelta(days=offset); start = end-timedelta(days=6)
        sampled = [a for a in individual if start.isoformat() <= a['date'] <= end.isoformat()]
        weekly.append({'start': start.isoformat(), 'end': end.isoformat(),
            'minutes': sum(s.duration_minutes for s in sessions if start <= s.date <= end),
            'questions': len(sampled), 'accuracy': round(100*sum(a['correct'] for a in sampled)/len(sampled), 1) if sampled else None})
    return {'version': VERSION, 'preparation_id': str(program.id), 'target': {
        'name': target.name if target else program.name, 'kind': target.kind if target else 'custom',
        'board': target.board if target else None, 'position': target.position if target else None,
        'institution': target.institution if target else None, 'edition': target.edition if target else None,
        'provenance': target.metadata_origin if target else 'manual'},
        'exam_date': exam_date.isoformat() if exam_date else None, 'days_remaining': days,
        'next_session': entry_json(upcoming) if upcoming else None,
        'coverage': coverage, 'mastery': estimate,
        'study_debt': {'overdue_blocks': len(debt_entries), 'minutes': sum(e.minutes for e in debt_entries),
            'unstarted_topics': sum(n['stage'] == 'not_started' for n in graph), 'window_days': 28},
        'reviews_due': {'topics': len(due), 'flashcards': flashcards_due},
        'performance': {'questions': question_totals[0], 'correct': question_totals[1], 'accuracy': accuracy},
        'recent_trend': weekly, 'current_pace': {'minutes_per_week': current, 'window_days': 7},
        'required_pace': {'minutes_per_week': planned if plan else None,
            'uncovered_topics_per_week': round(7*(total_topics-covered_count)/days, 1) if days and days > 0 and total_topics else None,
            'basis': 'scheduled_last_7_days' if plan else 'unknown',
            'notice': 'Carga do plano registrado; sem estimativa confiável de horas por assunto, não prevê conclusão do edital.'},
        'candidate_model': {'completed_sessions': len(sessions), 'window_days': 28,
            'mean_duration_minutes': round(sum(s.duration_minutes for s in sessions)/len(sessions), 1) if sessions else None,
            'availability': plan.availability if plan else None, 'consistency': consistency,
            'error_causes': dict(Counter(a['error_reason'] or 'unclassified' for a in individual if not a['correct'])),
            'difficult_subjects': sorted(candidates, key=lambda c: (-c['priority'], c['id']))[:5],
            'confidence': estimate['confidence'], 'preferred_time': None},
        'health': {'status': health, 'components': components, 'notice': 'Indicadores operacionais, não probabilidade de aprovação.'},
        'risk_areas': sorted(candidates, key=lambda c: (-c['priority'], c['id']))[:5],
        'next_candidates': sorted(candidates, key=lambda c: (-c['priority'], c['id']))[:10],
        'syllabus_graph': {'preparation_id': str(program.id), 'disciplines': [
            {'id': str(b.id), 'parent_id': str(program.id), 'title': b.name,
             'materials': materials[b.id], 'recommended_resources': (b.recursos_recomendados or [])[:30],
             'sources': (b.fontes or [])[:30]} for b in books], 'topics': graph},
        'mastery_evidence_ids': [a['attempt_id'] for a in individual],
        'evidence_ledger': sorted(ledger, key=lambda r: (r['at'] or '', r['id']), reverse=True)[:100],
        'source_freshness': {'computed_at': today.isoformat(), 'program_updated_at': program.updated_at.isoformat(),
            'latest_question_at': individual[0]['answered_at'] if individual else None,
            'official_source_checked_at': None},
        'truncated': truncated, 'limits': {'topics': LIMIT, 'questions': 5000, 'ledger': 100},
        'unlinked_evidence': ['essay_corrections_have_no_preparation_reference'],
        'requires_confirmation': True}
