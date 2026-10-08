"""One active execution in the existing owned Exam JSON; CAS under activity lock."""
from datetime import datetime,timezone
from uuid import uuid4,UUID
from fastapi import HTTPException
from pydantic import BaseModel,Field,ConfigDict,StrictInt
from db.activity import run_activity
from db.models.exams import Exam
from services.studies_catalog import owned
from db.repositories.exams import ExamRepository
from simulado_scoring import grade
from typing import Literal

class AnswerEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question_idx:int=Field(ge=0,le=499,strict=True)
    selected_answer:str=Field(max_length=100)
    seconds:int|None=Field(default=None,ge=0,le=86400,strict=True)
    confidence:Literal['guess','uncertain','confident']|None=None
    changed_answer:bool|None=Field(default=None,strict=True)

class SessionSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:UUID
    revision:int=Field(ge=0,strict=True)
    answers:list[AnswerEvidence]=Field(max_length=500)
    current_question:int=Field(ge=0,le=499,strict=True)
    marked:list[StrictInt]=Field(default_factory=list,max_length=500)
    elapsed_seconds:int=Field(ge=0,le=86400,strict=True)

def execution(exam):return (exam.blueprint or {}).get('execution')

def acknowledgment(value):
    # Autosave receipts must not retain hundreds of full answer snapshots.
    return {key:value[key] for key in ('session_id','revision','status','elapsed_seconds','updated_at')}

def validate_answers(questions,answers):
    grade([{'correct_answer':q.correct_answer,'weight':w} for q,w in questions],answers)
    for a in answers:
        if a.get('confidence') not in (None,'guess','uncertain','confident') or (a.get('changed_answer') is not None and type(a['changed_answer']) is not bool):
            raise HTTPException(422,'Confiança ou alteração inválida.')
        s=a.get('seconds')
        if s is not None and (type(s) is not int or not 0<=s<=86400):raise HTTPException(422,'Tempo da questão inválido.')
        q=questions[a['question_idx']][0];value=a['selected_answer'].strip()
        options=q.options or []
        allowed={str(o).strip() for o in options}|{chr(65+i) for i in range(len(options))}
        if value and options and value not in allowed:raise HTTPException(422,'Alternativa inválida.')

async def start(uid,eid,key):
    if not key:raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        exam=await owned(session,Exam,user.id,eid)
        if exam.kind!='simulado':raise HTTPException(404,'Simulado não encontrado.')
        old=execution(exam)
        if old and old['status']=='active':return acknowledgment(old)
        pairs=await ExamRepository(session).questions(user.id,eid)
        validate_answers(pairs,[])
        now=datetime.now(timezone.utc).isoformat()
        value={'session_id':str(uuid4()),'revision':0,'status':'active','answers':[],
            'current_question':0,'marked':[],'elapsed_seconds':0,'started_at':now,'updated_at':now}
        exam.blueprint={**(exam.blueprint or {}),'execution':value}
        return acknowledgment(value)
    return await run_activity(uid,key,['exam-start',str(eid)],apply)

async def save(uid,eid,body,key):
    if not key:raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        exam=await owned(session,Exam,user.id,eid);old=execution(exam)
        if exam.kind!='simulado' or not old or old['status']!='active' or old['session_id']!=str(body.session_id):raise HTTPException(409,'Execução indisponível. Recarregue a prova.')
        if old['revision']!=body.revision:raise HTTPException(409,'Progresso alterado em outra aba. Recarregue antes de continuar.')
        values=body.model_dump(mode='json');answers=values['answers']
        pairs=await ExamRepository(session).questions(user.id,eid);validate_answers(pairs,answers)
        if body.current_question>=len(pairs) or any(type(i) is not int or not 0<=i<len(pairs) for i in body.marked) or len(set(body.marked))!=len(body.marked):raise HTTPException(422,'Navegação inválida.')
        if body.elapsed_seconds<old['elapsed_seconds']:raise HTTPException(422,'O tempo não pode retroceder.')
        if sum(a.get('seconds') or 0 for a in answers)>body.elapsed_seconds:raise HTTPException(422,'Tempos das questões excedem a execução.')
        prior={a['question_idx']:a for a in old['answers']}
        for a in answers:
            previous=prior.pop(a['question_idx'],{})
            if (a.get('seconds') or 0)<(previous.get('seconds') or 0):raise HTTPException(422,'O tempo da questão não pode retroceder.')
            a['changed_answer']=bool(previous.get('changed_answer') or a.get('changed_answer') or (previous.get('selected_answer') and previous['selected_answer']!=a['selected_answer']))
        if any(a.get('seconds') for a in prior.values()):raise HTTPException(422,'Não descarte o tempo já registrado.')
        value={**old,**values,'answers':answers,'revision':old['revision']+1,'updated_at':datetime.now(timezone.utc).isoformat()}
        exam.blueprint={**exam.blueprint,'execution':value};return acknowledgment(value)
    return await run_activity(uid,key,['exam-save',str(eid),body.model_dump(mode='json')],apply)
