import json
import re
from datetime import datetime,timezone,timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,Field,StrictInt
from sqlalchemy import select,func
from db.session import unit_of_work
from db.models.studies import Notebook,StudyNote,Flashcard,FlashcardReview
from services.auth_routes import account
from services.study_activity_routes import mutate
from services.studies_catalog import owned
from services.time import local_today
from services.planning import apply_xp

router=APIRouter(prefix='/study/flashcards')
_llm=None


def configure(llm):
    global _llm
    _llm=llm


class CardBody(BaseModel):
    notebook_id: UUID
    deck_name: str = Field(min_length=1,max_length=300)
    front: str = Field(min_length=1,max_length=12000)
    back: str = Field(min_length=1,max_length=20000)
    tags: list[str] = Field(default_factory=list,max_length=100)


class ReviewBody(BaseModel):
    quality: StrictInt = Field(ge=0,le=5)


class GenerateBody(BaseModel):
    note_id: UUID
    count: int = Field(default=5,ge=1,le=100)


def public(card,last=None):
    result={c.key:getattr(card,c.key) for c in card.__table__.columns if c.key!='archived_at'}
    result['flashcard_id']=result.pop('id'); result['last_review']=last
    return jsonable_encoder(result)


@router.get('')
async def cards(request: Request,notebook_id: UUID | None=None,deck_name: str | None=None,due_only: bool=False):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        query=select(Flashcard).join(Notebook,(Notebook.id==Flashcard.notebook_id)&(Notebook.user_id==Flashcard.user_id)).where(
            Flashcard.user_id==uid,Flashcard.archived_at.is_(None),Notebook.archived_at.is_(None))
        if notebook_id: query=query.where(Flashcard.notebook_id==notebook_id)
        if deck_name: query=query.where(Flashcard.deck_name==deck_name)
        if due_only: query=query.where(Flashcard.next_review<=local_today(user['timezone']))
        rows=(await session.scalars(query.order_by(Flashcard.created_at,Flashcard.id).limit(1000))).all()
        latest=dict((await session.execute(select(FlashcardReview.flashcard_id,func.max(FlashcardReview.reviewed_at)).where(
            FlashcardReview.user_id==uid,FlashcardReview.flashcard_id.in_([r.id for r in rows])).group_by(FlashcardReview.flashcard_id))).all())
        return [public(r,latest[r.id].astimezone(ZoneInfo(user['timezone'])).date() if r.id in latest else None) for r in rows]


@router.post('')
async def create_card(request: Request,body: CardBody):
    async def apply(session,user):
        await owned(session,Notebook,user.id,body.notebook_id)
        row=Flashcard(user_id=user.id,**body.model_dump(),next_review=local_today(user.timezone))
        session.add(row); await session.flush(); return public(row)
    return await mutate(request,['create-card',body.model_dump(mode='json')],apply)


@router.post('/{flashcard_id}/review')
async def review_card(request: Request,flashcard_id: UUID,body: ReviewBody):
    async def apply(session,user):
        card=await owned(session,Flashcard,user.id,flashcard_id)
        await owned(session,Notebook,user.id,card.notebook_id)
        quality=body.quality
        if quality<3: card.repetitions=0; card.interval_days=1
        else:
            card.interval_days=1 if card.repetitions==0 else (6 if card.repetitions==1 else min(36500,int(card.interval_days*card.ease_factor)))
            card.repetitions+=1
        card.ease_factor=max(1.3,card.ease_factor+.1-(5-quality)*(.08+(5-quality)*.02))
        card.next_review=local_today(user.timezone)+timedelta(days=card.interval_days)
        session.add(FlashcardReview(user_id=user.id,flashcard_id=card.id,reviewed_at=datetime.now(timezone.utc),quality=quality))
        earned=5 if quality>=3 else 2; apply_xp(user,earned)
        return {'message':'Card reviewed','next_review':card.next_review.isoformat(),'interval_days':card.interval_days,
            'ease_factor':card.ease_factor,'xp_earned':earned,'new_xp':user.xp}
    return await mutate(request,['review-card',str(flashcard_id),body.quality],apply)


@router.delete('/{flashcard_id}')
async def delete_card(request: Request,flashcard_id: UUID):
    async def apply(session,user):
        card=await owned(session,Flashcard,user.id,flashcard_id)
        card.archived_at=datetime.now(timezone.utc)
        return {'message':'Flashcard deleted'}
    return await mutate(request,['delete-card',str(flashcard_id)],apply)


@router.post('/generate')
async def generate_cards(request: Request,body: GenerateBody):
    user=await account(request)
    async with unit_of_work() as session:
        note=await owned(session,StudyNote,UUID(user['user_id']),body.note_id)
        title,content,nid=note.title,note.content,note.notebook_id
    response=await _llm(f'Com base no conteúdo, gere {body.count} flashcards para memorização.\n{title}\n{content}\n'
        'Responda JSON: [{"front":"Pergunta ou conceito","back":"Resposta ou explicação"}]. '
        'Foque nos conceitos importantes, perguntas ativas claras e respostas concisas mas completas.',
        session_id=user['user_id'],system_message='Você é um especialista em técnicas de memorização e aprendizado.',user_id=user['user_id'],task='study_explanation')
    match=re.search(r'\[[\s\S]*\]',response)
    if not match: return {'message':response}
    try:
        values=json.loads(match.group())
        if len(values)!=body.count: raise ValueError()
        cards=[CardBody(notebook_id=nid,deck_name=title or 'AI Generated',front=c['front'],back=c['back'],tags=['ai-generated']) for c in values]
    except (ValueError,TypeError,KeyError): raise HTTPException(502,'A IA retornou flashcards inválidos; nenhum cartão foi salvo.')
    async def apply(session,owner):
        await owned(session,StudyNote,owner.id,body.note_id)
        rows=[Flashcard(user_id=owner.id,**card.model_dump(),ai_generated=True,next_review=local_today(owner.timezone)) for card in cards]
        session.add_all(rows); await session.flush()
        return {'message':f'{len(rows)} flashcards created','flashcards':[public(r) for r in rows]}
    return await mutate(request,['generate-cards',body.model_dump(mode='json')],apply)
