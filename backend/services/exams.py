from datetime import date, datetime, timezone
from sqlalchemy import select,func,Date
from fastapi import HTTPException
from db.activity import run_activity
from db.models.exams import ExamAttempt
from db.models.studies import QuestionAttempt,ReviewEvent
from db.repositories.exams import ExamRepository
from services.planning import apply_xp
from simulado_scoring import grade
from services.time import local_today
from services.study_evidence import attempts
from study_mastery import adaptive_review


async def submit_exam(user_id,exam_id,answers,duration_seconds,request_key):
    if not request_key:
        raise HTTPException(422,'Idempotency-Key obrigatório para concluir o simulado.')
    if type(duration_seconds) is not int or not 0 <= duration_seconds <= 86400:
        raise HTTPException(422,'Tempo de prova inválido.')
    async def apply(session,user):
        repo = ExamRepository(session)
        exam = await repo.get(user.id,exam_id)
        if exam is None or exam.kind!='simulado':
            raise HTTPException(404,'Simulado não encontrado.')
        pairs = await repo.questions(user.id,exam_id)
        questions = [{'question_text':q.statement,'correct_answer':q.correct_answer,'explanation':q.explanation,
            'weight':weight,'question_number':q.provenance.get('question_number',index+1),
            'disciplina':q.provenance.get('disciplina'),'subdisciplina':q.provenance.get('subdisciplina')} for index,(q,weight) in enumerate(pairs)]
        result = grade(questions,answers)
        previous = await repo.latest_attempt(user.id,exam_id)
        now = datetime.now(timezone.utc)
        row = ExamAttempt(user_id=user.id,exam_id=exam_id,completed_at=now,duration_seconds=duration_seconds,
            score=result['score'],scoring_version='all_questions_weighted_v1',result_details=result)
        session.add(row)
        await session.flush()
        linked = 0
        reviewed_topics=set()
        for answer in result['answers']:
            question = pairs[answer['question_idx']][0]
            # Preserve blank answers as facts too; evidence says whether an answer was given.
            session.add(QuestionAttempt(user_id=user.id,notebook_id=question.notebook_id,topic_id=question.topic_id,
                question_id=question.id,exam_attempt_id=row.id,source='simulado',answered_at=now,total=1,
                correct=int(answer['is_correct']),answer=answer['selected_answer'],
                evidence={'answered':answer['answered'],'weight':answer['weight'],'board':exam.provenance.get('banca'),
                    'exam':exam.title,'external_question_id':str(question.id)}))
            linked += int(bool(question.topic_id and answer['answered']))
            if question.topic_id and answer['answered']: reviewed_topics.add((question.notebook_id,question.topic_id))
        await session.flush()
        today=local_today(user.timezone)
        for notebook_id,topic_id in reviewed_topics:
            history=await attempts(session,user.id,user.timezone,notebook_id=notebook_id,topic_id=topic_id,limit=500)
            review_day=func.timezone(user.timezone,ReviewEvent.reviewed_at).cast(Date)
            previous_reviews=await session.scalar(select(func.count(func.distinct(review_day))).where(
                ReviewEvent.user_id==user.id,ReviewEvent.topic_id==topic_id,review_day<today))
            review=adaptive_review(history,today,previous_reviews=previous_reviews)
            session.add(ReviewEvent(user_id=user.id,topic_id=topic_id,reviewed_at=now,
                result=review['reason'],next_review=date.fromisoformat(review['due_date'])))
        earned = result['correct_count']*2
        apply_xp(user,earned)
        row.result_details={**result,'change_since_previous':round(result['score']-previous.score,1) if previous else None,
            'mastery_answers_linked':linked,'xp_earned':earned,'new_xp':user.xp}
        return {**row.result_details,'attempt_id':str(row.id),'simulado_id':str(exam_id),'title':exam.title,
            'program_id':str(exam.program_id) if exam.program_id else None,'banca':exam.provenance.get('banca'),
            'disciplina':exam.provenance.get('disciplina'),'concurso':exam.provenance.get('concurso'),
            'time_spent_seconds':duration_seconds,'completed_at':now.isoformat(),
            'change_since_previous':round(result['score']-previous.score,1) if previous else None,
            'mastery_answers_linked':linked,'xp_earned':earned,'new_xp':user.xp}
    return await run_activity(user_id,request_key,['submit-simulado',str(exam_id),answers,duration_seconds],apply)
