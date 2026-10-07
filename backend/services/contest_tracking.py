"""Owned source persistence and host-wide polling throttles."""
import hashlib
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from uuid import UUID,uuid4
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select,func,update
from sqlalchemy.dialects.postgresql import insert
from db.models.contests import ContestSource,ContestUpdate,ContestHostLimit
from db.models.studies import StudyProgram
from db.repositories.identity import IdentityRepository
from db.session import unit_of_work
from contest_sources import validate_url,provider_for,trust,SourceUnavailable


def identity(value):
    try:return UUID(str(value))
    except (ValueError,TypeError,AttributeError):raise HTTPException(404,'Fonte ou preparação não encontrada.') from None


async def program(session,uid,pid):
    row=await session.scalar(select(StudyProgram).where(StudyProgram.user_id==uid,StudyProgram.id==pid,StudyProgram.archived_at.is_(None)))
    if row is None:raise HTTPException(404,'Preparação não encontrada.')
    return row


def source_json(row):
    return jsonable_encoder({'source_id':row.id,'user_id':row.user_id,'program_id':row.program_id,
        **{key:getattr(row,key) for key in ('url','title','trust','provider','terms_confirmed_at','created_at','next_poll','enabled','failures','status','last_checked','error')}})


def update_json(row):
    return jsonable_encoder({'update_id':row.id,'user_id':row.user_id,'program_id':row.program_id,'source_id':row.source_id,'hash':row.content_hash,
        **{key:getattr(row,key) for key in ('source','title','url','document_url','document_type','hash_basis','source_type','official','published_at',
            'detected_at','summary','changes','text_extraction','text_partial')}})


async def list_sources(user_id,program_id):
    uid,pid=identity(user_id),identity(program_id)
    async with unit_of_work() as session:
        await program(session,uid,pid)
        rows=(await session.scalars(select(ContestSource).where(ContestSource.user_id==uid,ContestSource.program_id==pid,ContestSource.deleted_at.is_(None))
            .order_by(ContestSource.created_at,ContestSource.id))).all()
        return [source_json(row) for row in rows]


async def add(user_id,program_id,body):
    uid,pid=identity(user_id),identity(program_id)
    async with unit_of_work() as session:
        await IdentityRepository(session).by_id(uid,lock=True)
        await program(session,uid,pid)
        if not body.terms_allow_monitoring:raise HTTPException(422,'Confirme que os termos da página permitem acompanhamento automático.')
        try:url=validate_url(body.url)
        except SourceUnavailable as exc:raise HTTPException(422,str(exc)) from None
        digest=hashlib.sha256(url.encode()).hexdigest()
        row=await session.scalar(select(ContestSource).where(ContestSource.user_id==uid,ContestSource.program_id==pid,ContestSource.url_hash==digest))
        if row and row.deleted_at is None:return source_json(row)
        count=await session.scalar(select(func.count()).select_from(ContestSource).where(ContestSource.user_id==uid,ContestSource.program_id==pid,ContestSource.deleted_at.is_(None)))
        if count>=5:raise HTTPException(409,'Limite de cinco fontes por preparação.')
        now=datetime.now(timezone.utc)
        if row:
            row.deleted_at=None;row.enabled=True;row.next_poll=now;row.terms_confirmed_at=now;row.title=body.title.strip()
        else:
            row=ContestSource(user_id=uid,program_id=pid,url=url,url_hash=digest,title=body.title.strip(),trust=trust(url),
                provider=provider_for(url).name,terms_confirmed_at=now,next_poll=now)
            session.add(row)
        await session.flush();await session.refresh(row)
        return source_json(row)


async def remove(user_id,program_id,source_id):
    uid,pid,sid=identity(user_id),identity(program_id),identity(source_id)
    async with unit_of_work() as session:
        await IdentityRepository(session).by_id(uid,lock=True);await program(session,uid,pid)
        row=await session.scalar(select(ContestSource).where(ContestSource.user_id==uid,ContestSource.program_id==pid,ContestSource.id==sid).with_for_update())
        if row is None:raise HTTPException(404,'Fonte não encontrada.')
        row.deleted_at=datetime.now(timezone.utc);row.enabled=False;row.lease_token=None
        row.snapshot='';row.etag=None;row.modified=None
    return {'removed':True}


