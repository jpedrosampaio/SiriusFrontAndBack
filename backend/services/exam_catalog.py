from datetime import datetime,timezone
from uuid import UUID
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func
from db.activity import run_activity
from db.session import unit_of_work
from db.models.exams import Exam,Question,ExamQuestion,ExamAttempt
from db.models.studies import StudyArea,StudyProgram,Notebook,StudyTopic
from db.repositories.exams import ExamRepository
from services.studies_catalog import owned,public
from services.planning import apply_xp
from study_resources import positive_number
from question_intelligence import question_origin,provider_for_source


def identity(value):
    try: return UUID(str(value))
    except (ValueError,TypeError,AttributeError): raise HTTPException(422,'Identificador inválido.')


async def scope(session,uid,area_id=None,program_id=None,notebook_id=None,topic_key=None):
    area=await owned(session,StudyArea,uid,identity(area_id)) if area_id else None
    program=await owned(session,StudyProgram,uid,identity(program_id)) if program_id else None
    book=await owned(session,Notebook,uid,identity(notebook_id)) if notebook_id else None
    if program and area and program.area_id!=area.id: raise HTTPException(422,'Preparação não pertence à área.')
    if book and program and book.program_id!=program.id: raise HTTPException(422,'Matéria não pertence à preparação.')
    if book and area and book.area_id!=area.id: raise HTTPException(422,'Matéria não pertence à área.')
    topic=None
    if topic_key is not None:
        if not book: raise HTTPException(422,'Selecione a matéria para vincular o assunto.')
        topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==uid,StudyTopic.notebook_id==book.id,
            StudyTopic.topic_key==str(topic_key),StudyTopic.archived_at.is_(None)))
        if topic is None: raise HTTPException(422,'Assunto não encontrado.')
    return area,program,book,topic


async def validate_scope(uid,**kwargs):
    async with unit_of_work() as session:
        _,_,book,topic=await scope(session,identity(uid),**kwargs)
        return public(book) if book else None,topic.name if topic else None


def exam_json(exam):
    return jsonable_encoder({**exam.provenance,'simulado_id':exam.id,'user_id':exam.user_id,'title':exam.title,
        'description':exam.description or '', 'area_id':exam.area_id,'program_id':exam.program_id,'notebook_id':exam.notebook_id,
        'status':exam.status,'duration_minutes':exam.duration_minutes,
        'blueprint':{k:v for k,v in (exam.blueprint or {}).items() if k!='execution'},
        'execution_status':(exam.blueprint or {}).get('execution',{}).get('status'),'created_at':exam.created_at})


def question_json(question,weight,index,topic_key=None):
    provider=provider_for_source(question.source)
    origin=provider.origin(question.provenance) if provider else question_origin(question.source,question.provenance)
    return {**question.provenance,'question_id':str(question.id),'question_number':question.provenance.get('question_number',index+1),
        'provider':provider.name if provider else 'unknown','origin':origin,'generated_by_ai':origin=='ai_generated',
        'question_text':question.statement,'options':question.options,'correct_answer':question.correct_answer,
        'explanation':question.explanation or '', 'type':question.question_type,'weight':weight,
        'notebook_id':str(question.notebook_id) if question.notebook_id else None,'topic_key':topic_key}


def attempt_json(row,exam):
    return jsonable_encoder({**row.result_details,'attempt_id':row.id,'simulado_id':row.exam_id,'user_id':row.user_id,
        'title':exam.title,'program_id':exam.program_id,'banca':exam.provenance.get('banca'),
        'disciplina':exam.provenance.get('disciplina'),'concurso':exam.provenance.get('concurso'),
        'time_spent_seconds':row.duration_seconds,'completed_at':row.completed_at,'score':row.score})


