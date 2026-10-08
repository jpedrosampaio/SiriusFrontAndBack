import json
from uuid import UUID
from sqlalchemy import select
from db.models.studies import Notebook,StudyNote,StudyTopic
from db.session import unit_of_work
from services.studies_catalog import owned
from services.study_evidence import attempts


async def context(user_id,notebook_id,topic_key,mode,session=None):
    if session is None:
        async with unit_of_work() as owned_session:
            return await context(user_id,notebook_id,topic_key,mode,session=owned_session)
    uid,nid=UUID(str(user_id)),UUID(str(notebook_id))
    book=await owned(session,Notebook,uid,nid)
    topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==uid,StudyTopic.notebook_id==nid,
        StudyTopic.topic_key==topic_key,StudyTopic.archived_at.is_(None))) if topic_key is not None else None
    if topic_key is not None and topic is None:raise ValueError('Assunto não encontrado.')
    if mode=='materials':
        notes=(await session.scalars(select(StudyNote).where(StudyNote.user_id==uid,StudyNote.notebook_id==nid)
            .order_by(StudyNote.updated_at.desc(),StudyNote.id).limit(3))).all()
        if not notes:raise ValueError('Adicione um material próprio antes de gerar questões desse contexto.')
        return {'source_type':'user_material','source_ids':[str(row.id) for row in notes],
            'text':'\n'.join(row.content[:4000] for row in notes)[:12000]}
    if mode=='errors':
        rows=await attempts(session,uid,'UTC',notebook_id=nid,limit=500,active_topics=True)
        rows=[r for r in rows if not r['correct'] and (topic_key is None or r['topic_key']==topic_key)][:20]
        if not rows:raise ValueError('Este assunto ainda não tem erros individuais registrados.')
        return {'source_type':'error_evidence','source_ids':[r['attempt_id'] for r in rows],
            'text':json.dumps([{'question':r['question'][:1500],'error':r['error_reason']} for r in rows],ensure_ascii=False)[:12000]}
    text=json.dumps({'name':book.name,'selected_topic':topic.name if topic else None,
        'syllabus':book.syllabus},ensure_ascii=False)
    return {'source_type':'syllabus','source_ids':[str(nid)]+([str(topic.id)] if topic else []),
        'partial':len(text)>12000,'text':text[:12000]}
