import json
import re
from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field
from sqlalchemy import select
from db.session import unit_of_work
from db.models.studies import Notebook,StudyNote
from db.models.exams import Exam,Question,ExamQuestion
from services.auth_routes import account
from services.study_activity_routes import mutate
from services.studies_catalog import owned
from services import exam_catalog,study_cards
from services.exams import submit_exam
from services.exam_routes import Submission

router=APIRouter(prefix='/study/quizzes')


class QuizBody(BaseModel):
    notebook_id: UUID
    title: str = Field(min_length=1,max_length=300)
    questions: list[dict] = Field(min_length=1,max_length=100)


class GenerateBody(BaseModel):
    notebook_id: UUID
    count: int = Field(default=5,ge=1,le=100)


def quiz_json(document):
    return {**{k:document[k] for k in ('user_id','notebook_id','title','created_at')},
        'quiz_id':document['simulado_id'],'ai_generated':document.get('source_type')=='ai_generated',
        'questions':[{**q,'question':q['question_text']} for q in document['questions']]}


async def save(request,user,body,generated=False):
    questions=[]
    for q in body.questions:
        if not isinstance(q.get('options'),list): raise HTTPException(422,'Alternativas inválidas.')
        questions.append({**q,'question_text':q.get('question') or q.get('question_text'),
            'notebook_id':str(body.notebook_id),'weight':1})
    result=await exam_catalog.create(user['user_id'],request.headers.get('Idempotency-Key'),
        ['create-quiz',body.model_dump(mode='json'),generated],{'title':body.title,'notebook_id':str(body.notebook_id),
            'source_type':'ai_generated' if generated else 'manual'},questions,kind='quiz')
    return quiz_json(result['simulado'])


@router.post('')
async def create_quiz(request: Request,body: QuizBody):
    return await save(request,await account(request),body)


@router.get('')
async def quizzes(request: Request,notebook_id: UUID | None=None):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        query=select(Exam).join(Notebook,(Notebook.id==Exam.notebook_id)&(Notebook.user_id==Exam.user_id)).where(
            Exam.user_id==uid,Exam.kind=='quiz',Exam.archived_at.is_(None),Notebook.archived_at.is_(None))
        if notebook_id: query=query.where(Exam.notebook_id==notebook_id)
        rows=(await session.scalars(query.order_by(Exam.created_at.desc()).limit(100))).all()
        pairs=(await session.execute(select(ExamQuestion.exam_id,Question,ExamQuestion.weight,ExamQuestion.position).join(Question,
            (Question.id==ExamQuestion.question_id)&(Question.user_id==ExamQuestion.user_id)).where(ExamQuestion.user_id==uid,
                ExamQuestion.exam_id.in_([r.id for r in rows])).order_by(ExamQuestion.position))).all()
        grouped={}
        for eid,q,weight,index in pairs: grouped.setdefault(eid,[]).append(exam_catalog.question_json(q,weight,index))
        return [quiz_json({**exam_catalog.exam_json(r),'questions':grouped.get(r.id,[])}) for r in rows]


@router.post('/{quiz_id}/attempt')
async def submit_quiz(request: Request,quiz_id: UUID,body: Submission):
    user=await account(request)
    result=await submit_exam(UUID(user['user_id']),quiz_id,body.answers,body.time_spent_seconds,request.headers.get('Idempotency-Key'),kind='quiz')
    result['quiz_id']=result.pop('simulado_id')
    result['answers']=[{**a,'correct':a['is_correct']} for a in result['answers']]
    return result


@router.delete('/{quiz_id}')
async def remove_quiz(request: Request,quiz_id: UUID):
    async def apply(session,user):
        row=await owned(session,Exam,user.id,quiz_id)
        if row.kind!='quiz': raise HTTPException(404,'Quiz não encontrado.')
        row.archived_at=datetime.now(timezone.utc)
        return {'message':'Quiz deleted'}
    return await mutate(request,['delete-quiz',str(quiz_id)],apply)


@router.post('/generate')
async def generate_quiz(request: Request,body: GenerateBody):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        book=await owned(session,Notebook,uid,body.notebook_id); name=book.name
        notes=(await session.scalars(select(StudyNote).where(StudyNote.user_id==uid,StudyNote.notebook_id==book.id)
            .order_by(StudyNote.created_at).limit(50))).all()
        if not notes: raise HTTPException(404,'No notes found in this notebook')
        content='\n\n'.join(f'## {n.title}\n{n.content}' for n in notes)[:5000]
    response=await study_cards._llm(f'Com base no conteúdo, gere {body.count} perguntas de múltipla escolha.\n{content}\n'
        'Responda JSON: [{"question":"Pergunta","options":["A) opção 1","B) opção 2","C) opção 3","D) opção 4"],'
        '"correct_answer":"A","explanation":"Explicação"}]. Teste compreensão, use opções plausíveis e explicações educativas.',
        session_id=user['user_id'],system_message='Você é um professor experiente. Crie questões que avaliem compreensão profunda do conteúdo.',
        user_id=user['user_id'],task='study_question_generation')
    match=re.search(r'\[[\s\S]*\]',response)
    if not match: return {'message':response}
    try:
        values=json.loads(match.group())
        if len(values)!=body.count: raise ValueError()
        payload=QuizBody(notebook_id=body.notebook_id,title=f'Quiz: {name}',questions=values)
    except (ValueError,TypeError): raise HTTPException(502,'A IA retornou questões inválidas; nenhum quiz foi salvo.')
    return await save(request,user,payload,True)