async def create_in_session(session,user,document,questions,xp=0,kind="simulado"):
    if not isinstance(questions,list) or not 1<=len(questions)<=500: raise HTTPException(422,"Quantidade de questões inválida.")
    area,program,book,_=await scope(session,user.id,document.get('area_id'),document.get('program_id'),document.get('notebook_id'))
    exam=Exam(user_id=user.id,area_id=book.area_id if book else (program.area_id if program else (area.id if area else None)),
        program_id=book.program_id if book else (program.id if program else None),notebook_id=book.id if book else None,
        title=document['title'],description=document.get('description'),kind=kind,status='ready',
        duration_minutes=document.get('duration_minutes'),provenance={k:document[k] for k in
            ('source_type','banca','disciplina','concurso','question_type','difficulty','pdf_filename','year_detected') if k in document})
    session.add(exam); await session.flush(); values=[]
    for index,data in enumerate(questions):
        if not isinstance(data,dict) or not data.get('question_text') or not data.get('correct_answer'):
            raise HTTPException(422,'Questão sem enunciado ou gabarito.')
        _,_,notebook,topic=await scope(session,user.id,program_id=str(exam.program_id) if exam.program_id else None,
            notebook_id=data.get('notebook_id') or document.get('notebook_id'),topic_key=data.get('topic_key'))
        weight=positive_number(data.get('weight',1))
        if weight is None or weight>100: raise HTTPException(422,'Peso de questão inválido.')
        question=Question(user_id=user.id,notebook_id=notebook.id if notebook else None,topic_id=topic.id if topic else None,
            statement=str(data['question_text']),question_type=data.get('type') or document.get('question_type','multipla_escolha'),
            options=data.get('options') or [],correct_answer=str(data['correct_answer']),explanation=data.get('explanation'),
            source=document.get('source_type','manual'),provenance={k:data[k] for k in
                ('question_number','texto_base','disciplina','subdisciplina','difficulty','provenance','provider','source_context','validation_level') if k in data})
        session.add(question); await session.flush()
        session.add(ExamQuestion(user_id=user.id,exam_id=exam.id,question_id=question.id,position=index,weight=weight))
        values.append(question_json(question,weight,index,topic.topic_key if topic else None))
    apply_xp(user,xp); await session.flush()
    return {'success':True,'simulado':{**exam_json(exam),'questions':values,'questions_count':len(values)},
        'message':f'Simulado criado com {len(values)} questões!','xp_earned':xp}


async def create(uid,key,fingerprint,document,questions,xp=0,kind="simulado"):
    async def apply(session,user):
        return await create_in_session(session,user,document,questions,xp,kind)
    return await run_activity(identity(uid),key,fingerprint,apply)


async def details(session,uid,exam_id):
    exam=await owned(session,Exam,uid,exam_id)
    if exam.kind!='simulado': raise HTTPException(404,'Simulado não encontrado.')
    pairs=await ExamRepository(session).questions(uid,exam_id)
    topic_ids=[q.topic_id for q,_ in pairs if q.topic_id]
    topics=dict((await session.execute(select(StudyTopic.id,StudyTopic.topic_key).where(StudyTopic.user_id==uid,StudyTopic.id.in_(topic_ids)))).all())
    attempts=(await session.scalars(select(ExamAttempt).where(ExamAttempt.user_id==uid,ExamAttempt.exam_id==exam_id)
        .order_by(ExamAttempt.completed_at.desc()).limit(50))).all()
    return {**exam_json(exam),'questions':[question_json(q,w,i,topics.get(q.topic_id)) for i,(q,w) in enumerate(pairs)],
        'questions_count':len(pairs),'attempts':[attempt_json(a,exam) for a in attempts]}


async def list_exams(session,uid,area_id=None,program_id=None):
    query=select(Exam).where(Exam.user_id==uid,Exam.kind=='simulado',Exam.archived_at.is_(None))
    if area_id: query=query.where(Exam.area_id==area_id)
    if program_id: query=query.where(Exam.program_id==program_id)
    exams=(await session.scalars(query.order_by(Exam.created_at.desc()).limit(200))).all(); ids=[e.id for e in exams]
    counts=dict((await session.execute(select(ExamQuestion.exam_id,func.count()).where(ExamQuestion.user_id==uid,ExamQuestion.exam_id.in_(ids)).group_by(ExamQuestion.exam_id))).all())
    totals=(await session.execute(select(ExamAttempt.exam_id,func.count(),func.max(ExamAttempt.score)).where(ExamAttempt.user_id==uid,ExamAttempt.exam_id.in_(ids)).group_by(ExamAttempt.exam_id))).all()
    aggregates={eid:(count,best) for eid,count,best in totals}
    latest=(await session.scalars(select(ExamAttempt).where(ExamAttempt.user_id==uid,ExamAttempt.exam_id.in_(ids))
        .distinct(ExamAttempt.exam_id).order_by(ExamAttempt.exam_id,ExamAttempt.completed_at.desc(),ExamAttempt.id.desc()))).all()
    last={a.exam_id:a for a in latest}
    return [{**exam_json(e),'questions_count':counts.get(e.id,0),'attempts_count':aggregates.get(e.id,(0,0))[0],
        'best_score':aggregates.get(e.id,(0,0))[1],'last_attempt':attempt_json(last[e.id],e) if e.id in last else None} for e in exams]
