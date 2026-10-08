from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select,func,Date,or_
from db.models.studies import Notebook,StudyTopic,QuestionAttempt,ReviewEvent
from db.models.exams import Question
from study_mastery import mastery,adaptive_review
from question_intelligence import question_origin


def attempt_json(row,notebook,topic,question,zone):
    metadata=row.evidence or {}
    return {'attempt_id':str(row.id),'user_id':str(row.user_id),'notebook_id':str(row.notebook_id),
        'program_id':str(notebook.program_id) if notebook.program_id else None,'topic_key':topic.topic_key if topic else None,
        'title':topic.name if topic else notebook.name,'question':question.statement if question else metadata.get('question',''),
        'question_id':metadata.get('external_question_id'),'answer':row.answer or '', 'correct':bool(row.correct),
        'seconds':row.duration_seconds or 0,'source':row.source,'board':metadata.get('board',''),'exam':metadata.get('exam',''),
        'position':metadata.get('position',''),'error_reason':row.error_cause,'difficulty':metadata.get('difficulty'),
        'date':row.answered_at.astimezone(ZoneInfo(zone)).date().isoformat(),'created_at':row.created_at.isoformat(),
        'answered_at':row.answered_at.isoformat(),'internal_question_id':str(row.question_id) if row.question_id else None,
        'exam_attempt_id':str(row.exam_attempt_id) if row.exam_attempt_id else None,
        'confidence':metadata.get('confidence'),'skipped':metadata.get('skipped',metadata.get('answered') is False),
        'changed_answer':metadata.get('changed_answer'),
        'question_provenance':question_origin(question.source,question.provenance) if question else 'unknown'}


async def attempts(session,uid,zone,*,program_id=None,notebook_id=None,topic_id=None,limit=5000,active_topics=False):
    query=select(QuestionAttempt,Notebook,StudyTopic,Question).join(Notebook,
        (Notebook.id==QuestionAttempt.notebook_id)&(Notebook.user_id==QuestionAttempt.user_id))
    query=query.outerjoin(StudyTopic,(StudyTopic.id==QuestionAttempt.topic_id)&(StudyTopic.user_id==QuestionAttempt.user_id))
    query=query.outerjoin(Question,(Question.id==QuestionAttempt.question_id)&(Question.user_id==QuestionAttempt.user_id))
    query=query.where(QuestionAttempt.user_id==uid,QuestionAttempt.total==1,QuestionAttempt.question_id.is_not(None),Notebook.archived_at.is_(None))
    query=query.where(or_(QuestionAttempt.evidence['answered'].as_boolean().is_(None),QuestionAttempt.evidence['answered'].as_boolean().is_(True)))
    if program_id: query=query.where(Notebook.program_id==program_id)
    if notebook_id: query=query.where(QuestionAttempt.notebook_id==notebook_id)
    if topic_id: query=query.where(QuestionAttempt.topic_id==topic_id)
    if active_topics: query=query.where(or_(QuestionAttempt.topic_id.is_(None),StudyTopic.archived_at.is_(None)))
    rows=(await session.execute(query.order_by(QuestionAttempt.answered_at.desc(),QuestionAttempt.id.desc()).limit(limit))).all()
    return [attempt_json(*row,zone) for row in rows]


async def latest_reviews(session,uid,*,program_id=None,due=None,limit=1000):
    latest=select(ReviewEvent).where(ReviewEvent.user_id==uid).distinct(ReviewEvent.topic_id)
    latest=latest.order_by(ReviewEvent.topic_id,ReviewEvent.reviewed_at.desc(),ReviewEvent.id.desc()).subquery()
    query=select(latest.c.id,latest.c.next_review,latest.c.result,StudyTopic,Notebook).join(StudyTopic,
        (StudyTopic.id==latest.c.topic_id)&(StudyTopic.user_id==latest.c.user_id))
    query=query.join(Notebook,(Notebook.id==StudyTopic.notebook_id)&(Notebook.user_id==StudyTopic.user_id))
    query=query.where(Notebook.archived_at.is_(None),StudyTopic.archived_at.is_(None))
    if program_id: query=query.where(Notebook.program_id==program_id)
    if due: query=query.where(latest.c.next_review<=due)
    rows=(await session.execute(query.order_by(latest.c.next_review,latest.c.id).limit(limit))).all()
    return [{'review_id':str(identity),'notebook_id':str(nb.id),'program_id':str(nb.program_id) if nb.program_id else None,
        'topic_key':topic.topic_key,'title':topic.name,'due_date':day.isoformat() if day else None,
        'reason':reason if reason!='practice' else 'Revisão sugerida a partir da prática registrada.'} for identity,day,reason,topic,nb in rows]
