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
from services.exam_sessions import execution,validate_answers
from exam_intelligence import post_mortem


async def submit_exam(user_id,exam_id,answers,duration_seconds,request_key,kind='simulado',session_id=None,revision=None):
    if not request_key and kind=='simulado':
        raise HTTPException(422,'Idempotency-Key obrigatório para concluir o simulado.')
    if type(duration_seconds) is not int or not 0 <= duration_seconds <= 86400:
        raise HTTPException(422,'Tempo de prova inválido.')
    async def apply(session,user):
        submitted_answers=answers;submitted_duration=duration_seconds
        repo = ExamRepository(session)
        exam = await repo.get(user.id,exam_id)
        if exam is None or exam.kind!=kind:
            raise HTTPException(404,'Simulado não encontrado.')
        pairs = await repo.questions(user.id,exam_id)
        active=execution(exam)
        if session_id:
            if not active or active['session_id']!=str(session_id) or active['status']!='active' or active['revision']!=revision:
                raise HTTPException(409,'Execução já concluída ou alterada. Recarregue o resultado/progresso.')
            submitted_answers=active['answers'];submitted_duration=active['elapsed_seconds']
        elif active and active['status']=='active':
            raise HTTPException(409,'Conclua a execução ativa com sua identidade e revisão.')
        validate_answers(pairs,submitted_answers)
        questions = [{'question_text':q.statement,'correct_answer':q.correct_answer,'explanation':q.explanation,
            'weight':weight,'question_number':index+1 if (exam.blueprint or {}).get('numbering')=='exam_position' else q.provenance.get('question_number',index+1),
            'disciplina':q.provenance.get('disciplina'),'subdisciplina':q.provenance.get('subdisciplina')} for index,(q,weight) in enumerate(pairs)]
        rules=(exam.blueprint or {}).get('scoring',{})
        result = grade(questions,submitted_answers,rules)
        metadata={}
        for item in submitted_answers:
            confidence=item.get('confidence');changed=item.get('changed_answer');seconds=item.get('seconds')
            if confidence not in (None,'guess','uncertain','confident') or (changed is not None and type(changed) is not bool) or (seconds is not None and (type(seconds) is not int or not 0<=seconds<=86400)):
                raise HTTPException(422,'Metadados da resposta inválidos.')
            metadata[item['question_idx']]={'confidence':confidence,'changed_answer':changed,'seconds':seconds}
        for answer in result['answers']:
            answer.update(metadata.get(answer['question_idx'],{'confidence':None,'changed_answer':None,'seconds':None}))
            answer['skipped']=not answer['answered']
            answer['question_id']=str(pairs[answer['question_idx']][0].id)
            answer['question_type']=pairs[answer['question_idx']][0].question_type
        ids=[q.id for q,_ in pairs]
        recurring=(await session.scalars(select(QuestionAttempt.question_id).where(QuestionAttempt.user_id==user.id,
            QuestionAttempt.question_id.in_(ids),QuestionAttempt.correct==0,
            func.coalesce(QuestionAttempt.evidence['answered'].as_boolean(),True)).distinct())).all()
        result['post_mortem']=post_mortem(result,submitted_duration,exam.duration_minutes,[str(i) for i in recurring])
        previous = await repo.latest_attempt(user.id,exam_id)
        now = datetime.now(timezone.utc)
        if session_id:
            result['execution']={'session_id':str(session_id),'started_at':active['started_at'],
                'completed_at':now.isoformat(),'revision':revision,'timing_basis':'declared_visible_page_interaction'}
        row = ExamAttempt(user_id=user.id,exam_id=exam_id,completed_at=now,duration_seconds=submitted_duration,
            score=result['score'],scoring_version=rules.get('version','all_questions_weighted_v1'),result_details=result)
        session.add(row)
        await session.flush()
        if session_id:
            exam.blueprint={**exam.blueprint,'execution':{**active,'status':'completed','attempt_id':str(row.id)}}
        linked = 0
        reviewed_topics=set()
        for answer in result['answers']:
            question = pairs[answer['question_idx']][0]
            # Preserve blank answers as facts too; evidence says whether an answer was given.
            session.add(QuestionAttempt(user_id=user.id,notebook_id=question.notebook_id,topic_id=question.topic_id,
                question_id=question.id,exam_attempt_id=row.id,source=kind,answered_at=now,total=1,
                correct=int(answer['is_correct']),answer=answer['selected_answer'],
                duration_seconds=answer['seconds'],
                evidence={'answered':answer['answered'],'weight':answer['weight'],'board':exam.provenance.get('banca'),
                    'confidence':answer['confidence'],'changed_answer':answer['changed_answer'],'skipped':answer['skipped'],
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
        earned = int(result['score']/10)*3 if kind=='quiz' else result['correct_count']*2
        apply_xp(user,earned)
        row.result_details={**result,'change_since_previous':round(result['score']-previous.score,1) if previous else None,
            'mastery_answers_linked':linked,'xp_earned':earned,'new_xp':user.xp}
        return {**row.result_details,'attempt_id':str(row.id),'simulado_id':str(exam_id),'title':exam.title,
            'program_id':str(exam.program_id) if exam.program_id else None,'banca':exam.provenance.get('banca'),
            'disciplina':exam.provenance.get('disciplina'),'concurso':exam.provenance.get('concurso'),
            'time_spent_seconds':submitted_duration,'completed_at':now.isoformat(),
            'change_since_previous':round(result['score']-previous.score,1) if previous else None,
            'mastery_answers_linked':linked,'xp_earned':earned,'new_xp':user.xp}
    fingerprint=['submit-'+kind,str(exam_id),answers,duration_seconds]
    if session_id:fingerprint.extend([str(session_id),revision])
    return await run_activity(user_id,request_key,fingerprint,apply)