async def timeline(user_id,program_id,exams=False):
    uid,pid=identity(user_id),identity(program_id)
    async with unit_of_work() as session:
        await program(session,uid,pid)
        query=select(ContestUpdate).where(ContestUpdate.user_id==uid,ContestUpdate.program_id==pid)
        if exams:query=query.where(ContestUpdate.document_type.in_(['exam','answer_key']))
        rows=(await session.scalars(query.order_by(ContestUpdate.detected_at.desc(),ContestUpdate.id).limit(100))).all()
        return [update_json(row) for row in rows]


async def claim(user_id,program_id,source_id):
    uid,pid,sid=identity(user_id),identity(program_id),identity(source_id)
    now=datetime.now(timezone.utc)
    async with unit_of_work() as session:
        await program(session,uid,pid)
        row=await session.scalar(select(ContestSource).where(ContestSource.user_id==uid,ContestSource.program_id==pid,
            ContestSource.id==sid,ContestSource.deleted_at.is_(None)).with_for_update())
        if row is None:raise HTTPException(404,'Fonte não encontrada.')
        if not row.enabled or row.next_poll>now:return {'status':'cached','message':'A consulta já está agendada; intervalo mínimo de seis horas.'}
        row.next_poll=now+timedelta(hours=6);row.lease_token=uuid4()
        host=urlsplit(row.url).hostname
        await session.execute(insert(ContestHostLimit).values(host=host,next_poll=now).on_conflict_do_nothing(index_elements=['host']))
        allowed=await session.scalar(update(ContestHostLimit).where(ContestHostLimit.host==host,ContestHostLimit.next_poll<=now)
            .values(next_poll=now+timedelta(minutes=2)).returning(ContestHostLimit.host))
        if not allowed:
            row.next_poll=now+timedelta(minutes=15);row.lease_token=None
            return {'status':'deferred','message':'Outra fonte deste domínio foi consultada recentemente.'}
        return {'claimed':True,'source_id':str(row.id),'user_id':str(uid),'program_id':str(pid),'lease':str(row.lease_token),
            **{key:getattr(row,key) for key in ('url','title','trust','snapshot','content_hash','etag','modified','failures')}}


async def finish(source,page=None,documents=(),error=None):
    uid,pid,sid=identity(source['user_id']),identity(source['program_id']),identity(source['source_id'])
    now=datetime.now(timezone.utc)
    async with unit_of_work() as session:
        await IdentityRepository(session).by_id(uid,lock=True)
        active=await session.scalar(select(StudyProgram.id).where(StudyProgram.user_id==uid,StudyProgram.id==pid,StudyProgram.archived_at.is_(None)))
        row=await session.scalar(select(ContestSource).where(ContestSource.user_id==uid,ContestSource.id==sid,ContestSource.deleted_at.is_(None),
            ContestSource.lease_token==identity(source['lease'])).with_for_update())
        if active is None or row is None:return False
        row.last_checked=now;row.lease_token=None
        if error is not None:
            row.failures=min(8,row.failures+1);row.status='unavailable';row.error=error[:300]
            row.next_poll=now+timedelta(hours=min(72,6*2**row.failures))
            return True
        row.status='ok';row.error=None;row.failures=0
        if page is not None:
            for item in documents:
                values={key:item.get(key) for key in ('title','url','document_url','document_type','hash_basis','source_type','official','published_at','changes','text_extraction','text_partial')}
                await session.execute(insert(ContestUpdate).values(user_id=uid,program_id=pid,source_id=sid,source=row.title,
                    content_hash=item['hash'],detected_at=now,summary='Documento encontrado na página acompanhada; confira o conteúdo na fonte.',**values)
                    .on_conflict_do_nothing(index_elements=['user_id','source_id','content_hash']))
            row.snapshot=page.text;row.content_hash=page.content_hash;row.etag=page.etag;row.modified=page.modified
        return True


async def due():
    async with unit_of_work() as session:
        rows=(await session.execute(select(ContestSource.user_id,ContestSource.program_id,ContestSource.id).join(StudyProgram,
            (StudyProgram.id==ContestSource.program_id)&(StudyProgram.user_id==ContestSource.user_id)).where(ContestSource.enabled.is_(True),
            ContestSource.deleted_at.is_(None),ContestSource.next_poll<=datetime.now(timezone.utc),StudyProgram.archived_at.is_(None))
            .order_by(ContestSource.next_poll,ContestSource.id).limit(20))).all()
        return [(str(uid),str(pid),str(sid)) for uid,pid,sid in rows]
