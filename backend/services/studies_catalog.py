"""Study catalog and aggregates, with no stored mutable cumulative counters."""
from datetime import datetime,timezone
from sqlalchemy import select,func,update
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from db.models.studies import StudyArea,StudyProgram,Notebook,StudyNote,StudySession,QuestionAttempt,StudyTopic

DEFAULT_AREAS = [
    ('Faculdade','#007AFF','graduation-cap'),('Concursos','#10B981','file-text'),
    ('Trabalho','#F59E0B','briefcase'),('Outros','#8B5CF6','folder')]


async def owned(session,model,user_id,identity):
    query=select(model).where(model.user_id==user_id,model.id==identity)
    if hasattr(model,'archived_at'): query=query.where(model.archived_at.is_(None))
    row=await session.scalar(query)
    if row is None: raise HTTPException(404,'Registro de estudos não encontrado.')
    if isinstance(row,StudyNote): await owned(session,Notebook,user_id,row.notebook_id)
    return row


def public(row):
    names={StudyArea:'area_id',StudyProgram:'program_id',Notebook:'notebook_id',StudyNote:'note_id'}
    data={c.key:getattr(row,c.key) for c in row.__table__.columns if c.key!='archived_at'}
    data[names[type(row)]]=data.pop('id')
    if isinstance(row,Notebook):
        syllabus=data.pop('syllabus') or {}
        data['conteudo_programatico']=syllabus.get('conteudo_programatico',[])
        data['topicos']=syllabus.get('topicos',[])
    if isinstance(row,StudyNote): data['attachments']=[]
    return jsonable_encoder(data)


async def areas(session,user):
    rows=list((await session.scalars(select(StudyArea).where(StudyArea.user_id==user.id,StudyArea.archived_at.is_(None))
        .order_by(StudyArea.order,StudyArea.id))).all())
    if not rows:
        for order,(name,color,icon) in enumerate(DEFAULT_AREAS):
            row=StudyArea(user_id=user.id,name=name,color=color,icon=icon,order=order)
            session.add(row); rows.append(row)
        await session.flush()
    return [public(row) for row in rows]


async def notebook_rows(session,user_id,area_id=None,program_id=None):
    query=select(Notebook).where(Notebook.user_id==user_id,Notebook.archived_at.is_(None))
    if area_id: query=query.where(Notebook.area_id==area_id)
    if program_id: query=query.where(Notebook.program_id==program_id)
    return list((await session.scalars(query.order_by(Notebook.created_at,Notebook.id))).all())


async def facts(session,user_id,notebooks):
    ids=[row.id for row in notebooks]
    if not ids: return {}
    attempts=(await session.execute(select(QuestionAttempt.notebook_id,func.sum(QuestionAttempt.total),func.sum(QuestionAttempt.correct))
        .where(QuestionAttempt.user_id==user_id,QuestionAttempt.notebook_id.in_(ids)).group_by(QuestionAttempt.notebook_id))).all()
    minutes=(await session.execute(select(StudySession.notebook_id,func.sum(StudySession.duration_minutes))
        .where(StudySession.user_id==user_id,StudySession.notebook_id.in_(ids),StudySession.completed.is_(True)).group_by(StudySession.notebook_id))).all()
    result={identity:{'total_questions':0,'correct_questions':0,'total_study_time_minutes':0} for identity in ids}
    for identity,total,correct in attempts: result[identity].update(total_questions=total,correct_questions=correct)
    for identity,total in minutes: result[identity]['total_study_time_minutes']=total
    return result


async def notebooks(session,user_id,area_id=None,program_id=None):
    rows=await notebook_rows(session,user_id,area_id,program_id)
    totals=await facts(session,user_id,rows)
    return [{**public(row),**totals[row.id]} for row in rows]


async def programs(session,user_id,area_id=None):
    query=select(StudyProgram).where(StudyProgram.user_id==user_id,StudyProgram.archived_at.is_(None))
    if area_id: query=query.where(StudyProgram.area_id==area_id)
    rows=(await session.scalars(query.order_by(StudyProgram.created_at,StudyProgram.id))).all()
    books=await notebook_rows(session,user_id,area_id)
    totals=await facts(session,user_id,books)
    grouped={}
    for book in books:
        values=grouped.setdefault(book.program_id,{'notebooks_count':0,'total_questions':0,'correct_questions':0,'total_study_time_minutes':0})
        values['notebooks_count']+=1
        for key,value in totals[book.id].items(): values[key]+=value
    return [{**public(row),**grouped.get(row.id,{'notebooks_count':0,'total_questions':0,'correct_questions':0,'total_study_time_minutes':0})} for row in rows]


async def archive(session,user_id,model,identity):
    row=await owned(session,model,user_id,identity)
    now=datetime.now(timezone.utc); row.archived_at=now
    if model is StudyArea:
        await session.execute(update(StudyProgram).where(StudyProgram.user_id==user_id,StudyProgram.area_id==identity).values(archived_at=now))
        await session.execute(update(Notebook).where(Notebook.user_id==user_id,Notebook.area_id==identity).values(archived_at=now))
    elif model is StudyProgram:
        await session.execute(update(Notebook).where(Notebook.user_id==user_id,Notebook.program_id==identity).values(archived_at=now))


async def sync_topics(session,notebook):
    topics=notebook.syllabus.get('conteudo_programatico') or notebook.syllabus.get('topicos') or []
    existing={row.topic_key:row for row in (await session.scalars(select(StudyTopic).where(
        StudyTopic.user_id==notebook.user_id,StudyTopic.notebook_id==notebook.id))).all()}
    for row in existing.values(): row.archived_at=datetime.now(timezone.utc)
    async def topic(key,name,position,parent=None):
        row=existing.get(key)
        if row is None:
            row=StudyTopic(user_id=notebook.user_id,notebook_id=notebook.id,topic_key=key,name=name,position=position,parent_id=parent)
            session.add(row); await session.flush()
        else: row.name=name; row.position=position; row.parent_id=parent; row.archived_at=None
        return row
    for index,value in enumerate(topics):
        name=str(value.get('assunto','')) if isinstance(value,dict) else str(value)
        parent=await topic(str(index),name,index)
        children=value.get('subtopicos',[]) if isinstance(value,dict) else []
        if isinstance(children,list):
            for child_index,child in enumerate(children): await topic(f'{index}_{child_index}',str(child),child_index,parent.id)
