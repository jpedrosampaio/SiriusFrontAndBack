from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.exams import Exam,ExamAttempt
from services.auth_routes import account
from services.study_activity_routes import mutate
from services.studies_catalog import owned
from services.exams import submit_exam
from services.exam_catalog import list_exams,details,attempt_json

router=APIRouter(prefix='/study/simulados')


class Submission(BaseModel):
    answers: list[dict] = Field(max_length=500)
    time_spent_seconds: int = Field(default=0,ge=0,le=86400)


@router.get('')
async def list_simulados(request: Request,area_id: UUID | None=None,program_id: UUID | None=None):
    user=await account(request)
    async with unit_of_work() as session: return await list_exams(session,UUID(user['user_id']),area_id,program_id)


@router.get('/stats')
async def stats(request: Request):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        filters=(Exam.user_id==uid,Exam.kind=='simulado',Exam.archived_at.is_(None),ExamAttempt.user_id==uid)
        join=(Exam.id==ExamAttempt.exam_id)&(Exam.user_id==ExamAttempt.user_id)
        total_q=ExamAttempt.result_details['total_questions'].as_integer()
        correct=ExamAttempt.result_details['correct_count'].as_integer()
        count,average,best,questions,correct_count,seconds=(await session.execute(select(func.count(),func.avg(ExamAttempt.score),
            func.max(ExamAttempt.score),func.sum(total_q),func.sum(correct),func.sum(ExamAttempt.duration_seconds))
            .select_from(ExamAttempt).join(Exam,join).where(*filters))).one()
        groups={}
        for field in ('banca','disciplina','concurso'):
            label=func.coalesce(Exam.provenance[field].as_string(),'Outros')
            rows=(await session.execute(select(label,func.count(),func.sum(ExamAttempt.score),func.sum(correct),func.sum(total_q))
                .select_from(ExamAttempt).join(Exam,join).where(*filters).group_by(label))).all()
            groups['by_'+field]={name:{'attempts':n,'total_score':score,'total_correct':right or 0,'total_questions':total or 0,
                'avg_score':round(score/n,1),'accuracy':round((right or 0)/total*100,1) if total else 0}
                for name,n,score,right,total in rows if name}
        recent=(await session.execute(select(ExamAttempt,Exam).join(Exam,join).where(*filters)
            .order_by(ExamAttempt.completed_at.desc()).limit(10))).all()
        exam_count=await session.scalar(select(func.count()).select_from(Exam).where(Exam.user_id==uid,Exam.kind=='simulado',Exam.archived_at.is_(None)))
        return {'total_simulados':exam_count,'total_attempts':count,'average_score':round(average or 0,1),'best_score':round(best or 0,1),
            'total_questions_answered':questions or 0,'total_correct':correct_count or 0,
            'accuracy_rate':round((correct_count or 0)/questions*100,1) if questions else 0,'total_time_minutes':round((seconds or 0)/60,1),
            **groups,'recent_attempts':[attempt_json(row,exam) for row,exam in recent]}


@router.get('/{simulado_id}')
async def get_simulado(request: Request,simulado_id: UUID):
    user=await account(request)
    async with unit_of_work() as session: return await details(session,UUID(user['user_id']),simulado_id)


@router.post('/{simulado_id}/submit')
async def submit(request: Request,simulado_id: UUID,body: Submission):
    user=await account(request)
    return await submit_exam(UUID(user['user_id']),simulado_id,body.answers,body.time_spent_seconds,request.headers.get('Idempotency-Key'))


@router.get('/{simulado_id}/results')
async def results(request: Request,simulado_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        exam=await owned(session,Exam,uid,simulado_id)
        if exam.kind!='simulado': raise HTTPException(404,'Simulado não encontrado.')
        rows=(await session.scalars(select(ExamAttempt).where(ExamAttempt.user_id==uid,ExamAttempt.exam_id==simulado_id)
            .order_by(ExamAttempt.completed_at.desc()).limit(50))).all()
        return [attempt_json(r,exam) for r in rows]


@router.delete('/{simulado_id}')
async def remove(request: Request,simulado_id: UUID):
    async def apply(session,user):
        exam=await owned(session,Exam,user.id,simulado_id)
        if exam.kind!='simulado': raise HTTPException(404,'Simulado não encontrado.')
        exam.archived_at=datetime.now(timezone.utc)
        return {'message':'Simulado excluído.'}
    return await mutate(request,['delete-simulado',str(simulado_id)],apply)
