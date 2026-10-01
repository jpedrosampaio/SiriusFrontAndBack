from datetime import datetime, timezone
from fastapi import HTTPException
from db.activity import run_activity
from db.models.exams import ExamAttempt
from db.models.studies import QuestionAttempt
from db.repositories.exams import ExamRepository
from services.planning import apply_xp
from simulado_scoring import grade


async def submit_exam(user_id,exam_id,answers,duration_seconds,request_key):
    if not request_key:
        raise HTTPException(422,'Idempotency-Key obrigatório para concluir o simulado.')
    if type(duration_seconds) is not int or not 0 <= duration_seconds <= 86400:
        raise HTTPException(422,'Tempo de prova inválido.')
    async def apply(session,user):
        repo = ExamRepository(session)
        exam = await repo.get(user.id,exam_id)
        if exam is None:
            raise HTTPException(404,'Simulado não encontrado.')
        pairs = await repo.questions(user.id,exam_id)
        questions = [{'question_text':q.statement,'correct_answer':q.correct_answer,'explanation':q.explanation,
            'weight':weight,'disciplina':q.provenance.get('disciplina'),'subdisciplina':q.provenance.get('subdisciplina')} for q,weight in pairs]
        result = grade(questions,answers)
        previous = await repo.latest_attempt(user.id,exam_id)
        now = datetime.now(timezone.utc)
        row = ExamAttempt(user_id=user.id,exam_id=exam_id,completed_at=now,duration_seconds=duration_seconds,
            score=result['score'],scoring_version='all_questions_weighted_v1',result_details=result)
        session.add(row)
        await session.flush()
        linked = 0
        for answer in result['answers']:
            question = pairs[answer['question_idx']][0]
            # Preserve blank answers as facts too; evidence says whether an answer was given.
            session.add(QuestionAttempt(user_id=user.id,notebook_id=question.notebook_id,topic_id=question.topic_id,
                question_id=question.id,exam_attempt_id=row.id,source='simulado',answered_at=now,total=1,
                correct=int(answer['is_correct']),answer=answer['selected_answer'],
                evidence={'answered':answer['answered'],'weight':answer['weight']}))
            linked += int(bool(question.topic_id and answer['answered']))
        earned = result['correct_count']*2
        apply_xp(user,earned)
        return {**result,'attempt_id':str(row.id),'simulado_id':str(exam_id),'title':exam.title,
            'time_spent_seconds':duration_seconds,'completed_at':now.isoformat(),
            'change_since_previous':round(result['score']-previous.score,1) if previous else None,
            'mastery_answers_linked':linked,'xp_earned':earned,'new_xp':user.xp}
    return await run_activity(user_id,request_key,['submit-simulado',str(exam_id),answers,duration_seconds],apply)
