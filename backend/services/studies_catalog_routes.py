from datetime import date as Date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException,UploadFile,File
from pydantic import BaseModel,Field
from sqlalchemy import select,func
from db.activity import run_activity
from db.session import unit_of_work
from db.models.studies import StudyArea,StudyProgram,Notebook,StudyNote
from services.auth_routes import account
from services import studies_catalog as catalog

router=APIRouter(prefix='/study')


class AreaBody(BaseModel):
    name: str = Field(min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=10000)
    color: str = Field(default='#007AFF',max_length=50)
    icon: str = Field(default='book',max_length=100)


class ProgramBody(AreaBody):
    area_id: UUID
    target_date: Date | None = None


class ProgramUpdate(BaseModel):
    name: str | None = Field(default=None,min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=10000)
    color: str | None = Field(default=None,max_length=50)
    icon: str | None = Field(default=None,max_length=100)
    target_date: Date | None = None
    status: Literal['active','completed','paused'] | None = None


class NotebookBody(BaseModel):
    area_id: UUID
    program_id: UUID | None = None
    name: str = Field(min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=10000)
    color: str = Field(default='#007AFF',max_length=50)
    tags: list[str] = Field(default_factory=list,max_length=100)


class NotebookUpdate(BaseModel):
    area_id: UUID | None = None
    program_id: UUID | None = None
    name: str | None = Field(default=None,min_length=1,max_length=200)
    description: str | None = Field(default=None,max_length=10000)
    color: str | None = Field(default=None,max_length=50)
    tags: list[str] | None = Field(default=None,max_length=100)
    weight: float | None = Field(default=None,gt=0,le=1000,allow_inf_nan=False)
    dificuldade: str | None = Field(default=None,max_length=100)
    user_difficulty: str | None = Field(default=None,max_length=100)
    num_questoes_edital: int | None = Field(default=None,ge=0)
    topicos: list | None = Field(default=None,max_length=5000)
    conteudo_programatico: list | None = Field(default=None,max_length=5000)
    recursos_recomendados: list | None = Field(default=None,max_length=500)


class NoteBody(BaseModel):
    notebook_id: UUID
    title: str = Field(min_length=1,max_length=500)
    content: str = Field(default='',max_length=1000000)
    tags: list[str] = Field(default_factory=list,max_length=100)
    links: list[dict] = Field(default_factory=list,max_length=100)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None,min_length=1,max_length=500)
    content: str | None = Field(default=None,max_length=1000000)
    tags: list[str] | None = Field(default=None,max_length=100)
    links: list[dict] | None = Field(default=None,max_length=100)


async def mutate(request,fingerprint,apply):
    user=await account(request)
    return await run_activity(UUID(user['user_id']),request.headers.get('Idempotency-Key'),fingerprint,apply)


@router.get('/areas')
async def areas(request: Request):
    user=await account(request)
    return await run_activity(UUID(user['user_id']),None,['areas'],catalog.areas)


@router.post('/areas')
async def area_create(request: Request,body: AreaBody):
    async def apply(session,user):
        highest=await session.scalar(select(func.max(StudyArea.order)).where(StudyArea.user_id==user.id))
        row=StudyArea(user_id=user.id,order=(highest if highest is not None else -1)+1,**body.model_dump())
        session.add(row); await session.flush(); return catalog.public(row)
    return await mutate(request,['area_create',body.model_dump()],apply)


async def archive(request,model,identity,label):
    async def apply(session,user):
        await catalog.archive(session,user.id,model,identity)
        return {'message':label+' deleted'}
    return await mutate(request,['archive',label,str(identity)],apply)


@router.delete('/areas/{area_id}')
async def area_delete(request: Request,area_id: UUID): return await archive(request,StudyArea,area_id,'Area')


@router.get('/programs')
async def programs(request: Request,area_id: UUID | None = None):
    user=await account(request)
    async with unit_of_work() as session: return await catalog.programs(session,UUID(user['user_id']),area_id)


@router.post('/programs')
async def program_create(request: Request,body: ProgramBody):
    async def apply(session,user):
        await catalog.owned(session,StudyArea,user.id,body.area_id)
        row=StudyProgram(user_id=user.id,**body.model_dump()); session.add(row); await session.flush()
        return {**catalog.public(row),'total_questions':0,'correct_questions':0,'total_study_time_minutes':0,'notebooks_count':0}
    return await mutate(request,['program_create',body.model_dump(mode='json')],apply)


@router.patch('/programs/{program_id}')
async def program_update(request: Request,program_id: UUID,body: ProgramUpdate):
    async def apply(session,user):
        row=await catalog.owned(session,StudyProgram,user.id,program_id)
        for key,value in body.model_dump(exclude_unset=True).items():
            if value is None and key not in ('target_date','description'): raise HTTPException(422,'Campo não pode ser nulo.')
            setattr(row,key,value)
        await session.flush(); await session.refresh(row); return catalog.public(row)
    return await mutate(request,['program_update',str(program_id),body.model_dump(mode='json',exclude_unset=True)],apply)


