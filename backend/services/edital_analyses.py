"""Owned structured analyses. PDF bytes are never stored in PostgreSQL.

Only the extracted analysis is JSON; identity, lifecycle, hash and source text
have explicit columns. Public reads never fetch source text/pages.
"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, delete
from sqlalchemy.orm import defer
from db.models.files import EditalAnalysis
from db.session import unit_of_work


def identity(value):
    try: return UUID(str(value))
    except (ValueError, TypeError, AttributeError): raise HTTPException(404, 'Análise não encontrada.')


def public(row, include_source=False):
    payload=deepcopy(row.structured_payload)
    payload.update(analysis_id=str(row.id), user_id=str(row.user_id), pdf_hash=row.content_hash,
        analysis_version=int(row.analysis_version), pdf_filename=row.filename,
        created_at=row.created_at, expires_at=row.expires_at, from_cache=row.from_cache,
        revision=row.revision, reviewed_at=row.reviewed_at)
    if include_source: payload.update(pdf_text=row.extracted_text or '', pdf_pages=row.pages or [])
    return jsonable_encoder(payload)


async def get(user_id, analysis_id, include_source=False):
    async with unit_of_work() as session:
        query=select(EditalAnalysis).where(EditalAnalysis.user_id==identity(user_id),EditalAnalysis.id==identity(analysis_id))
        if not include_source: query=query.options(defer(EditalAnalysis.extracted_text),defer(EditalAnalysis.pages))
        row=await session.scalar(query)
        if row is None: raise HTTPException(404, 'Análise não encontrada. Reenvie o edital para analisá-lo novamente.')
        return public(row,include_source)


async def cached(user_id, content_hash, version):
    async with unit_of_work() as session:
        row=await session.scalar(select(EditalAnalysis).where(EditalAnalysis.user_id==identity(user_id),
            EditalAnalysis.content_hash==content_hash,EditalAnalysis.analysis_version==str(version),
            EditalAnalysis.status=='completed',EditalAnalysis.expires_at>datetime.now(timezone.utc))
            .order_by(EditalAnalysis.created_at.desc()).limit(1))
        return public(row,True) if row else None


async def save(user_id, data):
    async with unit_of_work() as session:
        row=EditalAnalysis(id=identity(data['analysis_id']),user_id=identity(user_id),
            content_hash=data['pdf_hash'],status='completed',analysis_version=str(data['analysis_version']),
            structured_payload={key:deepcopy(data[key]) for key in
                ('concurso','multiple_cargos','cargos','independent_verification') if key in data},
            extracted_text=data.get('pdf_text',''),pages=data.get('pdf_pages',[]),filename=data.get('pdf_filename'),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            from_cache=data.get('from_cache',False))
        session.add(row); await session.flush()
        return public(row)


async def replace_cargo(user_id, analysis_id, index, cargo, revision=None):
    async with unit_of_work() as session:
        row=await session.scalar(select(EditalAnalysis).where(EditalAnalysis.user_id==identity(user_id),
            EditalAnalysis.id==identity(analysis_id)).with_for_update())
        if row is None: raise HTTPException(404,'Análise não encontrada.')
        if revision is not None and row.revision != revision:
            raise HTTPException(409,'A análise mudou em outra aba. Recarregue antes de salvar.')
        payload=deepcopy(row.structured_payload)
        if not 0<=index<len(payload.get('cargos',[])): raise HTTPException(422,'Cargo inválido.')
        payload['cargos'][index]=deepcopy(cargo); row.structured_payload=payload; row.revision+=1


async def list_owned(user_id):
    async with unit_of_work() as session:
        rows=(await session.scalars(select(EditalAnalysis).where(EditalAnalysis.user_id==identity(user_id),
            EditalAnalysis.status=='completed').options(defer(EditalAnalysis.extracted_text),defer(EditalAnalysis.pages))
            .order_by(EditalAnalysis.created_at.desc()).limit(200))).all()
        seen=set(); result=[]
        for row in rows:
            cargos=row.structured_payload.get('cargos') or []
            if not cargos or row.content_hash in seen: continue
            seen.add(row.content_hash)
            result.append(jsonable_encoder({'analysis_id':row.id,'pdf_filename':row.filename,'pdf_hash':row.content_hash,
                'concurso':row.structured_payload.get('concurso',{}),'num_cargos':len(cargos),
                'cargos_names':[c.get('nome','') for c in cargos],'created_at':row.created_at,'expires_at':row.expires_at}))
        return {'editais':result,'total':len(result)}


async def remove(user_id, analysis_id):
    async with unit_of_work() as session:
        uid=identity(user_id)
        row=await session.scalar(select(EditalAnalysis).where(EditalAnalysis.user_id==uid,EditalAnalysis.id==identity(analysis_id)))
        if row is None: raise HTTPException(404,'Análise não encontrada.')
        removed=await session.execute(delete(EditalAnalysis).where(EditalAnalysis.user_id==uid,EditalAnalysis.content_hash==row.content_hash))
        return {'success':True,'deleted_count':removed.rowcount,'message':f'{removed.rowcount} análise(s) removida(s).'}
