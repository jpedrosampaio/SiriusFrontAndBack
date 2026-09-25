from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, HTTPException, Request
from pydantic import BaseModel, Field
from edital_quality import mark_discipline_quality
from edital_sources import locate_subject


class Topic(BaseModel):
    assunto: str = Field(min_length=1, max_length=2000)
    subtopicos: list[str] = Field(default_factory=list, max_length=300)


class Subject(BaseModel):
    nome: str = Field(min_length=1, max_length=300)
    peso: Optional[float] = Field(default=None, gt=0, le=1000)
    num_questoes: Optional[int] = Field(default=None, ge=0, le=10000)
    conteudo_programatico: list[Topic] = Field(min_length=1, max_length=500)


class Review(BaseModel):
    revision: int = Field(default=0, ge=0)
    disciplinas: list[Subject] = Field(min_length=1, max_length=100)


def review_router(db, authenticate):
    router = APIRouter(prefix='/study/programs/editais')

    async def owned(request, token, analysis_id):
        user = await authenticate(authorization=request.headers.get('Authorization'), session_token=token)
        query = {'user_id': user.user_id, 'analysis_id': analysis_id}
        doc = await db.edital_analyses.find_one(query, {'_id': 0})
        if not doc:
            raise HTTPException(404, 'Análise não encontrada')
        return query, doc

    @router.get('/{analysis_id}/source/{page}')
    async def get_page(request: Request, analysis_id: str, page: int, session_token: Optional[str] = Cookie(None)):
        _, doc = await owned(request, session_token, analysis_id)
        match = next((p for p in doc.get('pdf_pages', []) if p['page'] == page), None)
        if not match:
            raise HTTPException(404, 'Página indisponível. Reanalise o PDF para registrar as fontes.')
        return match

    @router.put('/{analysis_id}/cargos/{cargo_index}')
    async def review(request: Request, analysis_id: str, cargo_index: int, body: Review, session_token: Optional[str] = Cookie(None)):
        query, doc = await owned(request, session_token, analysis_id)
        cargos = doc.get('cargos', [])
        if not 0 <= cargo_index < len(cargos):
            raise HTTPException(404, 'Cargo não encontrado')
        subjects = []
        for incoming in body.disciplinas:
            previous = next((s for s in cargos[cargo_index].get('disciplinas', []) if s.get('nome') == incoming.nome), {})
            item = {**previous, **incoming.model_dump()}
            for field in ('peso', 'num_questoes'):
                if incoming.model_dump()[field] != previous.get(field):
                    item[field + '_status'] = 'informado_pelo_usuario'
            if item.get('peso_status') == 'informado_pelo_usuario':
                item['peso_fonte'] = 'Ajustado pelo usuário; confira o edital original'
            item['fontes'] = locate_subject(item['nome'], doc.get('pdf_pages', []))
            item['topicos'] = [t.assunto for t in incoming.conteudo_programatico]
            subjects.append(item)
        cargos[cargo_index]['disciplinas'] = subjects
        mark_discipline_quality(cargos)
        query['revision'] = body.revision if body.revision else {'$in': [0, None]}
        changed = await db.edital_analyses.update_one(query, {'$set': {'cargos': cargos, 'reviewed_at': datetime.now(timezone.utc).isoformat()}, '$inc': {'revision': 1}})
        if not changed.matched_count:
            raise HTTPException(409, 'A análise mudou em outra aba. Recarregue antes de salvar.')
        return {'cargos': cargos, 'revision': body.revision + 1}

    return router