@router.delete('/programs/{program_id}')
async def program_delete(request: Request,program_id: UUID): return await archive(request,StudyProgram,program_id,'Program')


@router.get('/notebooks')
async def notebooks(request: Request,area_id: UUID | None = None,program_id: UUID | None = None):
    user=await account(request)
    async with unit_of_work() as session: return await catalog.notebooks(session,UUID(user['user_id']),area_id,program_id)


async def validate_links(session,user_id,area_id,program_id):
    await catalog.owned(session,StudyArea,user_id,area_id)
    if program_id:
        program=await catalog.owned(session,StudyProgram,user_id,program_id)
        if program.area_id!=area_id: raise HTTPException(422,'O programa pertence a outra área.')


@router.post('/notebooks')
async def notebook_create(request: Request,body: NotebookBody):
    async def apply(session,user):
        await validate_links(session,user.id,body.area_id,body.program_id)
        row=Notebook(user_id=user.id,**body.model_dump()); session.add(row); await session.flush()
        return {**catalog.public(row),'total_questions':0,'correct_questions':0,'total_study_time_minutes':0}
    return await mutate(request,['notebook_create',body.model_dump(mode='json')],apply)


@router.patch('/notebooks/{notebook_id}')
async def notebook_update(request: Request,notebook_id: UUID,body: NotebookUpdate):
    async def apply(session,user):
        row=await catalog.owned(session,Notebook,user.id,notebook_id)
        values=body.model_dump(exclude_unset=True)
        await validate_links(session,user.id,values.get('area_id',row.area_id),values.get('program_id',row.program_id))
        syllabus=dict(row.syllabus)
        for key,value in values.items():
            if key in ('topicos','conteudo_programatico'): syllabus[key]=value or []
            else:
                if value is None and key not in ('program_id','description','user_difficulty','num_questoes_edital'):
                    raise HTTPException(422,'Campo não pode ser nulo.')
                setattr(row,key,value)
        row.syllabus=syllabus
        if 'topicos' in values or 'conteudo_programatico' in values: await catalog.sync_topics(session,row)
        await session.flush()
        await session.refresh(row)
        totals=await catalog.facts(session,user.id,[row])
        return {**catalog.public(row),**totals[row.id]}
    return await mutate(request,['notebook_update',str(notebook_id),body.model_dump(mode='json',exclude_unset=True)],apply)


@router.delete('/notebooks/{notebook_id}')
async def notebook_delete(request: Request,notebook_id: UUID): return await archive(request,Notebook,notebook_id,'Notebook')


@router.get('/notes')
async def notes(request: Request,notebook_id: UUID | None = None):
    user=await account(request); uid=UUID(user['user_id'])
    query=select(StudyNote).join(Notebook,(Notebook.id==StudyNote.notebook_id)&(Notebook.user_id==StudyNote.user_id))
    query=query.where(StudyNote.user_id==uid,Notebook.archived_at.is_(None))
    if notebook_id: query=query.where(StudyNote.notebook_id==notebook_id)
    async with unit_of_work() as session:
        return [catalog.public(row) for row in (await session.scalars(query.order_by(StudyNote.updated_at.desc(),StudyNote.id))).all()]


@router.post('/notes')
async def note_create(request: Request,body: NoteBody):
    async def apply(session,user):
        await catalog.owned(session,Notebook,user.id,body.notebook_id)
        row=StudyNote(user_id=user.id,**body.model_dump()); session.add(row); await session.flush()
        return catalog.public(row)
    return await mutate(request,['note_create',body.model_dump(mode='json')],apply)


@router.patch('/notes/{note_id}')
async def note_update(request: Request,note_id: UUID,body: NoteUpdate):
    async def apply(session,user):
        row=await catalog.owned(session,StudyNote,user.id,note_id)
        for key,value in body.model_dump(exclude_unset=True).items():
            if value is None: raise HTTPException(422,'Campo não pode ser nulo.')
            setattr(row,key,value)
        await session.flush(); await session.refresh(row); return catalog.public(row)
    return await mutate(request,['note_update',str(note_id),body.model_dump(mode='json',exclude_unset=True)],apply)


@router.delete('/notes/{note_id}')
async def note_delete(request: Request,note_id: UUID):
    async def apply(session,user):
        row=await catalog.owned(session,StudyNote,user.id,note_id); await session.delete(row)
        return {'message':'Note deleted'}
    return await mutate(request,['note_delete',str(note_id)],apply)


@router.post('/notes/{note_id}/upload')
async def note_upload(request: Request,note_id: UUID,file: UploadFile = File(...)):
    user=await account(request)
    async with unit_of_work() as session: await catalog.owned(session,StudyNote,UUID(user['user_id']),note_id)
    raise HTTPException(503,'Armazenamento de anexos ainda não configurado. A nota continua disponível.')
